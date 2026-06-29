# Plan: Orbita — SaaS de Agenda (clon modular de ConsultorioWeb)

## 0. Decisiones ya tomadas

- **Arquitectura:** 1 repo/codebase ("Orbita"), **N despliegues** — 1 servicio Railway + 1 base de datos Postgres por cada clínica cliente. No es multi-tenant compartido (no hay una sola DB con todos los clientes mezclados).
- **ConsultorioWeb (este repo) no se toca.** Sigue siendo tu sistema interno, full-featured, single-tenant. Orbita es un fork único que evoluciona por su cuenta — no se vuelve a sincronizar con este repo.
- **No borrar módulos del código**, solo ocultarlos detrás de un sistema de permisos por plan.
- Marca: Orbita, reemplazando todo rastro de "INTRA".

---

## 1. Crear el repo Orbita (fork único, limpio)

Repo nuevo en GitHub. Copiar `clinica/`, `core/`, templates, static, `Dockerfile`, `Procfile`, `requirements.txt`, `manage.py`.

**NO copiar al repo nuevo** (datos reales y artefactos sensibles encontrados en este repo):
- `db.sqlite3`, `db.backup.sqlite3`
- `backup_consultorioweb_*.sql`, `respaldo_produccion_*.dump`, `backup_*.dump`
- `datos_locales.json`, `respaldo_definitivo.json`, `respaldo_limpio.json`
- `PACIENTES_LIMPIOS.xlsx`, `REVISAR_PACIENTES.xlsx`, `datos_originales.xlsx`
- `credenciales_google.json`, `nuevos_terapeutas_credenciales.txt`
- `proyecto_web.zip`, `server_preview.log`
- `reporte_cambios_sesion.html`, `Reporte_Cambios_2Jun2026.pdf`, `reporte_cambios_2jun2026.py`
- `context.md`, `plan.md`, `planinstrumentos.md`, `planwhfinal.md`, `MEJORAS.md` (planeación interna de tu clínica, no aplica a Orbita)
- Revisar `Docs/` antes de copiar nada de ahí

Resultado esperado: repo limpio, sin un solo dato de paciente real ni credencial committeada.

---

## 2. Sistema de planes/módulos (paywall modular)

Hacerlo primero porque es bajo riesgo, reutilizable, y no depende de tener ya el repo separado o el deploy en Railway.

- Modelo `Configuracion` (singleton, una fila por instancia ya que cada clínica vive en su propia DB) con flags booleanos: `tiene_nomina`, `tiene_instrumentos`, `tiene_catalogo_terapeutas`, `tiene_whatsapp`, `tiene_portal_empresa`, `tiene_host_checklist`, etc.
- Decorador `@requiere_modulo('nomina')` para las vistas — si el flag está apagado, 403/redirect.
- Template tag o context processor `modulo_activo` para no mostrar el link en el menú si el módulo no está contratado.
- Como no hay multi-tenant compartido, activar/desactivar un módulo es editar esa fila desde el admin de Django — no se necesita lógica de "tenant actual" en cada query.

### Módulos candidatos a quedar detrás de un flag (no borrar, decidir cuáles se ofrecen como upsell):
- Nómina de terapeutas: `TabuladorGeneral`, `CorteSemanal`, `LineaNomina`, `BonoExtra`
- Programas específicos: `Host`, `HostChecklistTask`, `Consultoria`
- Cuestionarios clínicos: `Instrumento`, `PreguntaInstrumento`, `EnvioInstrumento`, `RespuestaInstrumento`
- Integración WhatsApp (`services_whatsapp.py`, `MensajeWhatsApp*`, `ConfiguracionWhatsApp`)
- Portal empresa / catálogo de terapeutas público

---

## 3. Rebranding (Orbita)

- Centralizar nombre y logo como **configuración**, no como texto fijo en 41 archivos: agregar `BRAND_NAME` / `BRAND_LOGO` al modelo `Configuracion` (o a settings si prefieres algo más simple), expuesto a todos los templates vía context processor. Esto también deja la puerta abierta a marca blanca por cliente más adelante.
- Reemplazar `logointra.jpg` por el logo de Orbita.
- Limpiar referencias a "INTRA" en templates, `views.py`, `static/clinica/catalogo/app.jsx`, etc.
- **No tocar** archivos de migraciones (`clinica/migrations/...`) ni backups/SQL — son historial, no texto visible al usuario.
- Renombrar el proyecto Django (`core/` → algo con Orbita) es cosmético y de bajo riesgo, pero no es esencial para el v1; se puede dejar para después.

---

## 4. Integraciones que hoy son "tuyas" y deben volverse por-instancia

- **WhatsApp** (`services_whatsapp.py`): hoy probablemente usa credenciales fijas de tu clínica. Cada cliente de Orbita necesita sus propias credenciales (Twilio/API de WhatsApp), leídas de variables de entorno o del modelo `Configuracion` de su instancia — nunca hardcodeadas ni committeadas.
- **Google** (`gspread`/`oauth2client`, `credenciales_google.json`): mismo problema. Definir si Orbita v1 incluye esta integración o se deja fuera del producto genérico.

---

## 5. Provisioning: alta de una clínica nueva

Para los primeros clientes, proceso manual documentado:
1. Crear nuevo servicio en Railway desde el repo Orbita + nueva base Postgres.
2. Configurar variables de entorno (`DATABASE_URL`, credenciales propias del cliente, `BRAND_NAME` si aplica).
3. Correr `python manage.py migrate` + crear superusuario.
4. Configurar subdominio (`clinica1.orbita.app`) vía Railway custom domains.
5. Activar en `Configuracion` los módulos según el plan que pagó.

Cuando haya 5-10 clientes y este proceso sea repetitivo, automatizarlo con un script o un Railway template — no antes, sería optimizar prematuramente.

---

## 6. Billing (fuera de alcance inmediato)

- v1: completamente manual — cobras (transferencia/Stripe Checkout simple) y tú activas el flag correspondiente en `Configuracion`.
- v2 (cuando haya volumen): Stripe con webhook que actualiza `Configuracion` automáticamente.

---

## 7. Operación día a día

- **Actualizar a todos los clientes:** push a `main` del repo Orbita + redeploy de cada servicio Railway. Mientras sean pocos clientes, es manual; documentar el checklist de redeploy.
- **Migraciones:** correr `migrate` en cada instancia después de cada deploy con cambios de modelo.
- **Backups:** confirmar que el plan de Railway usado incluye backups automáticos de Postgres por servicio.

---

## Qué NO vamos a hacer (por ahora, para no sobre-diseñar)

- No construir multi-tenancy compartido (FK de tenant en cada modelo) — innecesario mientras el costo de N instancias sea manejable.
- No automatizar el provisioning de instancias antes de tener clientes reales que lo justifiquen.
- No automatizar billing antes de tener el primer cliente pagando.

---

## Orden recomendado de ejecución

1. Crear el repo Orbita limpio (sección 1)
2. Sistema de planes/módulos (sección 2) — bajo riesgo, reutilizable
3. Rebranding (sección 3)
4. Ajustar integraciones WhatsApp/Google para ser por-instancia (sección 4)
5. Deploy de una instancia piloto en Railway de punta a punta (sección 5)
6. Billing y automatización de provisioning cuando haya clientes reales (secciones 6-7)
