from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from clinica import views as clinica_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    
    path('accounts/', include('django.contrib.auth.urls')),
    
    
    path('', clinica_views.home, name='home'),
    path('manual/actualizar/', clinica_views.actualizar_manual_portal, name='actualizar_manual_portal'),
    path('pacientes/', clinica_views.lista_pacientes, name='lista_pacientes'),
    path('pacientes/nuevo/', clinica_views.registrar_paciente, name='registrar_paciente'),
    path('pacientes/<int:paciente_id>/', clinica_views.detalle_paciente, name='detalle_paciente'),
    path('pacientes/<int:paciente_id>/editar/', clinica_views.editar_paciente, name='editar_paciente'),
    path('pacientes/<int:paciente_id>/division/', clinica_views.asignar_division_paciente, name='asignar_division_paciente'),
    path('pacientes/<int:paciente_id>/agendar/', clinica_views.agendar_cita, name='agendar_cita'),
    path('crear-cita/', clinica_views.crear_cita, name='crear_cita'),
    path('calendario/', clinica_views.vista_calendario, name='vista_calendario'),
    path('api/citas/', clinica_views.calendario_citas, name='calendario_citas'),
    path('api/verificar-disponibilidad/', clinica_views.verificar_disponibilidad, name='verificar_disponibilidad'),
    path('citas/<int:cita_id>/editar/', clinica_views.editar_cita, name='editar_cita'),
    path('citas/<int:cita_id>/eliminar/', clinica_views.eliminar_cita, name='eliminar_cita'),
    path('pacientes/<int:paciente_id>/eliminar/', clinica_views.eliminar_paciente, name='eliminar_paciente'),
    path('api/citas-calendario/', clinica_views.api_citas_calendario, name='api_citas_calendario'),
    path('api/terapeutas-paciente/', clinica_views.api_terapeutas_paciente, name='api_terapeutas_paciente'),
    path('api/pacientes-relacionados/', clinica_views.api_pacientes_relacionados, name='api_pacientes_relacionados'),
    path('portal-medico/', clinica_views.portal_terapeuta, name='portal_terapeuta'),
    path('portal-medico/manual/', clinica_views.descargar_manual_portal_medico, name='descargar_manual_portal_medico'),
    path('portal-medico/mi-disponibilidad/', clinica_views.mi_disponibilidad_terapeuta, name='mi_disponibilidad_terapeuta'),
    path('portal-medico/expedientes/', clinica_views.expedientes_terapeuta, name='expedientes_terapeuta'),
    path('portal-medico/expedientes/nuevo/', clinica_views.registrar_paciente_terapeuta, name='registrar_paciente_terapeuta'),
    path('portal-medico/expedientes/<int:paciente_id>/', clinica_views.expediente_terapeuta_detalle, name='expediente_terapeuta_detalle'),
    path('portal-medico/expedientes-grupales/', clinica_views.expedientes_grupales_lista, name='expedientes_grupales_lista'),
    path('portal-medico/expedientes-grupales/<int:expediente_id>/', clinica_views.expediente_grupal_detalle, name='expediente_grupal_detalle'),
    path('portal-medico/documentos/<int:doc_id>/', clinica_views.descargar_documento, name='descargar_documento'),
    path('portal-medico/bloqueos/nuevo/', clinica_views.crear_bloqueo_terapeuta, name='crear_bloqueo_terapeuta'),
    path('portal-medico/bloqueos/<int:bloqueo_id>/eliminar/', clinica_views.eliminar_bloqueo_terapeuta, name='eliminar_bloqueo_terapeuta'),
    path('portal-medico/confirmar-nomina/<int:corte_id>/', clinica_views.confirmar_nomina_terapeuta, name='confirmar_nomina_terapeuta'),
    path('mi-portal/', clinica_views.portal_paciente, name='portal_paciente'),
    path('mi-portal/solicitar/', clinica_views.solicitar_cita_paciente, name='solicitar_cita_paciente'),
    path('solicitud/rechazar/<int:solicitud_id>/', clinica_views.rechazar_solicitud, name='rechazar_solicitud'),
    path('mi-portal-doc/solicitar/', clinica_views.solicitar_cita_terapeuta, name='solicitar_cita_terapeuta'),
    path('api/disponibilidad-terapeuta/', clinica_views.api_disponibilidad_terapeuta, name='api_disponibilidad'),
    path('api/consultorios-por-horario/', clinica_views.api_consultorios_por_horario, name='api_consultorios_por_horario'),
    path('api/penalizacion-paciente/', clinica_views.api_penalizacion_paciente, name='api_penalizacion_paciente'),
    path('api/sin-reagendar/', clinica_views.api_sin_reagendar, name='api_sin_reagendar'),
    path('precios-servicios/', clinica_views.precios_servicios, name='precios_servicios'),
    path('citas/<int:cita_id>/checkout/', clinica_views.checkout_cita, name='checkout_cita'),
    path('bitacora/', clinica_views.bitacora_diaria, name='bitacora_diaria'),
    path('reporte-general/', clinica_views.reporte_general, name='reporte_general'),
    path('ausentismo/', clinica_views.estadisticas_ausentismo, name='estadisticas_ausentismo'),
    path('nomina/', clinica_views.nomina_lista, name='nomina_lista'),
    path('nomina/exportar-reporte-general/', clinica_views.nomina_exportar_reporte_general, name='nomina_exportar_reporte_general'),
    path('nomina/exportar-dispersion/', clinica_views.nomina_exportar_dispersion, name='nomina_exportar_dispersion'),
    path('nomina/todos/', clinica_views.nomina_todos_detalles, name='nomina_todos_detalles'),
    path('nomina/linea/<int:linea_id>/editar/', clinica_views.nomina_editar_linea, name='nomina_editar_linea'),
    path('nomina/bono/<int:bono_id>/editar/', clinica_views.nomina_editar_bono_extra, name='nomina_editar_bono_extra'),
    path('nomina/tabuladores/', clinica_views.tabuladores_config, name='tabuladores_config'),
    path('nomina/tabuladores/categoria/<int:categoria_id>/editar/', clinica_views.tabuladores_editar_categoria, name='tabuladores_editar_categoria'),
    path('nomina/tabuladores/regla/<int:regla_id>/editar/', clinica_views.tabuladores_editar_regla, name='tabuladores_editar_regla'),
    path('nomina/tabuladores/regla/<int:terapeuta_id>/crear/', clinica_views.tabuladores_crear_regla, name='tabuladores_crear_regla'),
    path('nomina/<int:terapeuta_id>/', clinica_views.nomina_detalle, name='nomina_detalle'),
    path('nomina/<int:terapeuta_id>/calcular/', clinica_views.nomina_calcular, name='nomina_calcular'),
    path('nomina/corte/<int:corte_id>/aprobar/', clinica_views.nomina_aprobar, name='nomina_aprobar'),
    path('nomina/corte/<int:corte_id>/bono/', clinica_views.nomina_agregar_bono, name='nomina_agregar_bono'),
    path('disponibilidad/', clinica_views.disponibilidad_semanal, name='disponibilidad_semanal'),
    path('disponibilidad/agregar/', clinica_views.agregar_disponibilidad, name='agregar_disponibilidad'),
    path('disponibilidad/eliminar/<int:horario_id>/', clinica_views.eliminar_disponibilidad, name='eliminar_disponibilidad'),

    # Reagendos
    path('citas/<int:cita_id>/solicitar-reagendo/', clinica_views.solicitar_reagendo, name='solicitar_reagendo'),
    path('reagendo/<int:solicitud_id>/aprobar/', clinica_views.aprobar_reagendo, name='aprobar_reagendo'),
    path('reagendo/<int:solicitud_id>/rechazar/', clinica_views.rechazar_reagendo, name='rechazar_reagendo'),

    # Reportes e Incidentes
    path('incidentes/reportar/', clinica_views.reportar_incidente, name='reportar_incidente'),
    path('incidentes/', clinica_views.lista_incidentes, name='lista_incidentes'),

    # Portal Empresa
    path('empresa/', clinica_views.portal_empresa, name='portal_empresa'),
    path('empresa/registrar-paciente/', clinica_views.registrar_paciente_empresa, name='registrar_paciente_empresa'),
    path('empresa/agendar-cita/', clinica_views.agendar_cita_empresa, name='agendar_cita_empresa'),
    path('empresa/citas-en-proceso/', clinica_views.citas_en_proceso_empresa, name='citas_en_proceso_empresa'),
    path('empresa/terapeutas-paciente/', clinica_views.terapeutas_paciente_empresa, name='terapeutas_paciente_empresa'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
