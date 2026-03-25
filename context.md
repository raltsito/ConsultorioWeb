# context.md — ConsultorioWeb (Clínica Web para INTRA)

> **Propósito de este archivo:** Documento de contexto definitivo para asistentes de IA. Describe la arquitectura, modelo de negocio, reglas de datos y stack tecnológico del proyecto. No es un tutorial; es una referencia técnica de alto nivel.

---

## 1. Visión General

**ConsultorioWeb** es un sistema de gestión clínica web interno desarrollado para **INTRA** (Instituto de Neurociencias, Terapia y Rehabilitación Avanzada, o similar). Está orientado exclusivamente al uso interno del personal y terapeutas; no es un sistema público de pacientes.

### Funcionalidades principales
- Registro, búsqueda y gestión de expedientes de **pacientes**.
- Agendamiento y gestión de **citas** en múltiples sedes y salas.
- **Calendario visual** de citas por terapeuta, consultorio o división.
- **Portal del Terapeuta:** Vista personal de citas y solicitudes.
- **Portal del Paciente:** Vista de próximas citas e historial (acceso autenticado).
- Solicitudes de cita entrantes con flujo de aprobación/rechazo por staff.
- Gestión de **horarios de terapeutas** por día de semana.
- Panel de administración Django (`/admin/`) para supervisión total.

### Actores del sistema
| Rol | Descripción |
|---|---|
| **Staff / Recepcionista** | Usuario con acceso completo: crea pacientes, agenda citas, valida solicitudes. |
| **Terapeuta** | Usuario con `Terapeuta` vinculado. Accede a su portal personal (`/portal-medico/`). |
| **Paciente** | Usuario con `Paciente` vinculado. Accede a su portal (`/mi-portal/`) para ver citas y hacer solicitudes. |

---

## 2. Stack Tecnológico

| Categoría | Tecnología |
|---|---|
| **Lenguaje** | Python 3.13 |
| **Framework Web** | Django 5.2 |
| **Base de datos (dev)** | SQLite3 (`db.sqlite3`) |
| **Base de datos (prod)** | PostgreSQL (vía variable de entorno `DATABASE_URL`) |
| **ORM / Conf DB** | `dj-database-url` para resolución dinámica del motor |
| **Servidor de aplicación** | Gunicorn |
| **Archivos estáticos** | WhiteNoise (`CompressedStaticFilesStorage`) |
| **Contenerización** | Docker (imagen `python:3.13-slim`) |
| **Despliegue objetivo** | Railway (también compatible con cualquier PaaS con Procfile/Docker) |
| **Procesamiento de datos** | Pandas, openpyxl (scripts auxiliares ETL) |
| **Autenticación** | Django Auth integrado (`django.contrib.auth`) |
| **WSGI alternativo** | `passenger_wsgi.py` (compatibilidad con hosting cPanel/Passenger) |

---

## 3. Arquitectura del Proyecto

El proyecto sigue la estructura estándar de Django con **una app principal** y un **módulo de configuración**.

```
ConsultorioWeb/
├── core/                   # Módulo de configuración del proyecto Django
│   ├── settings.py         # Configuración global (DB, static, auth, middleware)
│   ├── urls.py             # Router raíz: conecta todas las rutas a clinica/views.py
│   ├── wsgi.py             # Punto de entrada WSGI
│   └── asgi.py             # Punto de entrada ASGI
│
├── clinica/                # App principal: TODA la lógica del negocio
│   ├── models.py           # Definición de todas las entidades de datos
│   ├── views.py            # Vistas (lógica HTTP) y endpoints JSON de la API
│   ├── forms.py            # Formularios Django para validación de entrada
│   ├── admin.py            # Configuración del panel de administración
│   ├── utils.py            # Funciones auxiliares (helpers reutilizables)
│   ├── templates/          # Plantillas HTML (estructura Bootstrap/Jinja-like)
│   ├── static/             # CSS, JS e imágenes propios de la app
│   └── management/         # Comandos custom de `manage.py` (si aplica)
│
├── staticfiles/            # Directorio de salida de `collectstatic` (no editar)
├── media/                  # Archivos subidos por usuarios (documentos de pacientes)
├── logs/                   # Logs de la aplicación
│
├── manage.py               # CLI de Django
├── Dockerfile              # Imagen Docker para producción
├── start.sh                # Script de arranque: collectstatic → migrate → gunicorn
├── Procfile                # Comando de arranque para Railway/Heroku
├── passenger_wsgi.py       # Adaptador para hosting cPanel
└── requirements.txt        # Dependencias de Python
```

### Módulo `core`
Actúa exclusivamente como **configuración del proyecto**. No contiene lógica de negocio. El archivo `urls.py` es el router raíz que delega todas las rutas directamente a `clinica/views.py`.

### Módulo `clinica`
Es la **única app Django** del proyecto. Contiene el 100% de la lógica de negocio, modelos, vistas, formularios y templates. No existe separación en múltiples apps; toda la funcionalidad vive aquí.

---

## 4. Modelos de Datos

Todas las entidades están definidas en `clinica/models.py`. La base de datos usa el ORM de Django con `BigAutoField` como PK por defecto.

### Diagrama de Relaciones (simplificado)

```
User (Django Auth)
 ├──[OneToOne]──► Terapeuta
 └──[OneToOne]──► Paciente

Paciente ──[FK]──► Servicio   (servicio_inicial)
Paciente ──[M2M]──► Paciente  (pacientes_relacionados, simétrico)

Cita ──[FK]──► Paciente       (paciente principal)
Cita ──[M2M]──► Paciente      (pacientes_adicionales)
Cita ──[FK]──► Terapeuta
Cita ──[FK]──► Consultorio
Cita ──[FK]──► Servicio
Cita ──[FK]──► Division

Horario ──[FK]──► Terapeuta

SolicitudCita ──[FK]──► Terapeuta

── MÓDULO NÓMINA ──────────────────────────────────────
TabuladorGeneral  (categorías 0–11, independiente)

Terapeuta ──[OneToOne]──► ReglaTerapeuta
ReglaTerapeuta ──[FK]──► TabuladorGeneral  (referencia opcional)

CorteSemanal ──[FK]──► Terapeuta
CorteSemanal ──[FK]──► User               (aprobado_por)

LineaNomina ──[FK]──► CorteSemanal
LineaNomina ──[FK]──► Cita                (nullable en líneas de bono global)

BonoExtra ──[FK]──► CorteSemanal
BonoExtra ──[FK]──► Cita                  (nullable, referencia opcional)
BonoExtra ──[FK]──► User                  (registrado_por)
```

---

### Entidades principales

#### `Paciente`
Expediente central del sistema. Cada paciente tiene datos demográficos, de contacto, documentos adjuntos y relaciones con otros pacientes.

| Campo clave | Tipo | Notas |
|---|---|---|
| `nombre` | `CharField` | Nombre completo. Fuente de verdad. |
| `nombre_normalizado` | `CharField` | Generado automáticamente en `save()`. Versión sin tildes y en minúsculas de `nombre`. Usado para búsqueda. **No editable manualmente.** |
| `fecha_nacimiento` | `DateField` | Requerido. En importaciones masivas se usa `2000-01-01` como placeholder. |
| `sexo` | `CharField` | Choices: `Femenino` / `Masculino`. Default: `Femenino`. |
| `telefono` | `CharField` | WhatsApp del contacto principal. |
| `identidad_contacto` | `CharField` | Relación del contacto con el paciente: `propio`, `madre`, `padre`, `pareja`, `otro`. |
| `servicio_inicial` | `FK → Servicio` | Servicio por el que ingresó a la clínica. |
| `usuario` | `OneToOne → User` | Opcional. Solo si el paciente tiene acceso al portal web. |
| `pacientes_relacionados` | `M2M → self` | Familia / grupo en terapia. Relación simétrica. |
| `consentimiento_firmado` | `FileField` | PDF/imagen en `media/documentos/`. |

> **Regla crítica:** La función `quitar_tildes()` se ejecuta automáticamente en cada `save()` del modelo `Paciente` para mantener `nombre_normalizado` sincronizado. Nunca se debe escribir en este campo directamente.

---

#### `Cita`
Núcleo operativo del sistema. Representa una sesión agendada entre uno o más pacientes y un terapeuta.

| Campo clave | Tipo | Notas |
|---|---|---|
| `paciente` | `FK → Paciente` | Paciente titular (obligatorio). |
| `pacientes_adicionales` | `M2M → Paciente` | Permitido en terapias de pareja/familiar. |
| `fecha` + `hora` | `DateField` + `TimeField` | Fecha y hora de la cita. |
| `tipo_paciente` | `CharField` | `N` (Nuevo), `R` (Referido), `S` (Seguimiento). |
| `estatus` | `CharField` | Ver estados abajo. Default: `sin_confirmar`. |
| `terapeuta` | `FK → Terapeuta` | Puede ser nulo (cita sin asignar). |
| `consultorio` | `FK → Consultorio` | Sala física o virtual donde se realiza. |
| `servicio` | `FK → Servicio` | Tipo de terapia prestada en esa sesión. |
| `division` | `FK → Division` | Convenio/cliente bajo el que se factura. |
| `costo` | `DecimalField` | Monto cobrado. Nullable (puede ser pase o gratuita). |
| `metodo_pago` | `CharField` | `Terminal`, `Transferencia`, `Efectivo`, `Pase`. |
| `folio_fiscal` | `CharField` | Folio de comprobante fiscal. Opcional. |

**Estados válidos de una `Cita`:**

| Estatus | Código | Significado |
|---|---|---|
| Sin confirmar | `sin_confirmar` | Estado inicial al crear |
| Confirmada | `confirmada` | Paciente avisado, asistirá |
| Reagendada | `reagendo` | Se moverá de fecha |
| Canceló | `cancelo` | Paciente canceló |
| Sí asistió | `si_asistio` | Sesión completada |
| No asistió | `no_asistio` | Falla sin aviso |
| Incidencia | `incidencia` | Situación especial |

**Estados activos** (citas que "cuentan" como vigentes): `confirmada`, `sin_confirmar`, `reagendo`, `incidencia`.

---

#### `Terapeuta`
Perfil del profesional de salud. Vinculado opcionalamente a un `User` de Django para autenticación.

| Campo | Tipo | Notas |
|---|---|---|
| `nombre` | `CharField` | Nombre completo del terapeuta. |
| `activo` | `BooleanField` | Si está `False`, no aparece en listados de agendamiento. |
| `usuario` | `OneToOne → User` | Permite login al portal de terapeuta. |

---

#### `Horario`
Define la disponibilidad semanal recurrente de un terapeuta. Es la base para verificar disponibilidad al agendar.

| Campo | Tipo | Notas |
|---|---|---|
| `terapeuta` | `FK → Terapeuta` | — |
| `dia` | `IntegerField` | 0=Lunes … 6=Domingo. |
| `hora_inicio` | `TimeField` | — |
| `hora_fin` | `TimeField` | — |

---

#### `SolicitudCita`
Registro de peticiones de cita realizadas desde el **portal del paciente**. Flujo:
`pendiente` → `aceptada` (se convierte en `Cita`) o `rechazada` (se guarda `motivo_rechazo`).

---

#### `TabuladorGeneral`
Categorías base de pago (perfiles 0–11). Se aplica a terapeutas sin `ReglaTerapeuta` individual, o sirve de referencia categórica.

| Campo | Tipo | Notas |
|---|---|---|
| `numero` | `IntegerField` | Categoría única (0–11). |
| `descripcion` | `TextField` | Perfil de formación del nivel. |
| `pago_base` | `DecimalField` | Monto fijo por sesión en consultorio INTRA. |
| `pago_consultorio_propio` | `DecimalField` | Monto alternativo si la sesión es en consultorio del terapeuta (cats. 6 y 11). Nullable. |
| `bono_monto` | `DecimalField` | Monto del bono al alcanzar el umbral. Nullable. |
| `bono_umbral_pacientes` | `IntegerField` | Nro de pacientes para activar el bono (repetible). Nullable. |

---

#### `ReglaTerapeuta`
Reglas individuales de pago por terapeuta. Cuando existen, **reemplazan** al `TabuladorGeneral`. Relación `OneToOne` con `Terapeuta`.

**Lógica de resolución de pago por sesión (prioridad):**
1. Si la cita es de pareja/familiar y `pago_pareja` no es nulo → `pago_pareja`
2. Si `pago_individual` no es nulo → `pago_individual`
3. Si `pago_por_sesion` no es nulo → `pago_por_sesion`
4. Fallback → `tabulador_base.pago_base`

| Campo | Tipo | Notas |
|---|---|---|
| `terapeuta` | `OneToOne → Terapeuta` | — |
| `tabulador_base` | `FK → TabuladorGeneral` | Referencia categórica. Opcional. |
| `pago_por_sesion` | `DecimalField` | Tarifa única para cualquier modalidad. |
| `pago_individual` | `DecimalField` | Tarifa para sesiones individuales (cuando hay diferenciación). |
| `pago_pareja` | `DecimalField` | Tarifa para sesiones de pareja/familiar. |
| `pago_consultorio_propio` | `DecimalField` | Tarifa si la sesión ocurre en consultorio del propio terapeuta. |
| `bono_umbral_monto` | `DecimalField` | Monto del bono de volumen (repetible: ×2 si alcanza el doble del umbral). |
| `bono_umbral_pacientes` | `IntegerField` | Umbral de pacientes para activar el bono de volumen. |
| `bono_por_paciente` | `DecimalField` | Bono adicional fijo por cada paciente del periodo (tipo supervisor). |
| `notas` | `TextField` | Observaciones operativas (ej. hora extra en evaluaciones). |

---

#### `CorteSemanal`
Nómina semanal de un terapeuta. Agrupa citas con `estatus='si_asistio'` de **lunes a domingo**. El cálculo es ejecutado por el motor en `clinica/services.py` y se almacena como snapshot.

| Campo | Tipo | Notas |
|---|---|---|
| `terapeuta` | `FK → Terapeuta` | — |
| `fecha_inicio` | `DateField` | Lunes de la semana. |
| `fecha_fin` | `DateField` | Domingo de la semana. |
| `total_sesiones` | `IntegerField` | Cantidad de citas contabilizadas. |
| `subtotal_sesiones` | `DecimalField` | Suma de pagos por sesión (sin bonos). |
| `total_bonos` | `DecimalField` | Suma de todos los bonos del periodo. |
| `total_pago` | `DecimalField` | `subtotal_sesiones + total_bonos`. |
| `estatus` | `CharField` | `borrador` → `aprobado` → `pagado`. |
| `aprobado_por` | `FK → User` | Staff que aprobó el corte. Nullable. |

> **Restricción:** `unique_together = ('terapeuta', 'fecha_inicio')` — solo un corte por terapeuta por semana.

---

#### `LineaNomina`
Detalle línea por línea de un `CorteSemanal`. Audit trail del cálculo. Una línea por cita (`tipo='sesion'`) y líneas adicionales por cada bono aplicado.

| Campo | Tipo | Notas |
|---|---|---|
| `corte` | `FK → CorteSemanal` | — |
| `cita` | `FK → Cita` | Nulo solo en líneas de bono global (bono de volumen). |
| `tipo` | `CharField` | `sesion`, `bono_umbral`, `bono_por_paciente`. |
| `concepto` | `CharField` | Descripción legible del concepto calculado. |
| `monto` | `DecimalField` | Monto de la línea. |

---

#### `BonoExtra`
Pagos manuales esporádicos ligados a un `CorteSemanal`. Para conceptos fuera de las reglas automáticas del tabulador (ej. hora extra de elaboración de informe en evaluaciones). Se suman al `total_pago` del corte al momento de aprobar.

| Campo | Tipo | Notas |
|---|---|---|
| `corte` | `FK → CorteSemanal` | — |
| `cita` | `FK → Cita` | Opcional. Referencia a la cita que originó el bono. |
| `concepto` | `CharField` | Descripción del pago (ej. 'Hora de elaboración de informe'). |
| `monto` | `DecimalField` | — |
| `registrado_por` | `FK → User` | Staff o admin que autorizó el pago. |

---

#### Catálogos (tablas de referencia)

| Modelo | Propósito |
|---|---|
| `Division` | Convenio o tipo de cliente: `Particular`, `NEAPCO`, `GIASA`, `INSUNTE`, `DOROTHEA`, `UNIVAS`, `iFOOD`, `UTS`, `Cáritas de Saltillo`, `Escuela`, `Otro`. |
| `Servicio` | Tipo de terapia: `Terapia individual`, `Terapia infantil`, `Terapia de parejas`, `Terapia Familiar`, `Evaluación neuropsicológica`, `Consulta psiquiátrica`, `Consulta en salud mental`, `Consulta nutricional`, `Hipnosis`, `Psicotanatología`, `Consulta Médica`. |
| `Consultorio` | Sala física o virtual. Sedes: **República** (Salas 1-3), **Morelos** (Salas 1-2), **Colinas** (Única), **Trabajo Social (Poniente)**, **Zoom / Online**. |

---

## 5. Motor de Nómina (`clinica/services.py`)

Toda la lógica financiera vive aquí. Las vistas **nunca** calculan nómina directamente; siempre llaman a estas funciones.

### Funciones públicas

| Función | Descripción |
|---|---|
| `calcular_nomina_semanal(terapeuta, fecha_inicio, fecha_fin)` | Genera o recalcula el `CorteSemanal` en borrador. Lanza `ValueError` si el corte ya fue aprobado/pagado. |
| `preview_nomina_semanal(terapeuta, fecha_inicio, fecha_fin)` | Retorna un `dict` con el desglose completo **sin persistir** en BD. Útil para mostrar el resumen antes de confirmar. |
| `aprobar_corte_semanal(corte, aprobado_por)` | Cambia el estatus de `borrador` → `aprobado`. Después de aprobar el corte no puede recalcularse. |

### Helpers internos

| Helper | Descripción |
|---|---|
| `_resolver_monto_sesion(cita, regla)` | Aplica la jerarquía de prioridad de `ReglaTerapeuta` para determinar el monto de una cita. |
| `_calcular_bonos_automaticos(total_sesiones, regla)` | Calcula bonos por umbral y bono por paciente. Retorna lista de dicts para crear `LineaNomina`. |

### Jerarquía de prioridad en `_resolver_monto_sesion`
1. `pago_pareja` — si la cita tiene `pacientes_adicionales`
2. `pago_individual`
3. `pago_por_sesion`
4. `tabulador_base.pago_base` (fallback al TabuladorGeneral)
5. `Decimal("0.00")` con advertencia en el concepto

### Reglas importantes
- `calcular_nomina_semanal` usa `bulk_create` para las `LineaNomina` (eficiencia).
- Al recalcular un borrador: **borra las `LineaNomina` automáticas** pero **respeta los `BonoExtra` manuales**.
- Los `BonoExtra` existentes se suman al `total_bonos` y `total_pago` del snapshot.
- El bono por umbral es **repetible**: `floor(total_sesiones / umbral) × monto`.
- `preview_nomina_semanal` **no incluye** `BonoExtra` (requieren un corte existente en BD).

---

## 6. Scripts ETL y Procesamiento de Datos

Estos scripts Python viven en la raíz del proyecto y son herramientas de migración/carga de datos **de un solo uso o uso administrativo**. No forman parte del flujo de la aplicación web. Se ejecutan directamente desde la terminal.

### `limpiar_pacientes.py`
**Propósito:** Pre-procesamiento de datos legacy. Lee una lista de nombres de pacientes desde un Excel (con registros sucios/duplicados), aplica **lógica difusa** con `difflib.SequenceMatcher` (umbral de similitud: 85%) para detectar variaciones del mismo nombre, y genera el archivo limpio `PACIENTES_LIMPIOS.xlsx`.

**Flujo:** `REVISAR_PACIENTES.xlsx` → fuzzy dedup → `PACIENTES_LIMPIOS.xlsx`

### `cargar_pacientes.py`
**Propósito:** Importación masiva a la base de datos Django. Lee `PACIENTES_LIMPIOS.xlsx` (o `.csv`) e inserta registros en la tabla `Paciente` usando `get_or_create` (idempotente, seguro de re-ejecutar).

**Regla de importación:** Para campos requeridos sin datos disponibles se usan placeholders: `fecha_nacimiento = 2000-01-01`, `sexo = 'Femenino'`, `telefono = ''`. Estos deben actualizarse manualmente después.

**Flujo:** `PACIENTES_LIMPIOS.xlsx` → ORM Django → tabla `clinica_paciente`

### `cargar_catalogos.py`
**Propósito:** Seed de los catálogos base del sistema (`Division`, `Servicio`, `Consultorio`). Usa `get_or_create`, por lo que es seguro ejecutarlo múltiples veces.

**Flujo:** Datos hardcodeados en el script → ORM Django → tablas de catálogo

### `cargar_horarios.py`
**Propósito:** Carga o recarga completa de los horarios semanales de todos los terapeutas. **Destructivo:** borra todos los registros de `Horario` antes de insertar. Los datos de horarios están hardcodeados en el script.

> ⚠️ **Advertencia:** `cargar_horarios.py` hace `Horario.objects.all().delete()` al inicio. No ejecutar en producción sin respaldo.

### `analisis_datos.py`
**Propósito:** Script de análisis exploratorio de los datos originales (Excel legacy). No inserta datos en la BD.

---

## 6. Rutas de la Aplicación

| URL | Nombre | Acceso |
|---|---|---|
| `/` | `home` | Autenticado |
| `/pacientes/` | `lista_pacientes` | Staff |
| `/pacientes/nuevo/` | `registrar_paciente` | Staff |
| `/pacientes/<id>/` | `detalle_paciente` | Staff |
| `/pacientes/<id>/editar/` | `editar_paciente` | Staff |
| `/pacientes/<id>/agendar/` | `agendar_cita` | Staff |
| `/crear-cita/` | `crear_cita` | Staff |
| `/calendario/` | `vista_calendario` | Staff |
| `/citas/<id>/editar/` | `editar_cita` | Staff |
| `/citas/<id>/eliminar/` | `eliminar_cita` | Staff |
| `/portal-medico/` | `portal_terapeuta` | Terapeuta |
| `/citas/<id>/checkout/` | `checkout_cita` | Terapeuta (POST only — procesa el modal de cierre de sesión) |
| `/bitacora/` | `bitacora_diaria` | Staff — tabla diaria con DataTables, filtro por fecha, indicador de seguimiento |
| `/reporte-general/` | `reporte_general` | Staff — historial filtrable por fechas y terapeuta, exporta a CSV con `?export=csv` |
| `/mi-portal/` | `portal_paciente` | Paciente |
| `/mi-portal/solicitar/` | `solicitar_cita_paciente` | Paciente |
| `/admin/` | Django Admin | Superuser |
| `/api/citas/` | `calendario_citas` | JSON API |
| `/api/citas-calendario/` | `api_citas_calendario` | JSON API |
| `/api/verificar-disponibilidad/` | `verificar_disponibilidad` | JSON API |
| `/api/terapeutas-paciente/` | `api_terapeutas_paciente` | JSON API |
| `/api/pacientes-relacionados/` | `api_pacientes_relacionados` | JSON API |
| `/api/disponibilidad-terapeuta/` | `api_disponibilidad` | JSON API |
| `/accounts/login/` | `login` | Público |

---

## 7. Despliegue y Configuración

### Variables de entorno requeridas en producción

| Variable | Descripción | Ejemplo |
|---|---|---|
| `SECRET_KEY` | Clave secreta de Django | `"django-secret-xxx..."` |
| `DEBUG` | Modo debug. Siempre `False` en prod. | `False` |
| `DATABASE_URL` | Connection string completa a PostgreSQL | `postgres://user:pass@host:5432/db` |
| `PORT` | Puerto donde escucha Gunicorn | `8080` (Railway lo inyecta) |

### Proceso de arranque (`start.sh`)
Al iniciar el contenedor Docker, el script ejecuta en secuencia:
1. `python manage.py collectstatic --noinput` — Compila archivos estáticos en `staticfiles/`.
2. `python manage.py migrate --noinput` — Aplica migraciones pendientes.
3. `exec gunicorn core.wsgi --bind 0.0.0.0:${PORT:-8080}` — Inicia el servidor.

### Archivos estáticos y media
- **Estáticos** (`/static/`): Servidos por **WhiteNoise** directamente desde Gunicorn. No requiere Nginx.
- **Media** (`/media/`): Documentos subidos por usuarios (consentimientos, estudios). En producción, idealmente migrar a almacenamiento externo (S3, GCS).

### CSRF y Proxy SSL
La configuración incluye `CSRF_TRUSTED_ORIGINS` para dominios de Railway (`*.up.railway.app`) y `SECURE_PROXY_SSL_HEADER` para respetar el header `X-Forwarded-Proto` del proxy de Railway.

---

## 8. Reglas y Convenciones

Estas directrices deben ser respetadas por cualquier IA o desarrollador que trabaje en este proyecto.

### Estructura
- **No crear nuevas apps Django.** Toda la lógica nueva va en la app `clinica`.
- Si una funcionalidad crece mucho, extraerla a un módulo dentro de `clinica/` (ej. `clinica/services.py`, `clinica/selectors.py`), no a una nueva app.
- Los archivos estáticos propios de la app van en `clinica/static/clinica/`.
- Las plantillas van en `clinica/templates/clinica/`.

### Modelos de datos
- **Nunca escribir directamente en `Paciente.nombre_normalizado`.** Este campo es gestionado por el método `save()` del modelo.
- Los catálogos (`Division`, `Servicio`, `Consultorio`) son datos de referencia y no deben eliminarse aleatoriamente; hay citas que los referencian con `SET_NULL`.
- Al agregar campos opcionales a modelos existentes, siempre usar `null=True, blank=True` para no romper registros históricos.
- Al crear migraciones, verificar que no haya conflictos con data ya existente en `db.sqlite3` (dev) ni en PostgreSQL (prod).

### Scripts ETL
- Los scripts de la raíz (`cargar_*.py`, `limpiar_*.py`) son herramientas administrativas. **No integrarlos al código de la aplicación.**
- Cualquier script nuevo de este tipo debe usar el patrón `django.setup()` al inicio y `if __name__ == "__main__"` al final.
- Siempre usar `get_or_create` en lugar de `create` en scripts de carga para hacerlos idempotentes.

### Autenticación y Acceso
- El sistema de autenticación es el de Django nativo. No añadir JWT, OAuth o DRF sin aprobación explícita.
- Los portales por rol (terapeuta, paciente) se controlan con decoradores de Django o verificaciones `request.user` en las vistas. No existe un sistema de permisos personalizado más allá de los grupos de Django.

### Base de datos
- En desarrollo: SQLite (`db.sqlite3`). El archivo `db.backup.sqlite3` es un respaldo manual; no editarlo.
- En producción: PostgreSQL via `DATABASE_URL`. La selección del motor es automática gracias a `dj-database-url`.
- Los archivos JSON (`respaldo_definitivo.json`, `respaldo_limpio.json`, `datos_locales.json`) son fixtures/respaldos de datos. Cargables con `python manage.py loaddata`.

### Lo que NO está en este proyecto (para evitar confusiones)
- ❌ No hay Django REST Framework (DRF). Las APIs JSON son vistas Django simples que retornan `JsonResponse`.
- ❌ No hay frontend separado (React, Vue, etc.). El frontend es server-side rendering con templates Django y HTML/CSS/JS vanilla.
- ❌ No hay Celery ni tareas asíncronas.
- ❌ No hay sistema de cache (Redis, Memcached).
- ❌ No hay múltiples apps Django; solo `clinica`.
