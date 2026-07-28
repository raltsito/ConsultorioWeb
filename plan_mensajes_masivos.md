# Plan — Mensajes Masivos (Portal Dirección Comercial)

Campaña de WhatsApp a la base de alumnos de Academia (`bddo.xlsx`), enviada con
la plantilla de Meta y con bandeja para leer las respuestas.

Vista base ya creada: `/portal-direccion-comercial/mensajes-masivos/`
(`clinica/views.py:mensajes_masivos_direccion_comercial`, plantilla
`clinica/templates/clinica/mensajes_masivos_direccion_comercial.html`).

---

## 0. Lo que ya existe en el proyecto (se reutiliza)

| Pieza | Ubicación | Uso en este módulo |
|---|---|---|
| Cliente Cloud API | `clinica/services_whatsapp.py` | `enviar_template()` y `_normalizar_telefono()` sirven tal cual |
| Cuerpos de plantillas | `services_whatsapp.py:TEMPLATE_BODIES` | se agrega el body nuevo para poder mostrarlo en el panel |
| Webhook de Meta | `clinica/views.py:6892 whatsapp_webhook` | ya recibe respuestas; hay que extenderlo |
| Modelo de entrantes | `MensajeWhatsAppEntrante` (`models.py:815`) | las respuestas de los alumnos **ya se guardan** ahí, solo que sin poder asociarlas a nadie (`paciente` queda `NULL`) |
| Envío por lotes desde el front | `demos_whatsapp_enviar_lote` (`views.py:7220`) | mismo patrón AJAX, es el modelo a copiar |
| Credenciales | `core/settings.py:152-155` | `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN` ya configuradas |
| `openpyxl` | `requirements.txt` | leer el Excel, sin dependencias nuevas |

Lo que **no** existe y hay que construir: modelo de contactos de Academia,
modelo de campaña/envío, procesamiento de `statuses` en el webhook, y envío de
texto libre (`services_whatsapp.py` hoy solo sabe mandar plantillas).

No hay Celery, RQ ni django-q en el proyecto (verificado). Eso condiciona el
diseño del envío — ver Fase 3.

---

## 1. Los datos: `C:\Users\carlo\Downloads\bddo.xlsx`

Hoja única `Inscripciones detalladas`, encabezados en la **fila 3**, datos desde
la fila 4. Columnas:

`Año fuente · Diplomado · Nombre · Teléfono · Correo · Fecha inscripción · Matrícula · Estatus origen · Observaciones origen · Fila en archivo original`

Números reales:

- **316 filas** con nombre.
- Estatus: **192 Activo · 123 Inactivo · 1 Por confirmar**.
- Año: 198 de 2025, 118 de 2026.
- 21 diplomados distintos (DBT 65, Tanatología 3ra 30, TCC 8va virtual 23, …).
- Teléfonos: **288 con 10 dígitos, 2 con 11, 26 vacíos**.
- **248 teléfonos únicos** → hay ~40 filas que repiten persona (mismo alumno
  inscrito en varios diplomados).

⚠️ **Los duplicados importan**: si se envía por fila, ~40 personas reciben el
mismo mensaje 2 o 3 veces. Eso es spam, cuesta el doble y castiga el *quality
rating* del número. El diseño de abajo deduplica por teléfono.

⚠️ **248 destinatarios únicos vs. el límite de Meta**: si el WABA no está
verificado, el tope es **250 destinatarios únicos por 24 h**. Estamos a 2 de
tocarlo. Hay que confirmar el tier antes de disparar (Fase 2).

---

## 2. Fase 0 — Trabajo en Meta (bloqueante, fuera del código)

### 2.1 Crear la plantilla

En WhatsApp Manager → Plantillas de mensajes:

- **Nombre:** `promo_diplomado_psicoterapia_infantil`
- **Categoría:** `MARKETING` (obligatorio; no califica como UTILITY)
- **Idioma:** `es_MX` (es el que usa `enviar_template()`)
- **Body:** el texto tal cual — **604 caracteres**, dentro del límite de 1024. ✅
  Los saltos de línea sí se permiten en el body (la restricción de `\n` del
  código aplica solo a los *parámetros*, error 132018).

**Decisión pendiente — ¿variables o texto fijo?**
Recomiendo **cero variables**: el texto que diste no tiene hueco natural para el
nombre, aprobar es más rápido, y con 290 envíos no hay riesgo de parámetro vacío.
Si prefieres personalizar, la alternativa es anteponer `Hola {{1}}, ` y llenarlo
con `ContactoAcademia.nombre` (Meta no permite que el body *empiece* con la
variable, por eso el "Hola" delante).

**Botón de baja (recomendado):** agregar un *Quick Reply* con texto
`No deseo recibir promociones`. Meta pondera el opt-out en la calidad de las
plantillas de marketing, y nos deja capturar la baja por webhook (Fase 4.3).

### 2.2 Verificaciones antes de disparar

1. **Tier de mensajería** (WhatsApp Manager → Insights): 250 / 1K / 10K / …
   Con 248 destinatarios, si sale 250 hay que partir el envío en dos días o
   verificar el negocio primero.
2. **¿Mismo número que los recordatorios de pacientes?** Si `WHATSAPP_PHONE_NUMBER_ID`
   es el mismo que manda confirmaciones de citas de INTRA, una campaña de
   marketing con bloqueos o reportes puede bajar el quality rating y degradar
   los recordatorios operativos. Vale la pena evaluar un número aparte para
   Academia.
3. **Saldo / método de pago** del WABA: las conversaciones de marketing se cobran.

---

## 3. Fase 1 — Modelos y carga del Excel

Migración nueva (siguiente a `0094_seed_benja_administrativo`).

```
ContactoAcademia
  telefono        CharField(10)  unique, index   # normalizado a 10 dígitos
  nombre          CharField(200)
  correo          EmailField(blank)
  suscrito        BooleanField(default=True)     # False = pidió baja
  creado_en / actualizado_en

InscripcionAcademia            # N por contacto — resuelve los duplicados
  contacto        FK -> ContactoAcademia
  diplomado       CharField(120)
  anio_fuente     IntegerField
  estatus         CharField  (activo | inactivo | por_confirmar)
  matricula       CharField(blank)
  observaciones   TextField(blank)
  fila_origen     IntegerField(null)

CampanaMasiva
  nombre          CharField(150)
  plantilla_meta  CharField(120)                 # promo_diplomado_psicoterapia_infantil
  idioma          CharField(10, default='es_MX')
  texto_render    TextField                      # copia del body al momento del envío
  estado          CharField (borrador | enviando | enviada | pausada)
  creada_por      FK -> User
  creada_en

EnvioMasivo
  campana         FK -> CampanaMasiva
  contacto        FK -> ContactoAcademia
  telefono        CharField(20)
  wa_message_id   CharField(100, index, blank)   # correlación con statuses
  estado          CharField (pendiente | enviado | entregado | leido | fallido)
  error_codigo    CharField(20, blank)
  error_mensaje   TextField(blank)
  respuesta_api   JSONField(null)
  enviado_en / actualizado_en
  unique_together = (campana, contacto)          # blindaje anti doble envío
```

**Comando de importación** `clinica/management/commands/importar_contactos_academia.py`:

```
python manage.py importar_contactos_academia --archivo "C:\...\bddo.xlsx" [--dry-run]
```

- Lee desde la fila 4, mapea por nombre de encabezado (no por índice fijo).
- Normaliza el teléfono con `wa._normalizar_telefono()` y guarda los **últimos
  10 dígitos** (así quedan alineados con `buscar_paciente_por_wa_id`, que hace
  match por los últimos 10). Resuelve de paso los 2 registros de 11 dígitos.
- **Descarta las 26 filas sin teléfono** y las reporta al final.
- `update_or_create` por teléfono → idempotente, se puede correr varias veces.
- Si el mismo teléfono trae nombres distintos, conserva el primero y lo anota
  en las observaciones de la inscripción.
- Salida: contactos creados / actualizados, inscripciones creadas, filas
  descartadas y por qué.

Resultado esperado: **~248 contactos, ~290 inscripciones**.

El archivo se copia a `clinica/fixtures/` o se sube por la vista; queda a
decidir si la carga es de una sola vez (comando) o recurrente (upload en el
panel). Recomiendo empezar con el comando — es una carga única.

---

## 4. Fase 2 — La vista de envío

Reemplaza el placeholder actual. Tres bloques en la misma página:

### 4.1 Selección y preview

- Selector de plantilla (por ahora solo la nueva) + preview del texto exacto
  renderizado desde `TEMPLATE_BODIES`.
- Filtros sobre `ContactoAcademia` / `InscripcionAcademia`:
  **estatus** (activos ✔ + inactivos ✔ por default, es lo que pediste),
  diplomado, año fuente. Excluye siempre `suscrito=False`.
- Contador en vivo: *"Se enviará a **248** contactos únicos"*.
- Tabla con los destinatarios y checkbox para deseleccionar casos puntuales.
- Botón **Preparar envío** → crea la `CampanaMasiva` y un `EnvioMasivo` en
  estado `pendiente` por contacto. Todavía no manda nada.

### 4.2 Modo prueba (paso obligatorio antes del disparo real)

Campo para 1-3 teléfonos propios → manda solo a esos y muestra el resultado
crudo de Meta. Sirve para confirmar que la plantilla quedó aprobada, que el
texto se ve bien en el celular y que los emojis no se rompieron.

### 4.3 Envío por lotes

`POST /portal-direccion-comercial/mensajes-masivos/enviar-lote/`

Toma los siguientes **20 pendientes** de la campaña, los manda con
`wa.enviar_template()`, guarda `wa_message_id` de la respuesta, y devuelve
`{enviados, fallidos, restantes}`. El front lo llama en bucle con barra de
progreso hasta que `restantes == 0`.

**Por qué por lotes y no de un jalón:** no hay worker asíncrono en el proyecto y
`enviar_template` usa `timeout=10` por llamada — 290 envíos secuenciales en un
solo request superan el timeout de gunicorn en Railway y se cortarían a la
mitad. Es además el patrón que ya usa el panel DEMOS.

**Manejo de errores por envío** (sin abortar el lote):

| Código Meta | Significado | Acción |
|---|---|---|
| `131026` | número no está en WhatsApp | `fallido`, no reintentar |
| `131049` | tope de marketing por usuario (Meta decidió no entregarlo) | `fallido`, no reintentar |
| `130472` | usuario en experimento de Meta | `fallido`, no reintentar |
| `80007` / `130429` | rate limit | dejar `pendiente`, se reintenta en el siguiente lote |
| `132000-132xxx` | problema de plantilla | abortar la campaña y avisar |

Pausa de ~250 ms entre envíos dentro del lote.

---

## 5. Fase 3 — Respuestas y estados de entrega

### 5.1 Estados de entrega (enviado → entregado → leído)

`whatsapp_webhook` (`views.py:6906`) hoy solo lee `value['messages']` e ignora
`value['statuses']`. Se agrega el segundo bucle: por cada status, buscar
`EnvioMasivo` por `wa_message_id` y actualizar `estado` (`sent` → enviado,
`delivered` → entregado, `read` → leído, `failed` → fallido + `errors[0].code`).

No requiere cambiar la suscripción en Meta: los statuses llegan en el mismo
campo `messages` que ya está suscrito.

### 5.2 Ver las respuestas

Las respuestas **ya se están guardando** en `MensajeWhatsAppEntrante`, pero con
`paciente=NULL` porque los alumnos de Academia no son pacientes. Cambios:

1. Campo nuevo `MensajeWhatsAppEntrante.contacto_academia` → FK nullable a
   `ContactoAcademia`.
2. En `_registrar_mensaje_entrante` (`views.py:6831`): si
   `buscar_paciente_por_wa_id` no encuentra paciente, buscar `ContactoAcademia`
   por los últimos 10 dígitos del `wa_id` y ligarlo.
3. **Bandeja en el panel**: pestaña "Respuestas" listando los
   `MensajeWhatsAppEntrante` de contactos de Academia posteriores al inicio de
   la campaña — nombre, diplomado, teléfono, texto, fecha, badge de no leído, y
   botón "Marcar atendido" (los campos `atendido` / `atendido_por` /
   `atendido_en` ya existen en el modelo).
4. **Responder** (dentro de la ventana de 24 h que abre la respuesta del
   alumno): función nueva `wa.enviar_texto(telefono, texto)` con
   `"type": "text"` — hoy `services_whatsapp.py` solo sabe mandar plantillas.
   Fuera de las 24 h, Meta rechaza el texto libre y solo se puede plantilla;
   la UI debe mostrar el contador y deshabilitar el campo cuando expira.

### 5.3 Bajas (opt-out)

Si el texto entrante corresponde al Quick Reply de baja, o contiene
`BAJA` / `NO DESEO` / `STOP` (misma normalización sin acentos que usa
`_es_confirmacion`), marcar `ContactoAcademia.suscrito = False`. Los filtros de
la Fase 2 ya excluyen a los no suscritos.

---

## 6. Fase 4 — Seguimiento de la campaña

Tercer bloque del panel: tarjetas con **enviados / entregados / leídos /
fallidos / respuestas**, tabla de `EnvioMasivo` filtrable por estado, motivo del
fallo visible por fila, y exportar a CSV. Reusa el estilo `.dc-card` /
`.dc-hero` del portal (azul `#0d6efd`).

---

## 7. Archivos a tocar

| Archivo | Cambio |
|---|---|
| `clinica/models.py` | 4 modelos nuevos + FK en `MensajeWhatsAppEntrante` |
| `clinica/migrations/0095_*.py` | migración |
| `clinica/management/commands/importar_contactos_academia.py` | **nuevo** |
| `clinica/services_whatsapp.py` | body de la plantilla en `TEMPLATE_BODIES` + `enviar_texto()` |
| `clinica/views.py` | vista de envío, `enviar_lote`, bandeja, responder, `statuses` en el webhook, opt-out |
| `core/urls.py` | 4-5 rutas nuevas bajo `portal-direccion-comercial/mensajes-masivos/` |
| `clinica/templates/clinica/mensajes_masivos_direccion_comercial.html` | reemplazo completo |
| `clinica/admin.py` | registrar los modelos nuevos |

---

## 8. Orden de ejecución sugerido

1. Fase 0 en Meta (plantilla a aprobación) — **arrancar ya**, tarda de minutos
   a 24 h y bloquea todo lo demás.
2. Fase 1: modelos + comando de importación. Verificar los ~248 contactos.
3. Fase 2: panel + envío por lotes + **modo prueba a tu propio número**.
4. Fase 3: webhook de statuses + bandeja de respuestas.
5. Disparo real (dividido en dos días si el tier es 250).
6. Fase 4: métricas.

Las fases 1 y 3 no dependen de que Meta apruebe, así que se pueden construir en
paralelo mientras la plantilla está en revisión.

---

## 9. Decisiones que necesito de ti

1. **¿Plantilla con `{{1}}` nombre o texto fijo?** (recomiendo texto fijo).
2. **¿El número de WhatsApp es el mismo de los recordatorios de pacientes de
   INTRA?** Si sí, evaluemos los riesgos de calidad antes de disparar.
3. **¿Tier de mensajería del WABA?** (250 / 1K / …) — define si el envío va en
   uno o dos días.
4. **¿Carga del Excel única (comando) o recurrente (upload en el panel)?**
   (recomiendo comando).
5. **¿Se envía a los 21 diplomados o solo a algunos?** Dijiste activos e
   inactivos; asumo **toda la base**, incluidos los 4 que ya están en
   Psicoterapia Infantil — dime si a esos hay que excluirlos.
