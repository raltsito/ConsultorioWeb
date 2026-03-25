# Plan.md — Roadmap de Automatización de Bitácora y Nómina (ConsultorioWeb)

> **Instrucción para Claude:** NO escribas código todavía. Lee este documento, analízalo, activa tu "skill" de diseño de UI/UX y arquitectura de software, y ten este plan en mente. Cuando iniciemos cada fase, te pediré que actualices nuestro archivo `context.md` con los nuevos modelos y rutas antes de programar. Vamos a trabajar estrictamente por Sprints para asegurar la calidad.

## 1. El Problema Actual (Flujo Manual a Reemplazar)
Actualmente, INTRA maneja un flujo manual desconectado:
1. **Bitácora (Google Sheets):** Los terapeutas llenan a mano si el paciente asistió, cómo pagó, el monto, y si solicitan "Siguiente Cita".
2. **Reporte General (Google Sheets):** Recepción consolida la bitácora para control financiero.
3. **Nómina Semanal:** Cada semana, administración cruza el Reporte General con un documento de Word (Tabuladores de pago por servicio, perfil de terapeuta y bonos) para calcular cuánto pagarle a cada especialista.

## 2. El Objetivo del Sistema
Centralizar este flujo en **ConsultorioWeb** (Django) para que sea lo más automatizado posible:
- **Terapeutas:** Al terminar una sesión en su portal, reportan la asistencia, el pago y solicitan la siguiente cita.
- **Motor de Pagos:** El sistema calcula automáticamente la nómina semanal basada en reglas dinámicas (tabuladores generales, individuales y bonos).
- **Recepción (Staff):** Tendrá un panel de control con tablas de verificación detalladas (Vista tipo Bitácora, Vista de Reporte General y Vista de Nómina) para auditar y aprobar flujos.

---

## 3. Plan de Desarrollo por Sprints (Módulos)

### Sprint 1: Arquitectura de Datos (Tabuladores y Corte Semanal)
*Objetivo: Preparar la base de datos para soportar reglas de negocio financieras.*
- Diseñar modelos para `TabuladorPago` (reglas generales por servicio, excepciones por terapeuta, manejo de bonos).
- Diseñar modelo `CorteSemanal` o `Nomina` para agrupar las citas completadas de un terapeuta en una semana específica.
- *Entregable:* Actualización del `context.md` con los nuevos modelos y creación de `models.py`.

### Sprint 2: El Flujo del Terapeuta (Cierre de Cita y Seguimiento)
*Objetivo: Reemplazar el llenado manual de la Bitácora de Google Sheets.*
- UI/UX en el portal del terapeuta para hacer el "Check-out" de una cita (marcar estado a `si_asistio`, registrar `metodo_pago` y `costo`).
- Integrar en este mismo flujo el formulario de "Solicitar Espacio" (crear `SolicitudCita` para el próximo seguimiento).
- *Entregable:* Vistas, formularios y templates del portal médico.

### Sprint 3: Vistas de Recepción (Tablas de Control y Auditoría)
*Objetivo: Darle al staff visibilidad total (Reemplazo visual de Sheets).*
- Crear una vista de "Bitácora Diaria" (citas del día, asistencia, pagos, solicitudes pendientes).
- Crear una vista de "Reporte General" (filtro histórico por fechas, exportable a CSV/Excel).
- UI/UX enfocada en tablas tipo "DataTables" para fácil lectura, ordenamiento y verificación.
- *Entregable:* Dashboards de recepción y endpoints de datos.

### Sprint 4: Motor de Cálculo y Nómina Semanal
*Objetivo: Automatizar el cruce con el documento de Word.*
- Lógica de negocio (Services/Utils) que tome las citas de una semana con estatus `si_asistio` y aplique las reglas de los `TabuladorPago`.
- Vista para que Administración apruebe el corte semanal y genere el reporte de pago por terapeuta.
- *Entregable:* Lógica de cálculo, vistas de nómina y reportes de pago.

### Sprint 5: Pulido y Exportación
*Objetivo: Refinar detalles y asegurar la extracción de datos.*
- Asegurar que todas las tablas de recepción puedan descargarse en Excel.
- Validaciones finales de seguridad y permisos.

---
**¿Entendido, Claude? Confirma que has procesado este plan y dime qué dudas arquitectónicas tienes sobre el Sprint 1 antes de que te dé luz verde para empezar a planear los modelos de datos.**