# Mejoras pendientes — ConsultorioWeb / INTRA

## Flujo de trabajo

- [ ] **Notificaciones internas** — badge o contador en portal empresa/terapeuta cuando recepción acepta o rechaza una solicitud
- [ ] **Historial de solicitudes en portal empresa** — tabla con todas las solicitudes enviadas y su estatus (pendiente / aprobada / rechazada)
- [ ] **Reagendar desde el portal** — mover una cita existente sin tener que cancelar y crear una nueva

## Datos y reportes

- [ ] **Reporte por empresa** — citas del mes, asistencias y cancelaciones por división (útil para que las empresas rindan cuentas a RRHH)
- [ ] **Exportar agenda del terapeuta** — descargar citas de la semana en PDF o CSV
- [ ] **Estadísticas de ausentismo** — pacientes con más cancelaciones o inasistencias, visible para recepción

## Pacientes

- [ ] **Autocompletado al agendar** — reemplazar el `<select>` de paciente por un campo con búsqueda tipo Select2 (recepción con cientos de pacientes lo agradecerá)
- [ ] **Foto o avatar de paciente** — ayuda a terapeutas a identificar visualmente a sus pacientes

## Técnico

- [ ] **Almacenamiento externo para media (S3)** — los documentos subidos viven dentro del contenedor Docker y se pierden en cada redeploy; conectar a S3 o similar es crítico
- [x] **Respaldo automático de BD** — GitHub Actions corre cada domingo, hace pg_dump de producción y guarda en rama `backups` (últimos 4 respaldos)
- [ ] **Paginación en listas grandes** — lista de pacientes y bitácora se vuelven lentas con cientos de registros

## Seguridad / acceso

- [ ] **Forzar cambio de contraseña en primer login** — las contraseñas iniciales de empresa son predecibles; obligar a cambiarla al primer acceso
- [ ] **Logs de acceso por empresa** — registrar cuándo y desde dónde se conectó cada usuario empresa
