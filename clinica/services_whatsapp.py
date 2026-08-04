"""Cliente de WhatsApp Cloud API (Meta) y construcción de mensajes para Citas."""
import requests
from django.conf import settings

# Verificar la versión vigente en Meta for Developers al implementar:
# Meta deprecia versiones de Graph API ~2 años después de su lanzamiento,
# v19.0 (lanzada feb-2024) puede ya no estar disponible.
WHATSAPP_API_URL = "https://graph.facebook.com/v21.0"

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
         'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
DIAS_SEMANA = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']

# Dirección/instrucciones de llegada por sede, usadas en el template de confirmación.
# 'republica' es el fallback cuando consultorio es None o la sede no está en este mapa.
# Sin saltos de línea: WhatsApp rechaza parámetros de template con \n/\t (error 132018).
SEDE_DIRECCIONES = {
    'republica': '📍 Piedras Negras 1925, República Oriente, 25280 Saltillo, Coah. '
                 'https://goo.gl/maps/ZT79pYXUtkrZAow1A',
    'morelos': '📍 Blvd Morelos 801, Morelos, Saltillo, Coah. '
               'https://maps.app.goo.gl/psTTcpmYCcWPc6yX6',
    'colinas': '📍 Mier 1235, Colinas de Santiago, Real del Sol III, 25016, Saltillo, Coah. '
               'https://maps.app.goo.gl/BpnUL9PL2511a9qF8',
    'trabajo_social': '📍 2do Piso, Facultad de Trabajo Social UAdeC "Dra. Cuquita Cepeda de Dávila", '
                       'Col. Adolfo López Mateos, Saltillo, Coah. '
                       'https://maps.app.goo.gl/v6EVAQJZXDPjDecJ9',
    'zoom': 'El enlace de la reunión virtual se le enviará una vez realizada la transferencia '
            'y compartido el comprobante al 844 443 9987. '
            'Le solicitamos conectarse puntualmente.',
    'externo': 'En la ubicación acordada con su terapeuta.',
}

# Leyenda legal exigida en todas las plantillas de pacientes reales de INTRA
# (no aplica a las plantillas DEMO de prospectos, que son de otro negocio).
# El link apunta a la página pública que muestra Políticas de Atención + Aviso
# de Privacidad Integral (ver clinica/views.py:terminos_condiciones).
AVISO_LEGAL = (
    'Al continuar acepta los Términos y condiciones del servicio y política de '
    'privacidad, puede consultarlas en: https://agenda.intra.org.mx/terminos/'
)

# Cuerpo literal de cada template aprobado en Meta (ver planwhfinal.md secciones 3-5).
# Meta no devuelve el texto renderizado en la respuesta del API, así que se
# reconstruye aquí para poder mostrarlo en el panel de chat (MensajeWhatsApp.texto).
# Si se edita un template en Meta Business Manager, hay que actualizar esto también.
#
# IMPORTANTE: agregar AVISO_LEGAL aquí NO cambia lo que WhatsApp envía de verdad.
# Meta solo entrega el texto exacto que fue aprobado en WhatsApp Manager, así que
# cada uno de estos 5 templates (los de pacientes reales) debe editarse ahí con el
# texto de abajo y reenviarse a aprobación antes de que el cambio surta efecto.
TEMPLATE_BODIES = {
    'recordatorio_cita_5_dias':
        'Hola {{1}}, te recordamos que tienes una cita programada el {{2}} a las {{3}} '
        'en el consultorio de {{4}}.\n\n'
        'Tu cita es con: {{5}}\nServicio: {{6}}\n\n'
        'Ante cualquier cambio o duda, no dudes en contactarnos. ¡Te esperamos!\n\n'
        + AVISO_LEGAL,
    'recordatorio_cita_3_dias':
        'Hola {{1}}, te recordamos que en 3 días tienes una cita con nosotros.\n\n'
        '📅 {{2}} a las {{3}}\n📍 Consultorio {{4}}\n👨‍⚕️ {{5}}\n🏥 Servicio: {{6}}\n\n'
        '¡Te esperamos puntualmente!\n\n'
        + AVISO_LEGAL,
    'confirmacion_cita_1_dia':
        'Buenas tardes, confirmamos su cita el {{1}} a las {{2}}, consultorio {{3}}.\n\n'
        'Profesional: {{4}}\nPaciente: {{5}}\nServicio: {{6}}\n\n'
        'Por favor llegue puntual; no podremos reprogramar ni extender el tiempo.\n\n'
        'Costo: ${{7}}. ¿Pagará por transferencia, efectivo o tarjeta?\n\n'
        'Transferencia:\n🏦 Banco: BBVA\n💳 Tarjeta: 4555 1130 1572 4679\n👤 Titular: Miriam Rubí Iracheta\n\n'
        '{{8}}\n\nResponda *CONFIRMO* a este mensaje para confirmar su cita.\n\n'
        'Para cambios o dudas, escríbanos al 844 443 9987.\n\n'
        + AVISO_LEGAL,
    'encuesta_conformidad':
        'Hola {{1}}, esperamos que tu sesión de {{2}} con {{3}} haya sido de gran beneficio para ti.\n\n'
        'Nos gustaría conocer tu experiencia. ¿Cómo calificarías tu atención del 1 al 5?\n\n'
        '1️⃣ Muy mala\n2️⃣ Mala\n3️⃣ Regular\n4️⃣ Buena\n5️⃣ Excelente\n\n'
        'Tu opinión nos ayuda a mejorar. ¡Gracias!\n\n'
        + AVISO_LEGAL,
    'reactivacion_paciente':
        'Hola {{1}}, hace un tiempo que no nos visitas y queremos saber cómo estás.\n\n'
        'En {{2}} seguimos disponibles para apoyarte en tu bienestar. Si deseas retomar tu '
        'proceso o agendar una nueva cita, con gusto te atendemos.\n\n'
        'Comunícate con nosotros o escríbenos aquí. ¡Te esperamos! 🌿\n\n'
        + AVISO_LEGAL,

    # --- Plantillas de DEMO para prospectos (panel exclusivo SUPERADMIN) ---
    'recordatorio_pago_3_dias':
        'Hola {{1}}, te recordamos que en 3 días vence tu mensualidad en la Escuela de '
        'Enfermería Dorothea 🩺\n\n'
        '📅 Fecha de vencimiento: {{2}}\n💳 Monto: ${{3}}\n\n'
        '🏪 Pago en OXXO: menciona la referencia DEMO-12345 en cualquier tienda\n\n'
        'Si ya realizaste tu pago, ignora este mensaje.\n\n'
        '¡Gracias por formar parte de Dorothea!',
    # Nombre con guion bajo inicial: asi quedo registrada/aprobada en Meta
    # (WhatsApp Manager), no coincide con la convencion de las demas.
    '_recordatorio_pago_mismo_dia':
        'Hola {{1}}, hoy {{2}} vence tu mensualidad en la Escuela de Enfermería Dorothea 🩺\n\n'
        '💳 Monto a pagar: ${{3}}\n\n'
        '🏪 Pago en OXXO: menciona la referencia DEMO-12345 en cualquier tienda\n\n'
        'Te recordamos realizar tu pago hoy para mantener tu acceso a clases y evitar recargos.\n\n'
        '¡Gracias por tu compromiso con tu formación! 🩺',

    # --- Campañas masivas de Academia (panel Dirección Comercial) ---
    # La clave es el nombre EXACTO con el que la plantilla quedó aprobada en
    # Meta ('masivos1'); si no coincide, la API responde 132001. El nombre
    # legible para el panel va en CAMPANAS_MASIVAS['titulo'].
    # Sin variables a propósito: el mismo texto para todos, aprueba más rápido en
    # Meta y no hay riesgo de parámetro vacío en un envío de ~250 mensajes.
    'masivos1':
        '🎓 ¡Atención, estudiantes de Academia! 🚨\n\n'
        '¡Últimos lugares para el Diplomado en Psicoterapia Infantil!\n\n'
        'Solo esta semana podrás aprovechar esta promoción exclusiva:\n\n'
        '✅ Inscripción por solo $500 (precio regular $650)\n'
        '✅ Mensualidad por solo $500 (precio regular $650)\n\n'
        '⏳ La promoción termina esta semana, después de esa fecha la inscripción y la '
        'mensualidad regresan a $650.\n\n'
        '📚 Inicio de clases: 15 de agosto.\n\n'
        '📲 Inscríbete hoy y asegura tu lugar con este precio preferencial.\n\n'
        '📞 Contáctanos al 844 236 9864.\n\n'
        '¡No dejes pasar esta oportunidad de fortalecer tu formación profesional en '
        'Psicoterapia Infantil!',
}

# Plantillas ofrecidas en el panel de Mensajes Masivos (Dirección Comercial).
# 'campos' vacío = plantilla sin variables. La clave debe existir y estar
# APROBADA en Meta Business Manager con exactamente ese nombre y ese idioma:
# si cualquiera de los dos no coincide, la API responde 132001.
CAMPANAS_MASIVAS = {
    'masivos1': {
        'titulo': 'Promoción — Diplomado en Psicoterapia Infantil',
        'descripcion': 'Últimos lugares, inscripción y mensualidad a $500. Inicio 15 de agosto.',
        'campos': [],
        'idioma': 'es_MX',
    },
}

# Campañas de demo mostradas en el panel "DEMOS" (acceso exclusivo SUPERADMIN).
# Cada plantilla debe existir y estar aprobada en Meta Business Manager con el
# mismo nombre en 'clave' antes de poder enviarse. 'campos' define el orden
# exacto de los {{N}} del body (ver TEMPLATE_BODIES arriba).
DEMOS_CAMPANAS = {
    'dorothea': {
        'nombre': 'Escuela de Enfermería Dorothea',
        'plantillas': [
            {
                'clave': 'recordatorio_pago_3_dias',
                'titulo': 'Recordatorio de pago — 3 días antes',
                'campos': ['nombre', 'fecha_vencimiento', 'monto'],
            },
            {
                'clave': '_recordatorio_pago_mismo_dia',
                'titulo': 'Recordatorio de pago — mismo día',
                'campos': ['nombre', 'fecha_vencimiento', 'monto'],
            },
        ],
    },
}

# Números a los que dispara el botón "PROBAR ENVÍO" del panel de Mensajes
# Masivos. Se validan contra esta lista en el servidor: el front no puede pedir
# una prueba a un número arbitrario.
TELEFONOS_PRUEBA = ['8445860246', '8118226008']

# Clasificación de los códigos de error de la Cloud API para decidir qué hacer
# con cada envío fallido dentro de un lote.
# Reintentables: se dejan en 'pendiente' y el siguiente lote los vuelve a tomar.
ERRORES_REINTENTABLES = {'4', '80007', '130429', '131056', '613'}
# Definitivos: el mensaje nunca va a llegar, marcar 'fallido' y no insistir.
ERRORES_DEFINITIVOS = {'131026', '131047', '131049', '130472', '131031', '133010'}


def clasificar_error(codigo: str) -> str:
    """
    'plantilla'    -> problema con la plantilla en Meta: aborta la campaña entera,
                      porque va a fallar idéntico en los 248 envíos.
    'reintentable' -> límite de tasa momentáneo, se reintenta en el siguiente lote.
    'definitivo'   -> este número en particular no puede recibirlo.
    """
    codigo = str(codigo or '')
    if codigo.startswith('132'):
        return 'plantilla'
    if codigo in ERRORES_REINTENTABLES:
        return 'reintentable'
    return 'definitivo'


def extraer_error(respuesta: dict):
    """Saca (codigo, mensaje) de una respuesta de error de la Cloud API."""
    error = (respuesta or {}).get('error') or {}
    codigo = str(error.get('code', '')) if error else ''
    mensaje = error.get('message') or ''
    detalle = (error.get('error_data') or {}).get('details')
    if detalle:
        mensaje = f'{mensaje} — {detalle}'
    if not error:
        mensaje = mensaje or 'Respuesta inesperada de Meta'
    return codigo, mensaje


CAMPOS_DEMO_LABELS = {
    'nombre': 'Nombre del contacto',
    'fecha_vencimiento': 'Fecha de vencimiento',
    'monto': 'Monto ($)',
}


def renderizar_template(nombre_template: str, parametros: list) -> str:
    """Sustituye {{1}}, {{2}}... en el cuerpo del template por los parámetros enviados."""
    texto = TEMPLATE_BODIES.get(nombre_template, '')
    for i, valor in enumerate(parametros, start=1):
        texto = texto.replace('{{%d}}' % i, str(valor))
    return texto


def _normalizar_telefono(telefono: str) -> str:
    """
    Convierte cualquier formato a 52XXXXXXXXXX (formato Meta).
    BD guarda: 8110001001 (10 dígitos, Paciente.telefono)
    Meta entrega/espera: 528110001001 o 5218110001001
    """
    digits = ''.join(filter(str.isdigit, telefono or ''))
    if len(digits) == 13 and digits.startswith('521'):
        digits = '52' + digits[3:]
    if len(digits) == 10:
        digits = '52' + digits
    return digits


def buscar_paciente_por_wa_id(wa_id: str):
    """
    Busca el Paciente cuyo teléfono corresponde al wa_id que llegó por el webhook.
    BD guarda 10 dígitos (Paciente.telefono); Meta entrega 52XXXXXXXXXX (12) o
    5218110001001-style ocasionalmente con el '1' extra (13) -> se toman los
    últimos 10 dígitos para el match.
    """
    from .models import Paciente
    digits = ''.join(filter(str.isdigit, wa_id or ''))
    if len(digits) < 10:
        return None
    local = digits[-10:]
    return Paciente.objects.filter(telefono=local).first()


def enviar_template(telefono: str, nombre_template: str, parametros: list,
                    idioma: str = 'es_MX') -> dict:
    """
    Envía un template pre-aprobado por Meta.
    parametros: lista de strings en el orden de los {{N}} del template.
    idioma: debe ser el mismo con el que se aprobó en Meta; si el nombre o el
            idioma no coinciden, la API responde 132001.
    """
    numero = _normalizar_telefono(telefono)
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "template",
        "template": {
            "name": nombre_template,
            "language": {"code": idioma},
            "components": [{
                "type": "body",
                "parameters": [{"type": "text", "text": str(p)} for p in parametros]
            }]
        }
    }
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    response = requests.post(
        f"{WHATSAPP_API_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages",
        headers=headers,
        json=payload,
        timeout=10
    )
    return response.json()


def enviar_texto(telefono: str, texto: str) -> dict:
    """
    Envía un mensaje de texto libre (sin plantilla).

    Solo funciona dentro de la ventana de 24 h que abre una respuesta del
    contacto: fuera de ella Meta rechaza el mensaje (error 131047) y hay que
    usar una plantilla aprobada. Se usa para contestar en la bandeja de
    Mensajes Masivos.
    """
    payload = {
        "messaging_product": "whatsapp",
        "to": _normalizar_telefono(telefono),
        "type": "text",
        "text": {"body": texto},
    }
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        f"{WHATSAPP_API_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages",
        headers=headers,
        json=payload,
        timeout=10,
    )
    return response.json()


# --- Adjuntos (media) ---------------------------------------------------------
#
# Tipos que acepta la Cloud API, con sus MIME válidos y el tamaño máximo.
# 'document' admite cualquier MIME, por eso su set va vacío: es el cajón por
# defecto para lo que no sea imagen/video/audio.
#
# El límite de 'document' está en 25 MB a propósito, aunque Meta admite 100: el
# archivo sube primero a nuestro servidor y de ahí a Meta, y con el --timeout 120
# de gunicorn (ver start.sh) uno más grande no alcanza a completar el viaje.
# Cubre de sobra los PDF y presentaciones que se mandan a los alumnos.
MEDIA_TIPOS = {
    'image': {'mimes': {'image/jpeg', 'image/png'}, 'max_mb': 5, 'etiqueta': 'Imagen'},
    'video': {'mimes': {'video/mp4', 'video/3gpp'}, 'max_mb': 16, 'etiqueta': 'Video'},
    'audio': {'mimes': {'audio/aac', 'audio/mp4', 'audio/mpeg', 'audio/amr', 'audio/ogg'},
              'max_mb': 16, 'etiqueta': 'Audio'},
    'document': {'mimes': set(), 'max_mb': 25, 'etiqueta': 'Documento'},
}

# Meta solo deja poner texto junto al archivo en estos tipos; en audio y sticker
# el caption se ignora (o la API lo rechaza), así que se manda aparte.
MEDIA_ACEPTAN_CAPTION = {'image', 'video', 'document'}


def tipo_para_mime(mime: str) -> str:
    """MIME -> tipo de mensaje de la Cloud API. Lo desconocido va como documento."""
    mime = (mime or '').lower().split(';')[0].strip()
    for tipo, info in MEDIA_TIPOS.items():
        if mime in info['mimes']:
            return tipo
    return 'document'


def validar_media(tipo: str, tamano_bytes: int):
    """Devuelve un mensaje de error si el archivo no cumple, o None si está bien."""
    info = MEDIA_TIPOS.get(tipo)
    if not info:
        return f'Tipo de archivo no soportado por WhatsApp: {tipo}'
    limite = info['max_mb'] * 1024 * 1024
    if tamano_bytes > limite:
        return (f'{info["etiqueta"]} demasiado grande: {tamano_bytes / 1048576:.1f} MB. '
                f'WhatsApp acepta hasta {info["max_mb"]} MB.')
    if tamano_bytes == 0:
        return 'El archivo está vacío.'
    return None


def subir_media(archivo, nombre: str, mime: str) -> dict:
    """
    Sube el archivo a Meta y devuelve su respuesta ({'id': ...} si salió bien).

    La Cloud API no acepta binarios en el mensaje: primero se sube aquí, se
    obtiene un media_id y ese ID es el que viaja en el mensaje. Meta guarda el
    archivo 30 días.

    `archivo` puede ser bytes o un objeto con read(); aquí se normaliza a bytes
    a propósito. requests 2.34 decide si leer el objeto con un isinstance contra
    un Protocol, y esa comprobación usa inspect.getattr_static, que no dispara
    el __getattr__ con el que _TemporaryFileWrapper delega su read(). En Python
    3.13 (el de producción) eso hace que requests pase el objeto crudo a urllib3
    y reviente con "a bytes-like object is required, not '_TemporaryFileWrapper'"
    justo con los archivos grandes, que son los que Django guarda en disco.
    Pasando bytes se toma la primera rama de requests y el problema desaparece.
    """
    if hasattr(archivo, 'read'):
        if hasattr(archivo, 'seek'):
            archivo.seek(0)
        archivo = archivo.read()

    response = requests.post(
        f"{WHATSAPP_API_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/media",
        headers={"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"},
        data={"messaging_product": "whatsapp"},
        files={"file": (nombre, archivo, mime)},
        # Más generoso que los 10s del resto: aquí viaja el binario completo.
        timeout=90,
    )
    return response.json()


def enviar_media(telefono: str, tipo: str, media_id: str,
                 caption: str = '', nombre: str = '') -> dict:
    """
    Envía un adjunto ya subido a Meta.

    Igual que enviar_texto, es un mensaje de sesión: solo funciona dentro de la
    ventana de 24 h que abre la respuesta del contacto.
    """
    contenido = {"id": media_id}
    if caption and tipo in MEDIA_ACEPTAN_CAPTION:
        contenido["caption"] = caption
    if tipo == 'document' and nombre:
        # Sin filename WhatsApp muestra el documento con el media_id como nombre.
        contenido["filename"] = nombre

    payload = {
        "messaging_product": "whatsapp",
        "to": _normalizar_telefono(telefono),
        "type": tipo,
        tipo: contenido,
    }
    response = requests.post(
        f"{WHATSAPP_API_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages",
        headers={
            "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    return response.json()


def descargar_media(media_id: str):
    """
    Baja un adjunto de Meta. Devuelve (contenido_bytes, mime) o (None, error).

    Son dos llamadas: la primera cambia el media_id por una URL temporal, y esa
    URL exige el mismo token en el header (no es pública), por eso el archivo
    tiene que pasar por nuestro servidor y no se puede enlazar directo desde el
    navegador.
    """
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"}
    meta = requests.get(f"{WHATSAPP_API_URL}/{media_id}", headers=headers, timeout=15).json()

    url = meta.get('url')
    if not url:
        codigo, mensaje = extraer_error(meta)
        # Pasados 30 días Meta borra el archivo y este es el camino normal.
        return None, mensaje or f'Meta ya no tiene este archivo (código {codigo})'

    archivo = requests.get(url, headers=headers, timeout=60)
    if archivo.status_code != 200:
        return None, f'Meta respondió {archivo.status_code} al bajar el archivo'
    return archivo.content, meta.get('mime_type', 'application/octet-stream')


def buscar_contacto_academia_por_wa_id(wa_id: str):
    """
    Igual que buscar_paciente_por_wa_id pero contra ContactoAcademia: Meta
    entrega 52XXXXXXXXXX (12 dígitos) y la BD guarda 10, así que el match es
    por los últimos 10.
    """
    from .models import ContactoAcademia
    digits = ''.join(filter(str.isdigit, wa_id or ''))
    if len(digits) < 10:
        return None
    return ContactoAcademia.objects.filter(telefono=digits[-10:]).first()


# Frases con las que un contacto pide dejar de recibir campañas. Se comparan
# sin acentos y en mayúsculas (ver views._es_baja_campana). "No deseo recibir
# promociones" es el texto exacto del botón de opt-out de la plantilla.
FRASES_BAJA = [
    'NO DESEO RECIBIR',
    'DEJAR DE RECIBIR',
    'NO ME MANDEN',
    'NO ME ENVIEN',
    'DAR DE BAJA',
    'DARME DE BAJA',
    'BAJA',
    'STOP',
    'UNSUBSCRIBE',
]


def construir_parametros_cita(cita) -> dict:
    """
    Extrae los datos de una Cita para llenar los templates.
    Maneja FKs nullable (terapeuta, servicio, consultorio) sin romper el mensaje.
    """
    fecha = cita.fecha
    fecha_str = f"{DIAS_SEMANA[fecha.weekday()]}, {fecha.day} de {MESES[fecha.month - 1]}"

    # %I siempre da 2 dígitos ("02:00 pm"). Quitar SOLO el cero inicial si existe
    # (lstrip('0') es peligroso: en "00:30 am" borraría ambos ceros -> ":30 am")
    hora_str = cita.hora.strftime("%I:%M %p").lower()
    if hora_str.startswith('0'):
        hora_str = hora_str[1:]

    sucursal = cita.consultorio.get_sede_display() if cita.consultorio else "INTRA"
    terapeuta = cita.terapeuta.nombre if cita.terapeuta else "—"
    servicio = cita.servicio.nombre if cita.servicio else "—"

    sede = cita.consultorio.sede if cita.consultorio else None
    direccion = SEDE_DIRECCIONES.get(sede, SEDE_DIRECCIONES['republica'])

    monto = cita.costo
    if monto is None and cita.servicio:
        monto = cita.servicio.precio
    monto = monto if monto is not None else 0
    # Sin decimales si es un monto entero ("450" en vez de "450.00")
    monto_str = f"{int(monto)}" if monto == int(monto) else f"{monto:.2f}"

    return {
        "nombre_paciente": cita.paciente.nombre,
        "fecha":           fecha_str,
        "hora":            hora_str,
        "sucursal":        sucursal,
        "terapeuta":       terapeuta,
        "servicio":        servicio,
        "monto":           monto_str,
        "direccion":       direccion,
    }
