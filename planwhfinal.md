# Plan de Integración WhatsApp — ConsultorioWeb (Agenda Intra)
**Versión:** 1.0 (adaptada al código real)
**Basado en:** `planwh.md` (Junio 2025)
**Proyecto:** ConsultorioWeb — Django 5.2 / Railway
**App Django:** `clinica/`

---

## 0. Resumen de adaptaciones respecto al plan original

El plan original (`planwh.md`) está bien orientado (Meta Cloud API, todo dentro de Django, normalización de teléfono), pero asume nombres de campos y modelos que **no coinciden exactamente** con `clinica/models.py`. Esta tabla resume los ajustes necesarios antes de escribir código:

| Plan original asume | Realidad en ConsultorioWeb | Ajuste |
|---|---|---|
| `cita.hora_inicio` | `Cita.hora` (TimeField único) | Usar `cita.hora` |
| `cita.paciente.nombre_completo` | `Paciente.nombre` (no existe `nombre_completo`) | Usar `cita.paciente.nombre` |
| `cita.sucursal` | No existe. Hay `cita.consultorio` (FK a `Consultorio`, nullable) con `sede` (choices: república/morelos/colinas/trabajo_social/zoom/externo) | Usar `cita.consultorio.get_sede_display()` con fallback si es `None` |
| `cita.precio` | `Cita.costo` (DecimalField, nullable) | Usar `cita.costo`, con fallback a `cita.servicio.precio` |
| `ESTATUS_ACTIVOS = ['sin_confirmar', 'confirmada']` (placeholder) | Ya existe `Cita.ESTATUS_ACTIVOS = (CONFIRMADA, SIN_CONFIRMAR, INCIDENCIA)` | Reusar la constante del modelo, no redefinir |
| Encuesta "1 día después" filtra `estatus='confirmada'` | Una cita "de ayer" ya pasó; el estatus relevante es `ESTATUS_SI_ASISTIO` (`'si_asistio'`) | Filtrar por `Cita.ESTATUS_SI_ASISTIO` |
| `cita.fecha.strftime("%A, %d de %B")` | Los contenedores de Railway no tienen locale `es_MX` instalado → `strftime` con `%A`/`%B` devuelve nombres en inglés | Usar el mismo truco ya usado en `views.py` (listas `meses`/`dias_semana` en español hardcodeadas) |
| `paciente__telefono__isnull=False` | `Paciente.telefono` es `CharField` **sin** `null=True` (nunca es `NULL`, puede ser `''`) | Filtrar con `.exclude(paciente__telefono='')` |
| `cita.terapeuta`, `cita.servicio`, `cita.consultorio` siempre presentes | Las 3 FKs son `on_delete=SET_NULL, null=True` → pueden ser `None` | `construir_parametros_cita` debe manejar `None` explícitamente (si no, se imprime literalmente "None" en el mensaje) |
| Migración nueva sin número | Última migración existente: `0075_pregunta_titulo_grupo.py` | La nueva migración será `0076_...` |

Todo lo demás del plan original (Meta Cloud API en vez de OpenWA, todo dentro de Django, `api_key_required` ya existente, `requests` ya en `requirements.txt`, cron externo vía cron-job.org) es correcto y se mantiene sin cambios.

---

## 1. Contexto y decisiones previas (sin cambios)

### Por qué Meta Cloud API y no OpenWA
Se descarta `@open-wa/wa-automate` por el riesgo de ban del número de INTRA (reverse engineering de WhatsApp Web, sin SLA). Meta Cloud API es la vía oficial.

### Por qué todo vive dentro de Django
Confirmado en el código:
- `api_key_required` ya existe en `clinica/api_auth.py` (líneas 1-19) y funciona exactamente como lo describe el plan: permite sesión de navegador autenticada **o** header `X-API-Key` igual a `settings.DJANGO_API_KEY`.
- `requests==2.32.5` ya está en `requirements.txt` — no se necesita instalar nada nuevo.
- `clinica/services.py` y `clinica/services_instrumentos.py` establecen la convención: un módulo `services_*.py` con funciones puras, sin clases, que las vistas y comandos importan.
- `core/urls.py` es el único archivo de rutas (no hay `clinica/urls.py`), organizado por secciones con comentarios (`# API endpoints externos...`, `# Reagendos`, etc.). El webhook de Meta será una vista nueva en `clinica/views.py` (6103 líneas) + rutas en esa sección.

### Dato crítico — normalización de teléfono
`Paciente.telefono` (línea 410 de `models.py`) ya está etiquetado como `"Teléfono (WhatsApp)"`, confirmando que es el campo correcto. Se guarda como 10 dígitos locales (ej. `8110001001`). WhatsApp Cloud API espera `52XXXXXXXXXX`. La función `_normalizar_telefono` se implementa desde el día uno (necesaria para **enviar**, aunque el matching de respuestas entrantes quede para fases futuras).

---

## 2. Alcance de este plan (Fase 1) — sin cambios

| Feature | Tipo | Prioridad |
|---|---|---|
| Recordatorio 5 días antes | Automático + Manual | Alta |
| Recordatorio 3 días antes | Automático + Manual | Alta |
| Confirmación 1 día antes | Automático + Manual | Alta |
| Encuesta de conformidad 1 día después | Automático + Manual | Media |
| Envío a pacientes sin cita de seguimiento | Manual (con filtro de fechas) | Media |

---

## 3. Templates de mensajes (sin cambios — contenido aprobado por Meta)

Estos textos se registran tal cual en Meta Business Manager. La columna "Variables" indica el **orden** de los `{{N}}`, que debe coincidir con el orden que `construir_parametros_cita` devuelve en la sección 6.

### Template 1 — Recordatorio 5 días antes
**Nombre:** `recordatorio_cita_5_dias` · **Categoría:** `UTILITY`
```
Hola {{1}}, te recordamos que tienes una cita programada el {{2}} a las {{3}} en el consultorio de {{4}}.

Tu cita es con: {{5}}
Servicio: {{6}}

Ante cualquier cambio o duda, no dudes en contactarnos. ¡Te esperamos!
```
*Variables: nombre_paciente, fecha, hora, sucursal, terapeuta, servicio*
*Botón: Llamar a un número de teléfono → `+52 844 443 9987` · Texto: "Cambio o duda"*

---

### Template 2 — Recordatorio 3 días antes
**Nombre:** `recordatorio_cita_3_dias` · **Categoría:** `UTILITY`
```
Hola {{1}}, te recordamos que en 3 días tienes una cita con nosotros.

📅 {{2}} a las {{3}}
📍 Consultorio {{4}}
👨‍⚕️ {{5}}
🏥 Servicio: {{6}}

¡Te esperamos puntualmente!
```
*Variables: nombre_paciente, fecha, hora, sucursal, terapeuta, servicio*
*Botón: Llamar a un número de teléfono → `+52 844 443 9987` · Texto: "Cambio o duda"*

---

### Template 3 — Confirmación 1 día antes
**Nombre:** `confirmacion_cita_1_dia` · **Categoría:** `UTILITY`
```
Buenas tardes, confirmamos su cita el {{1}} a las {{2}}, consultorio {{3}}.

Profesional: {{4}}
Paciente: {{5}}
Servicio: {{6}}

Por favor llegue puntual; no podremos reprogramar ni extender el tiempo.

Costo: ${{7}}. ¿Pagará por transferencia, efectivo o tarjeta?

Transferencia:
🏦 Banco: BBVA
💳 Tarjeta: 4555 1130 1572 4679
👤 Titular: Miriam Rubí Iracheta

{{8}}

Para cambios o dudas, escríbanos al 844 443 9987.
```
*Variables: fecha_completa, hora, sucursal, terapeuta, nombre_paciente, servicio, monto, direccion* (415 caracteres, límite de Meta: 550)

`direccion` varía según `cita.consultorio.sede` (ver `SEDE_DIRECCIONES` en `services_whatsapp.py`): cada sede (República, Morelos, Colinas, Trabajo Social, Zoom, Externo) tiene su propio texto de ubicación o instrucciones de acceso.

*Sin botón: el número de WhatsApp ya queda como texto plano (tap-to-message nativo en WhatsApp), no se necesita botón de llamada en esta plantilla.*

---

### Template 4 — Encuesta de conformidad (1 día después)
**Nombre:** `encuesta_conformidad` · **Categoría:** `UTILITY`
```
Hola {{1}}, esperamos que tu sesión de {{2}} con {{3}} haya sido de gran beneficio para ti.

Nos gustaría conocer tu experiencia. ¿Cómo calificarías tu atención del 1 al 5?

1️⃣ Muy mala
2️⃣ Mala
3️⃣ Regular
4️⃣ Buena
5️⃣ Excelente

Tu opinión nos ayuda a mejorar. ¡Gracias!
```
*Variables: nombre_paciente, servicio, terapeuta*

---

### Template 5 — Reactivación pacientes sin seguimiento
**Nombre:** `reactivacion_paciente` · **Categoría:** `MARKETING`
```
Hola {{1}}, hace un tiempo que no nos visitas y queremos saber cómo estás.

En {{2}} seguimos disponibles para apoyarte en tu bienestar. Si deseas retomar tu proceso o agendar una nueva cita, con gusto te atendemos.

Comunícate con nosotros o escríbenos aquí. ¡Te esperamos! 🌿
```
*Variables: nombre_paciente, nombre_clinica (fijo: "INTRA")*
*Botón: Llamar a un número de teléfono → `+52 844 443 9987` · Texto: "Cambio o duda"*

---

## 4. Arquitectura de archivos (sin cambios)

```
clinica/
├── services_whatsapp.py              ← cliente Meta Cloud API (NUEVO)
├── views.py                           ← + vista webhook + vistas de disparo manual + vista "sin seguimiento"
├── models.py                          ← + campos Cita.recordatorio_*_enviado_en + modelo MensajeWhatsApp
├── migrations/0076_whatsapp_*.py      ← NUEVO
└── management/
    └── commands/
        └── enviar_recordatorios_whatsapp.py   ← comando cron (NUEVO)

core/
├── settings.py                        ← + variables WHATSAPP_*
└── urls.py                            ← + rutas nuevas (sección "WhatsApp")
```

---

## 5. Modelos — migración `0076`

### Campos nuevos en `Cita`

```python
recordatorio_5d_enviado_en = models.DateTimeField(null=True, blank=True)
recordatorio_3d_enviado_en = models.DateTimeField(null=True, blank=True)
recordatorio_1d_enviado_en = models.DateTimeField(null=True, blank=True)
encuesta_enviada_en        = models.DateTimeField(null=True, blank=True)
```

### Modelo nuevo: `MensajeWhatsApp` (log de auditoría)

```python
class MensajeWhatsApp(models.Model):
    TIPO_CHOICES = [
        ('recordatorio_5d', 'Recordatorio 5 días'),
        ('recordatorio_3d', 'Recordatorio 3 días'),
        ('confirmacion_1d', 'Confirmación 1 día'),
        ('encuesta',        'Encuesta conformidad'),
        ('reactivacion',    'Reactivación seguimiento'),
    ]
    ORIGEN_CHOICES = [
        ('automatico', 'Automático'),
        ('manual',     'Manual'),
    ]
    cita          = models.ForeignKey('Cita', null=True, blank=True, on_delete=models.SET_NULL,
                                       related_name='mensajes_whatsapp')
    paciente      = models.ForeignKey('Paciente', on_delete=models.CASCADE,
                                       related_name='mensajes_whatsapp')
    telefono      = models.CharField(max_length=20)
    tipo          = models.CharField(max_length=20, choices=TIPO_CHOICES)
    origen        = models.CharField(max_length=10, choices=ORIGEN_CHOICES, default='automatico')
    enviado_en    = models.DateTimeField(auto_now_add=True)
    exitoso       = models.BooleanField(default=False)
    respuesta_api = models.JSONField(null=True, blank=True)
    enviado_por   = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name = 'Mensaje WhatsApp'
        verbose_name_plural = 'Mensajes WhatsApp'
        ordering = ['-enviado_en']
```

> **Por qué loguear siempre:** sin este registro, un template rechazado por Meta o un número inválido pasan inadvertidos. `related_name='mensajes_whatsapp'` permite mostrar el historial de envíos directamente en `detalle_paciente.html` (`paciente.mensajes_whatsapp.all`).

`DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'` (línea 132 de `settings.py`) ya aplica automáticamente — no hace falta declarar el `id`.

Dependencia de la migración: `('clinica', '0075_pregunta_titulo_grupo')`.

---

## 6. `clinica/services_whatsapp.py`

```python
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
```

**Notas de adaptación:**
- Las listas `MESES` / `DIAS_SEMANA` reproducen el mismo truco que ya usa `views.py` (ej. líneas 2388, 2422) para evitar depender del locale `es_MX` del sistema operativo, que no está instalado en el contenedor de Railway.
- `construir_parametros_cita` ya no depende de `hasattr` (que en el plan original siempre era `False` para campos inexistentes como `sucursal`/`precio`); ahora resuelve directamente contra los campos reales y sus `None` posibles.
- `hora_str` quita como máximo **un** cero inicial con slicing, no con `.lstrip('0')` (que borraría todos los ceros consecutivos — relevante si alguna vez se formatea una hora distinta a `%I`, que sí puede traer "00").
- `monto_str` omite los decimales cuando el monto es entero (`450` en vez de `450.00`), igual que el `str(int(cita.precio))` del plan original, pero sin perder centavos si algún servicio los tiene.

---

## 7. `management/commands/enviar_recordatorios_whatsapp.py`

```python
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from clinica.models import Cita, MensajeWhatsApp
from clinica import services_whatsapp as wa


class Command(BaseCommand):
    help = 'Envía recordatorios y encuestas de citas por WhatsApp'

    def handle(self, *args, **options):
        hoy = timezone.localdate()

        # --- Recordatorio 5 días ---
        for cita in self._citas_activas(hoy + timedelta(days=5)).filter(
                recordatorio_5d_enviado_en__isnull=True):
            self._enviar(cita, 'recordatorio_5d', 'recordatorio_cita_5_dias',
                lambda d: [d['nombre_paciente'], d['fecha'], d['hora'],
                           d['sucursal'], d['terapeuta'], d['servicio']])

        # --- Recordatorio 3 días ---
        for cita in self._citas_activas(hoy + timedelta(days=3)).filter(
                recordatorio_3d_enviado_en__isnull=True):
            self._enviar(cita, 'recordatorio_3d', 'recordatorio_cita_3_dias',
                lambda d: [d['nombre_paciente'], d['fecha'], d['hora'],
                           d['sucursal'], d['terapeuta'], d['servicio']])

        # --- Confirmación 1 día antes ---
        for cita in self._citas_activas(hoy + timedelta(days=1)).filter(
                recordatorio_1d_enviado_en__isnull=True):
            self._enviar(cita, 'confirmacion_1d', 'confirmacion_cita_1_dia',
                lambda d: [d['fecha'], d['hora'], d['sucursal'], d['terapeuta'],
                           d['nombre_paciente'], d['servicio'], d['monto']])

        # --- Encuesta 1 día después (solo a quien SÍ asistió) ---
        fecha_ayer = hoy - timedelta(days=1)
        citas_ayer = Cita.objects.filter(
            fecha=fecha_ayer,
            estatus=Cita.ESTATUS_SI_ASISTIO,
            encuesta_enviada_en__isnull=True,
        ).exclude(paciente__telefono='').select_related('paciente', 'terapeuta', 'servicio', 'consultorio')

        for cita in citas_ayer:
            self._enviar(cita, 'encuesta', 'encuesta_conformidad',
                lambda d: [d['nombre_paciente'], d['servicio'], d['terapeuta']])

        self.stdout.write(self.style.SUCCESS('Recordatorios enviados correctamente.'))

    def _citas_activas(self, fecha):
        return Cita.objects.filter(
            fecha=fecha,
            estatus__in=Cita.ESTATUS_ACTIVOS,
        ).exclude(paciente__telefono='').select_related('paciente', 'terapeuta', 'servicio', 'consultorio')

    def _enviar(self, cita, tipo, nombre_template, get_params):
        datos = wa.construir_parametros_cita(cita)
        try:
            resp = wa.enviar_template(cita.paciente.telefono, nombre_template, get_params(datos))
            exitoso = 'messages' in resp
        except Exception as e:
            resp = {'error': str(e)}
            exitoso = False

        campo = {
            'recordatorio_5d': 'recordatorio_5d_enviado_en',
            'recordatorio_3d': 'recordatorio_3d_enviado_en',
            'confirmacion_1d': 'recordatorio_1d_enviado_en',
            'encuesta':        'encuesta_enviada_en',
        }[tipo]
        setattr(cita, campo, timezone.now())
        cita.save(update_fields=[campo])

        MensajeWhatsApp.objects.create(
            cita=cita,
            paciente=cita.paciente,
            telefono=cita.paciente.telefono,
            tipo=tipo,
            origen='automatico',
            exitoso=exitoso,
            respuesta_api=resp,
        )
```

**Notas de adaptación:**
- `Cita.ESTATUS_ACTIVOS` y `Cita.ESTATUS_SI_ASISTIO` son constantes que **ya existen** en `models.py` (líneas 530-552) — se reutilizan en vez de redefinir una lista de strings sueltos.
- `.exclude(paciente__telefono='')` sustituye al `paciente__telefono__isnull=False` del plan original, porque `telefono` es `CharField` sin `null=True` (nunca es `NULL`, pero sí puede estar vacío en registros legacy).
- La encuesta usa `ESTATUS_SI_ASISTIO` en vez de `'confirmada'`: una cita "de ayer" que sigue en `confirmada` normalmente significa que nadie cerró el checkout; lo correcto es encuestar solo a quien efectivamente asistió.

---

## 8. Vistas — disparo manual

```python
# clinica/views.py — agregar estas vistas

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import json
from . import services_whatsapp as wa
from .models import Cita, MensajeWhatsApp, Paciente
from .api_auth import api_key_required


MAP_WHATSAPP_MANUAL = {
    'recordatorio_5d': ('recordatorio_cita_5_dias',
        lambda d: [d['nombre_paciente'], d['fecha'], d['hora'],
                   d['sucursal'], d['terapeuta'], d['servicio']]),
    'recordatorio_3d': ('recordatorio_cita_3_dias',
        lambda d: [d['nombre_paciente'], d['fecha'], d['hora'],
                   d['sucursal'], d['terapeuta'], d['servicio']]),
    'confirmacion_1d': ('confirmacion_cita_1_dia',
        lambda d: [d['fecha'], d['hora'], d['sucursal'], d['terapeuta'],
                   d['nombre_paciente'], d['servicio'], d['monto']]),
    'encuesta':        ('encuesta_conformidad',
        lambda d: [d['nombre_paciente'], d['servicio'], d['terapeuta']]),
}


@login_required
@require_POST
def whatsapp_enviar_manual(request, cita_id, tipo):
    """
    Botón manual en la ficha de cita (editar_cita.html):
    tipo: recordatorio_5d | recordatorio_3d | confirmacion_1d | encuesta
    """
    if tipo not in MAP_WHATSAPP_MANUAL:
        return JsonResponse({'error': 'Tipo inválido'}, status=400)

    cita = Cita.objects.select_related('paciente', 'terapeuta', 'servicio', 'consultorio').get(pk=cita_id)
    if not cita.paciente.telefono:
        return JsonResponse({'error': 'El paciente no tiene teléfono registrado'}, status=400)

    nombre_template, get_params = MAP_WHATSAPP_MANUAL[tipo]
    datos = wa.construir_parametros_cita(cita)

    try:
        resp = wa.enviar_template(cita.paciente.telefono, nombre_template, get_params(datos))
        exitoso = 'messages' in resp
    except Exception as e:
        resp = {'error': str(e)}
        exitoso = False

    MensajeWhatsApp.objects.create(
        cita=cita,
        paciente=cita.paciente,
        telefono=cita.paciente.telefono,
        tipo=tipo,
        origen='manual',
        exitoso=exitoso,
        respuesta_api=resp,
        enviado_por=request.user
    )
    return JsonResponse({'ok': exitoso, 'meta_response': resp})


@login_required
@require_POST
def whatsapp_reactivacion_seguimiento(request):
    """
    Botón en la vista de pacientes sin seguimiento (sección 9).
    Body JSON: { "paciente_ids": [1, 2, 3] }
    """
    data = json.loads(request.body)
    ids = data.get('paciente_ids', [])
    pacientes = Paciente.objects.filter(pk__in=ids).exclude(telefono='')

    resultados = []
    for paciente in pacientes:
        try:
            resp = wa.enviar_template(
                paciente.telefono,
                'reactivacion_paciente',
                [paciente.nombre, 'INTRA']
            )
            exitoso = 'messages' in resp
        except Exception as e:
            resp = {'error': str(e)}
            exitoso = False

        MensajeWhatsApp.objects.create(
            paciente=paciente,
            telefono=paciente.telefono,
            tipo='reactivacion',
            origen='manual',
            exitoso=exitoso,
            respuesta_api=resp,
            enviado_por=request.user
        )
        resultados.append({'paciente_id': paciente.pk, 'ok': exitoso})

    return JsonResponse({'resultados': resultados})
```

**Dónde colocar el botón manual:** `clinica/templates/clinica/editar_cita.html` tiene un bloque de acciones en las líneas 103-117 (`Borrar Cita` / `Cancelar` / `Guardar Cambios`). Ahí se agrega un grupo de botones (dropdown "Enviar WhatsApp ▾" con las 4 opciones) que hace `fetch(POST)` a `whatsapp_enviar_manual` con `cita.id` y el `tipo`, mostrando un toast con el resultado (`ok`/`meta_response`).

---

## 9. Vista nueva — Pacientes sin cita de seguimiento

El plan original asume que ya existe una vista "pacientes sin seguimiento con filtro de fechas", pero **no existe en el código actual** (`lista_pacientes` en `views.py:738` no tiene ese filtro). Hay que crearla.

```python
# clinica/views.py

from datetime import datetime
from django.utils import timezone

@login_required
def pacientes_sin_seguimiento(request):
    """
    Pacientes cuya última cita con ESTATUS_SI_ASISTIO fue antes de `desde`
    y que no tienen ninguna cita futura activa.
    Filtro vía querystring: ?desde=YYYY-MM-DD&hasta=YYYY-MM-DD
    """
    hoy = timezone.localdate()
    desde_str = request.GET.get('desde')
    hasta_str = request.GET.get('hasta')
    desde = datetime.strptime(desde_str, '%Y-%m-%d').date() if desde_str else None
    hasta = datetime.strptime(hasta_str, '%Y-%m-%d').date() if hasta_str else hoy

    pacientes_con_cita_futura = Cita.objects.filter(
        fecha__gte=hoy,
        estatus__in=Cita.ESTATUS_ACTIVOS,
    ).values_list('paciente_id', flat=True)

    qs = Paciente.objects.exclude(telefono='').exclude(pk__in=pacientes_con_cita_futura)

    # Anotar última cita asistida por paciente
    from django.db.models import Max
    qs = qs.annotate(
        ultima_asistencia=Max('citas__fecha', filter=models.Q(citas__estatus=Cita.ESTATUS_SI_ASISTIO))
    ).filter(ultima_asistencia__isnull=False, ultima_asistencia__lte=hasta)

    if desde:
        qs = qs.filter(ultima_asistencia__gte=desde)

    return render(request, 'clinica/pacientes_sin_seguimiento.html', {
        'pacientes': qs.order_by('-ultima_asistencia'),
        'desde': desde_str or '',
        'hasta': hasta_str or hoy.isoformat(),
    })
```

> Notas:
> - Requiere `from django.db import models` (ya importado en `views.py`) para `models.Q`.
> - `Max('citas__fecha', ...)` depende de que `Cita.paciente` tenga `related_name='citas'` — **verificado**: `models.py:573` lo declara así (`paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='citas')`), por lo que la query funciona tal cual.

El template `pacientes_sin_seguimiento.html` lista pacientes con: nombre, teléfono, fecha de última asistencia, checkbox de selección y un botón "Enviar reactivación" que llama a `whatsapp_reactivacion_seguimiento` con los `paciente_ids` marcados.

---

## 10. Verificación de Webhook (Meta handshake) — sin cambios

```python
# clinica/views.py

@csrf_exempt
def whatsapp_webhook(request):
    """
    GET:  verificación inicial de Meta (handshake)
    POST: mensajes entrantes (reservado para fases futuras)
    """
    if request.method == 'GET':
        mode      = request.GET.get('hub.mode')
        token     = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        if mode == 'subscribe' and token == settings.WHATSAPP_VERIFY_TOKEN:
            return HttpResponse(challenge, content_type='text/plain')
        return HttpResponse(status=403)

    if request.method == 'POST':
        return HttpResponse(status=200)
```

---

## 11. Variables de entorno

### Railway (panel de variables)
```env
WHATSAPP_TOKEN=<token de acceso permanente de Meta>
WHATSAPP_PHONE_NUMBER_ID=<ID del número en Meta for Developers>
WHATSAPP_VERIFY_TOKEN=<string que tú defines, ej: intra_verify_2026>
WHATSAPP_BUSINESS_ACCOUNT_ID=<ID de la cuenta de negocio>
```

### `core/settings.py` — agregar junto a `DJANGO_API_KEY` (línea 149), siguiendo el patrón `os.environ.get` ya usado en el archivo:
```python
WHATSAPP_TOKEN = os.environ.get('WHATSAPP_TOKEN', '')
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', '')
WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN', '')
WHATSAPP_BUSINESS_ACCOUNT_ID = os.environ.get('WHATSAPP_BUSINESS_ACCOUNT_ID', '')
```

---

## 12. Cron — sin costo adicional en Railway (sin cambios)

`start.sh` solo levanta `gunicorn` (no hay proceso `worker`/cron actualmente), así que se mantiene la propuesta de **cron-job.org** (gratuito):

```
URL:    https://tu-app.railway.app/api/whatsapp/trigger-cron/
Método: POST
Header: X-API-Key: <DJANGO_API_KEY>
Schedule: 0 8 * * *   (cada día a las 8am, hora de Monterrey — TIME_ZONE ya está en 'America/Monterrey')
```

```python
@api_key_required  # decorador existente en clinica/api_auth.py, sin modificar
@require_POST
def whatsapp_trigger_cron(request):
    from django.core import management
    management.call_command('enviar_recordatorios_whatsapp')
    return JsonResponse({'ok': True})
```

---

## 13. URLs nuevas — `core/urls.py`

Agregar como nueva sección, siguiendo el estilo de agrupación por comentarios ya usado en el archivo (junto a `# Notificaciones terapeuta` / `# API endpoints externos`):

```python
    # WhatsApp
    path('api/whatsapp/webhook/',
         clinica_views.whatsapp_webhook,             name='whatsapp_webhook'),
    path('api/whatsapp/trigger-cron/',
         clinica_views.whatsapp_trigger_cron,        name='whatsapp_trigger_cron'),
    path('api/whatsapp/manual/<int:cita_id>/<str:tipo>/',
         clinica_views.whatsapp_enviar_manual,       name='whatsapp_manual'),
    path('api/whatsapp/reactivacion/',
         clinica_views.whatsapp_reactivacion_seguimiento, name='whatsapp_reactivacion'),
    path('pacientes/sin-seguimiento/',
         clinica_views.pacientes_sin_seguimiento,    name='pacientes_sin_seguimiento'),
```

---

## 14. Checklist de implementación

### Setup externo (Meta — antes de escribir código)
- [ ] Crear las 5 plantillas en Meta Business Manager (sección 3)
- [ ] Esperar aprobación de Meta (24–48 horas)
- [ ] Obtener `WHATSAPP_TOKEN` (permanente, no el temporal de 24h)
- [ ] Anotar `WHATSAPP_PHONE_NUMBER_ID` y `WHATSAPP_BUSINESS_ACCOUNT_ID`
- [ ] Confirmar número dedicado (no puede estar activo en la app de WhatsApp simultáneamente)

### Código
- [ ] Crear `clinica/services_whatsapp.py` (sección 6)
- [ ] Migración `0076`: campos `Cita.recordatorio_*_enviado_en` + modelo `MensajeWhatsApp` (sección 5)
- [ ] Crear `management/commands/enviar_recordatorios_whatsapp.py` (sección 7)
- [ ] Agregar vistas `whatsapp_enviar_manual`, `whatsapp_reactivacion_seguimiento`, `whatsapp_webhook`, `whatsapp_trigger_cron`, `pacientes_sin_seguimiento` en `views.py`
- [ ] Crear template `pacientes_sin_seguimiento.html` (sección 9)
- [ ] Agregar botón "Enviar WhatsApp ▾" en `editar_cita.html` (líneas ~103-117)
- [ ] Registrar URLs en `core/urls.py` (sección 13)
- [ ] Agregar `WHATSAPP_*` a `core/settings.py` (sección 11)
- [ ] Variables de entorno en Railway

### Deploy y verificación
- [ ] Deploy en Railway
- [ ] Registrar webhook URL en panel de Meta (`/api/whatsapp/webhook/`)
- [ ] Verificar handshake (Meta hace GET inmediatamente)
- [ ] Configurar cron en cron-job.org
- [ ] Prueba manual con número propio antes de mandar a pacientes reales
- [ ] Verificar log `MensajeWhatsApp` desde Django Admin (registrar el modelo en `clinica/admin.py`)
- [ ] Probar `construir_parametros_cita` con una `Cita` que tenga `terapeuta=None`, `servicio=None` o `consultorio=None` para confirmar que no aparece "None" en el mensaje

---

## 15. Lo que queda fuera de este plan (Fases futuras) — sin cambios

- **Auto-agendamiento conversacional** — state machine con `ConversacionWhatsApp`
- **Respuestas automáticas del bot** — "SI/NO" actualiza estatus de cita (aquí sí aplicará la normalización de teléfono para *matching* del `wa_id` entrante contra `Paciente.telefono`)
- **Panel de promos** — campañas masivas de categoría MARKETING
- **Opt-in explícito** — campo `Paciente.whatsapp_optin`

---

*Documento adaptado para uso interno de desarrollo — Órbita × INTRA*
