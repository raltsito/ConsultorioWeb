# Plan: Módulo "Instrumentos" — Encuestas/Evaluaciones nativas

## Contexto
Hoy los instrumentos (encuestas para evaluar pacientes) viven en WordPress + Forminator,
conectados a Google Sheets para sacar resultados. Objetivo: traerlos 100% nativos a
ConsultorioWeb, dentro del Portal del Terapeuta (`/portal-medico/`), con un diseño
**muy cuidado, bonito y con animaciones**, a la altura del resto del portal.

Flujo deseado: el terapeuta elige un instrumento → genera un link único → se lo
manda al paciente (o lo abre él mismo en consulta) → el paciente lo contesta desde
el navegador (sin necesidad de cuenta/login) → las respuestas y resultados quedan
guardados y visibles en el expediente / portal del terapeuta.

> Convención del proyecto: todo vive en la app `clinica` (modelos, vistas, templates,
> `services_instrumentos.py` si la lógica crece). Nada de apps nuevas ni DRF.

---

## Fase 0 — Diseño de datos (modelos) ✅ COMPLETADA
- [x] Definir modelo `Instrumento` (catálogo): `nombre`, `clave` (slug para el motor
      de puntuación), `descripcion`, `instrucciones`, `activo`, `creado_en`
- [x] Definir modelo `PreguntaInstrumento`: FK a `Instrumento`, `texto`, `orden`, `clave`,
      `tipo_respuesta` (opción única/múltiple, escala/Likert, sí-no, texto libre),
      `opciones` (JSONField `[{valor, etiqueta}]`), `requerida`
- [x] Definir modelo `EnvioInstrumento` (el "link" generado): `token` (UUID único),
      FK a `Instrumento`, FK a `Paciente`, `generado_por` (User), `estado`
      (`pendiente`/`respondido`/`cancelado`), `creado_en`, `respondido_en`
- [x] Definir modelo `RespuestaInstrumento`: FK a `EnvioInstrumento`, FK a `PreguntaInstrumento`,
      `valor` (crudo) + `valor_numerico` (para el motor de puntuación), `unique_together` envío+pregunta
- [x] Resultado/puntaje: en `EnvioInstrumento` se agregaron `puntaje_total`,
      `interpretacion` (texto automático) y `resultado_detalle` (JSONField con el
      desglose: subescalas, rangos, semáforos…). Las **fórmulas/baremos en sí**
      vivirán en `clinica/services_instrumentos.py`, identificadas por `Instrumento.clave`
      — así cada instrumento puede tener su propia lógica sin tocar los modelos.
      Ya se creó `clinica/services_instrumentos.py` con `calcular_resultado_instrumento()`
      y un registro `_CALCULADORAS` por clave (vacío por ahora — listo para recibir
      las fórmulas de Preconsulta/SCID-II en cuanto tengamos el Sheet)
- [x] Migración creada y aplicada en dev: `0072_instrumento_envioinstrumento_preguntainstrumento_and_more.py` (sin conflictos con datos existentes)

## Fase 1 — Administración de instrumentos (catálogo)
- [x] **Captura inicial habilitada vía admin de Django**: se registraron `Instrumento`
      (con inline de `PreguntaInstrumento` para cargar preguntas + opciones JSON
      directo desde la pantalla del instrumento, `clave` autogenerada desde el nombre)
      y `EnvioInstrumento` (solo lectura + inline de `RespuestaInstrumento`, para
      auditar aplicaciones y resultados desde `/admin/`). Esto nos permite empezar
      a cargar **Preconsulta** y **SCID-II** ya mismo sin esperar a tener pantallas nativas
- [x] Vista nativa **"Catálogo de Instrumentos"** dentro del portal del terapeuta
      (`/portal-medico/instrumentos/`, fuera del admin): grid animado de tarjetas
      por instrumento (nombre, descripción, # de preguntas o aviso "aún sin preguntas
      cargadas"), buscador en vivo por nombre/descripción, paleta turquesa/coral INTRA
      con animaciones de entrada escalonadas y hover con pulso en el ícono. Acceso
      directo agregado al encabezado del portal del terapeuta. Solo muestra
      instrumentos `activo=True`. Probado: render, búsqueda con/sin resultados,
      exclusión de inactivos y conteo de preguntas — todo OK
- [ ] Decidir si la edición fina de instrumentos se queda en el admin de Django
      (ya cubierto arriba) o eventualmente se construye una pantalla nativa a medida
- [ ] **Catálogo inicial a soportar** (lote 1, según captura de Forminator —
      después se agregarán más): Preconsulta, Terapia de Parejas, SCID-II, SCL,
      TCI, IDARE, DASS-21, BDI, BAI, BAI-Y, ISRA, Inventario de Estado Marital,
      EAD, TDS, TEPT, Habilidades Sociales, MBI, Eneagrama, ATS, Hamilton (y los
      que sigan en la lista — confirmar si hay más abajo del corte de pantalla)
- [ ] Para cada instrumento del catálogo: capturar sus preguntas, tipo de
      respuesta/escala y, sobre todo, su **fórmula de puntuación/baremo propio**
      (cada uno es distinto: SCID-II, BDI, BAI, Hamilton, etc. tienen sus propios
      rangos e interpretaciones clínicas — esto es trabajo de captura, no solo de código)
- [ ] **Pilotos a construir primero:** `Preconsulta` y `SCID-II` — capturarlos
      completos (preguntas + baremo) y dejarlos funcionando de punta a punta antes
      de avanzar con el resto de los 18 instrumentos restantes
- [ ] (Opcional) Importar/precargar los instrumentos que ya existen en Forminator
      como semilla inicial (catálogo + preguntas), priorizando el lote 1

## Fase 2 — Generar y enviar el link al paciente ✅ FLUJO BASE LISTO
- [x] Botón "Aplicar instrumento" en el expediente del paciente (portal terapeuta),
      como nueva tarjeta `.xcard` "Instrumentos" en el sidebar (mismo lenguaje visual
      que Citas/Notas/Documentos)
- [x] Modal "Aplicar instrumento" para elegir del catálogo activo y generar un
      `EnvioInstrumento` con token único (UUID) vía endpoint AJAX
      (`generar_envio_instrumento`, JSON, con CSRF + permisos)
- [x] Tras generar: pantalla de confirmación animada (check ✓) con el link en un
      input de solo lectura + botón "Copiar" (clipboard API con fallback), y mensaje
      "¡Copiado al portapapeles!" — envío sigue siendo manual (WhatsApp, etc.)
- [x] Permitir generar el **mismo instrumento varias veces para el mismo paciente**:
      cada clic crea un `EnvioInstrumento` nuevo e independiente; la lista de
      "Instrumentos enviados" del paciente los muestra todos, del más reciente al
      más antiguo, cada uno con su propio estado/resultado (longitudinal, sin límite)
- [x] Lista de instrumentos aplicados al paciente directamente en el `.xcard`:
      nombre, fecha de envío/respuesta y estado (`Pendiente` → botón "Copiar enlace",
      `Respondido` → badge verde, `Cancelado` → badge); se actualiza en vivo (sin
      recargar) al generar un nuevo enlace, con animación de entrada de la fila
- [x] Registrar la actividad: nueva acción `instrumento_enviado` / categoría
      `instrumento` en `RegistroActividad` (con su ícono propio), siguiendo el
      patrón existente vía `_registrar_actividad`
- [x] Probado de punta a punta con cliente de pruebas: botón visible → modal →
      generar enlace → JSON con link y datos del envío → fila nueva en la lista →
      registro de actividad creado → permisos (403 a pacientes ajenos, 405 a GET)
- [ ] Definir vigencia del link (¿expira? — de momento no expira ni es de un solo
      uso por tiempo; cada aplicación es su propio `EnvioInstrumento` y se bloquea
      sólo al ser respondido/cancelado — revisar si se requiere caducidad a futuro)

## Fase 3 — Formulario público para el paciente (sin login) ✅ FLUJO BASE LISTO
- [x] Nueva URL pública `instrumentos/<uuid:token>/` (vista `responder_instrumento`,
      **sin** `@login_required` — el token UUID es la única "credencial")
- [x] Instrucciones del instrumento integradas en la pantalla del formulario
      (campo `Instrumento.instrucciones`, se muestran arriba del cuestionario)
- [x] Formulario dinámico generado a partir de `PreguntaInstrumento`: soporta
      opción única, opción múltiple, escala/Likert, sí-no y texto libre — todas
      las preguntas en una sola pantalla con barra de progreso animada
- [x] Guarda `RespuestaInstrumento` (texto legible + valor numérico resuelto desde
      `opciones` para alimentar el motor de puntuación), marca `EnvioInstrumento`
      como `respondido`, registra `respondido_en` y dispara el hook de cálculo
      automático (`calcular_resultado_instrumento`)
- [x] Pantalla de agradecimiento animada (check ✓ dibujándose con SVG)
- [x] Casos borde con pantallas propias y bonitas: ya respondido, cancelado,
      preguntas obligatorias sin contestar (resalta cuáles faltan)
- [x] **Probado de punta a punta** con un instrumento de prueba: token → responder
      → guardar → marcar como respondido → bloquear reintento. Todo funcionando.
- [ ] Pulir UX a futuro: ¿una pregunta a la vez tipo wizard? ¿temporizador/guardado
      automático para cuestionarios largos como SCID-II? (revisar una vez que
      tengamos las preguntas reales cargadas y veamos qué tan largos son)

## Fase 4 — Resultados para el terapeuta ✅ FLUJO BASE LISTO
- [x] Nueva vista/página `resultado_envio_instrumento` (`clinica/resultado_instrumento.html`,
      extiende `base.html`) con diseño propio animado (paleta turquesa/coral INTRA,
      tarjetas `riSlideUp`, círculo de puntaje con `riPop`, filas de respuestas con
      stagger, línea de tiempo de evolución con `riGrowLine`)
- [x] Muestra **ambas cosas** sobre un `EnvioInstrumento` respondido:
      (a) círculo de puntaje total + interpretación automática (cuando el instrumento
      ya tiene baremo registrado en `services_instrumentos.py`) y desglose
      `resultado_detalle` en tarjetas tipo grid; (b) si **no** hay baremo aún, un
      aviso claro + el listado completo de respuestas crudas (pregunta, respuesta
      legible y valor numérico) para interpretación manual del terapeuta
- [x] Vista de **evolución/histórico**: cuando el mismo paciente tiene 2+ aplicaciones
      *respondidas* del mismo instrumento, se agrega automáticamente una sección con
      línea de tiempo animada comparando el puntaje de cada aplicación (resaltando
      "esta aplicación" en coral)
- [x] Acceso protegido (solo el terapeuta del paciente; redirige con mensaje si el
      envío todavía no ha sido respondido) y enlazado desde la tarjeta "Instrumentos"
      del expediente — el badge "Respondido" ahora es un botón "Ver resultado"
- [x] Probado de punta a punta: generar 2 aplicaciones → responder ambas como paciente
      → abrir resultado → verificar puntaje/datos crudos/evolución, **con y sin**
      fórmula de puntuación registrada, y bloqueo de acceso a envíos pendientes — todo OK
- [ ] (Opcional) Exportar resultado a PDF con `reportlab` (mismo patrón que `_generar_pdf_apertura`)
- [ ] (Opcional) Gráficas más ricas (barras/series) si algún instrumento lo amerita más adelante

## Fase 5 — Diseño visual y animaciones ✨ (foco principal)
- [ ] Definir un lenguaje visual propio para "Instrumentos" (paleta acorde a INTRA: turquesa `#26C6DA` / coral `#EF5350`, tarjetas `rounded-4`, sombras suaves)
- [ ] Pantalla del paciente: experiencia tipo "wizard" — barra de progreso animada, transiciones suaves entre preguntas, microinteracciones en botones/opciones al seleccionar
- [ ] Animaciones de entrada (fade/slide) consistentes con `base.html` (extender `@keyframes` existentes, sin meter librerías externas pesadas)
- [ ] Pantalla de agradecimiento con animación de cierre (ej. check animado, confeti sutil, ilustración)
- [ ] Tarjetas de "Instrumentos" en el portal del terapeuta con hover/elevación, iconografía Bootstrap Icons coherente con el resto (`bi-clipboard2-pulse`, `bi-graph-up`, etc.)
- [ ] Revisión responsive: el paciente probablemente conteste desde el celular en sala de espera — mobile-first de verdad

## Fase 6 — Migración de datos legacy (Forminator / Google Sheets)
- [ ] Decidir si vale la pena migrar histórico o solo arrancar "en limpio" desde cierta fecha
- [ ] Si se migra: script ETL puntual (siguiendo patrón de `cargar_*.py`, `get_or_create`, `django.setup()`) para volcar instrumentos/respuestas históricas desde el export de Sheets

## Fase 7 — Pruebas y despliegue
- [ ] Probar flujo completo: generar link → responder desde celular → ver resultado en portal
- [ ] Probar casos borde de seguridad (token adivinado, reuso de link, acceso a resultados ajenos)
- [ ] Validar migraciones contra `db.sqlite3` (dev) y plan de despliegue a producción (Railway/Postgres)
- [ ] Apagar/objetar gradualmente el flujo de Forminator una vez validado lo nativo

---

## Decisiones ya resueltas con el usuario
- **Puntuación:** cada instrumento debe dar tanto interpretación automática (con su
  propio baremo/fórmula) como los datos crudos para interpretación manual del terapeuta.
- **Envío del link:** copiar/pegar manual (WhatsApp u otro medio) — sin integración de envío automático.
- **Catálogo inicial (lote 1):** Preconsulta, Terapia de Parejas, SCID-II, SCL, TCI,
  IDARE, DASS-21, BDI, BAI, BAI-Y, ISRA, Inventario de Estado Marital, EAD, TDS,
  TEPT, Habilidades Sociales, MBI, Eneagrama, ATS, Hamilton — y más adelante se sumarán otros.
- **Reaplicación:** un mismo instrumento puede aplicarse al mismo paciente las veces
  que sea necesario (seguimiento longitudinal) → cada aplicación genera su propio
  `EnvioInstrumento` y resultado, habilitando vistas de evolución/histórico.

## Decisiones ya resueltas con el usuario (cont.)
- **Fórmulas/baremos:** el usuario ya tiene un Google Sheets con toda la información
  de puntuación e interpretación de cada instrumento — no hay que investigarlas desde cero.
  - [ ] Conseguir acceso/export de ese Google Sheets como insumo para capturar cada
        instrumento (preguntas, escalas, fórmula de puntaje, rangos/interpretación)
  - [ ] Revisar el Sheets junto con el usuario para mapear su estructura → modelos
        (`Instrumento` / `PreguntaInstrumento` / reglas de puntuación)

## Decisiones ya resueltas con el usuario (cont. 2)
- **Catálogo confirmado:** la lista de 20 instrumentos del lote 1 es completa,
  no hay más abajo de "Hamilton".
- **Instrumentos piloto:** se arranca el desarrollo con **Preconsulta** y **SCID-II**
  para validar el flujo completo end-to-end (modelo → link → respuesta del paciente
  → puntuación/interpretación → resultado visible) antes de escalar al resto del catálogo.
