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

# Cuerpo literal de cada template aprobado en Meta (ver planwhfinal.md secciones 3-5).
# Meta no devuelve el texto renderizado en la respuesta del API, así que se
# reconstruye aquí para poder mostrarlo en el panel de chat (MensajeWhatsApp.texto).
# Si se edita un template en Meta Business Manager, hay que actualizar esto también.
TEMPLATE_BODIES = {
    'recordatorio_cita_5_dias':
        'Hola {{1}}, te recordamos que tienes una cita programada el {{2}} a las {{3}} '
        'en el consultorio de {{4}}.\n\n'
        'Tu cita es con: {{5}}\nServicio: {{6}}\n\n'
        'Ante cualquier cambio o duda, no dudes en contactarnos. ¡Te esperamos!',
    'recordatorio_cita_3_dias':
        'Hola {{1}}, te recordamos que en 3 días tienes una cita con nosotros.\n\n'
        '📅 {{2}} a las {{3}}\n📍 Consultorio {{4}}\n👨‍⚕️ {{5}}\n🏥 Servicio: {{6}}\n\n'
        '¡Te esperamos puntualmente!',
    'confirmacion_cita_1_dia':
        'Buenas tardes, confirmamos su cita el {{1}} a las {{2}}, consultorio {{3}}.\n\n'
        'Profesional: {{4}}\nPaciente: {{5}}\nServicio: {{6}}\n\n'
        'Por favor llegue puntual; no podremos reprogramar ni extender el tiempo.\n\n'
        'Costo: ${{7}}. ¿Pagará por transferencia, efectivo o tarjeta?\n\n'
        'Transferencia:\n🏦 Banco: BBVA\n💳 Tarjeta: 4555 1130 1572 4679\n👤 Titular: Miriam Rubí Iracheta\n\n'
        '{{8}}\n\nResponda *CONFIRMO* a este mensaje para confirmar su cita.\n\n'
        'Para cambios o dudas, escríbanos al 844 443 9987.',
    'encuesta_conformidad':
        'Hola {{1}}, esperamos que tu sesión de {{2}} con {{3}} haya sido de gran beneficio para ti.\n\n'
        'Nos gustaría conocer tu experiencia. ¿Cómo calificarías tu atención del 1 al 5?\n\n'
        '1️⃣ Muy mala\n2️⃣ Mala\n3️⃣ Regular\n4️⃣ Buena\n5️⃣ Excelente\n\n'
        'Tu opinión nos ayuda a mejorar. ¡Gracias!',
    'reactivacion_paciente':
        'Hola {{1}}, hace un tiempo que no nos visitas y queremos saber cómo estás.\n\n'
        'En {{2}} seguimos disponibles para apoyarte en tu bienestar. Si deseas retomar tu '
        'proceso o agendar una nueva cita, con gusto te atendemos.\n\n'
        'Comunícate con nosotros o escríbenos aquí. ¡Te esperamos! 🌿',

    # --- Plantillas de DEMO para prospectos (panel exclusivo SUPERADMIN) ---
    'recordatorio_pago_3_dias':
        'Hola {{1}}, te recordamos que en 3 días vence tu mensualidad en la Escuela de '
        'Enfermería Dorothea 🩺\n\n'
        '📅 Fecha de vencimiento: {{2}}\n💳 Monto: ${{3}}\n\n'
        '🏪 Pago en OXXO: menciona la referencia DEMO-12345 en cualquier tienda\n\n'
        'Si ya realizaste tu pago, ignora este mensaje.\n\n'
        '¡Gracias por formar parte de Dorothea!',
    'recordatorio_pago_mismo_dia':
        'Hola {{1}}, hoy {{2}} vence tu mensualidad en la Escuela de Enfermería Dorothea 🩺\n\n'
        '💳 Monto a pagar: ${{3}}\n\n'
        '🏪 Pago en OXXO: menciona la referencia DEMO-12345 en cualquier tienda\n\n'
        'Te recordamos realizar tu pago hoy para mantener tu acceso a clases y evitar recargos.\n\n'
        '¡Gracias por tu compromiso con tu formación! 🩺',
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
                'clave': 'recordatorio_pago_mismo_dia',
                'titulo': 'Recordatorio de pago — mismo día',
                'campos': ['nombre', 'fecha_vencimiento', 'monto'],
            },
        ],
    },
}

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


def enviar_template(telefono: str, nombre_template: str, parametros: list) -> dict:
    """
    Envía un template pre-aprobado por Meta.
    parametros: lista de strings en el orden de los {{N}} del template.
    """
    numero = _normalizar_telefono(telefono)
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "template",
        "template": {
            "name": nombre_template,
            "language": {"code": "es_MX"},
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
