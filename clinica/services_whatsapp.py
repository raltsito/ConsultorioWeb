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
    }
