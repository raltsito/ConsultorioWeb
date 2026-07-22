from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from clinica import views as clinica_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    path('accounts/', include('django.contrib.auth.urls')),
    
    
    path('', clinica_views.home, name='home'),
    path('privacidad/', clinica_views.aviso_privacidad, name='aviso_privacidad'),
    path('politicas-atencion/', clinica_views.politicas_atencion, name='politicas_atencion'),
    path('terminos/', clinica_views.terminos_condiciones, name='terminos_condiciones'),
    path('manual/actualizar/', clinica_views.actualizar_manual_portal, name='actualizar_manual_portal'),
    path('pacientes/', clinica_views.lista_pacientes, name='lista_pacientes'),
    path('pacientes/nuevo/', clinica_views.registrar_paciente, name='registrar_paciente'),
    path('pacientes/<int:paciente_id>/', clinica_views.detalle_paciente, name='detalle_paciente'),
    path('pacientes/<int:paciente_id>/editar/', clinica_views.editar_paciente, name='editar_paciente'),
    path('pacientes/<int:paciente_id>/division/', clinica_views.asignar_division_paciente, name='asignar_division_paciente'),
    path('pacientes/<int:paciente_id>/agendar/', clinica_views.agendar_cita, name='agendar_cita'),
    path('crear-cita/', clinica_views.crear_cita, name='crear_cita'),
    path('citas/tardias/', clinica_views.citas_tardias, name='citas_tardias'),
    path('expositor/solicitar/', clinica_views.solicitar_horas_expositor, name='solicitar_horas_expositor'),
    path('expositor/<int:solicitud_id>/responder/', clinica_views.responder_horas_expositor, name='responder_horas_expositor'),
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
    path('portal-medico/expedientes/<int:paciente_id>/instrumentos/generar/', clinica_views.generar_envio_instrumento, name='generar_envio_instrumento'),
    path('portal-medico/expedientes/<int:paciente_id>/instrumentos/raven/', clinica_views.registrar_resultado_raven, name='registrar_resultado_raven'),
    path('portal-medico/expedientes/<int:paciente_id>/instrumentos/<int:envio_id>/resultado/', clinica_views.resultado_envio_instrumento, name='resultado_envio_instrumento'),
    path('portal-medico/expedientes-grupales/', clinica_views.expedientes_grupales_lista, name='expedientes_grupales_lista'),
    path('portal-medico/expedientes-grupales/<int:expediente_id>/', clinica_views.expediente_grupal_detalle, name='expediente_grupal_detalle'),
    path('portal-medico/documentos/<int:doc_id>/', clinica_views.descargar_documento, name='descargar_documento'),
    path('portal-medico/bloqueos/nuevo/', clinica_views.crear_bloqueo_terapeuta, name='crear_bloqueo_terapeuta'),
    path('portal-medico/bloqueos/<int:bloqueo_id>/eliminar/', clinica_views.eliminar_bloqueo_terapeuta, name='eliminar_bloqueo_terapeuta'),
    path('portal-medico/confirmar-nomina/<int:corte_id>/', clinica_views.confirmar_nomina_terapeuta, name='confirmar_nomina_terapeuta'),
    path('portal-medico/instrumentos/', clinica_views.catalogo_instrumentos, name='catalogo_instrumentos'),
    path('portal-medico/recursos/', clinica_views.recursos_propios, name='recursos_propios'),
    path('portal-medico/recursos/<int:recurso_id>/descargar/', clinica_views.descargar_recurso_propio, name='descargar_recurso_propio'),
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
    path('incidentes/responder/', clinica_views.responder_incidente, name='responder_incidente'),
    path('incidentes/', clinica_views.lista_incidentes, name='lista_incidentes'),

    # Portal Empresa
    path('empresa/', clinica_views.portal_empresa, name='portal_empresa'),
    path('empresa/registrar-paciente/', clinica_views.registrar_paciente_empresa, name='registrar_paciente_empresa'),
    path('empresa/agendar-cita/', clinica_views.agendar_cita_empresa, name='agendar_cita_empresa'),
    path('empresa/citas-en-proceso/', clinica_views.citas_en_proceso_empresa, name='citas_en_proceso_empresa'),
    path('empresa/terapeutas-paciente/', clinica_views.terapeutas_paciente_empresa, name='terapeutas_paciente_empresa'),

    # Instrumentos — link público para que el paciente conteste (sin login)
    path('instrumentos/<uuid:token>/', clinica_views.responder_instrumento, name='responder_instrumento'),

    # Portal Host
    path('host/', clinica_views.portal_host, name='portal_host'),
    path('host/checklist/', clinica_views.checklist_host_config, name='checklist_host_config'),

    # Portal Consultoria
    path('consultoria/', clinica_views.portal_consultoria, name='portal_consultoria'),
    path('consultoria/manual/', clinica_views.descargar_manual_portal_consultoria, name='descargar_manual_portal_consultoria'),
    path('consultoria/mi-disponibilidad/', clinica_views.mi_disponibilidad_consultoria, name='mi_disponibilidad_consultoria'),
    path('consultoria/expedientes/', clinica_views.expedientes_consultoria, name='expedientes_consultoria'),
    path('consultoria/expedientes/nuevo/', clinica_views.registrar_paciente_consultoria, name='registrar_paciente_consultoria'),
    path('consultoria/expedientes/<int:paciente_id>/', clinica_views.expediente_consultoria_detalle, name='expediente_consultoria_detalle'),
    path('consultoria/solicitar-cita/', clinica_views.solicitar_cita_consultoria, name='solicitar_cita_consultoria'),
    path('consultoria/bloqueos/nuevo/', clinica_views.crear_bloqueo_consultoria, name='crear_bloqueo_consultoria'),
    path('consultoria/bloqueos/<int:bloqueo_id>/eliminar/', clinica_views.eliminar_bloqueo_consultoria, name='eliminar_bloqueo_consultoria'),
    path('consultoria/confirmar-nomina/<int:corte_id>/', clinica_views.confirmar_nomina_consultoria, name='confirmar_nomina_consultoria'),
    path('consultoria/recursos/', clinica_views.recursos_consultoria, name='recursos_consultoria'),
    path('consultoria/recursos/<int:recurso_id>/descargar/', clinica_views.descargar_recurso_consultoria, name='descargar_recurso_consultoria'),
    path('consultoria/expositor/solicitar/', clinica_views.solicitar_horas_expositor_consultoria, name='solicitar_horas_expositor_consultoria'),
    path('consultoria/incidentes/reportar/', clinica_views.reportar_incidente_consultoria, name='reportar_incidente_consultoria'),

    # Portal Direccion Comercial
    path('portal-direccion-comercial/', clinica_views.portal_direccion_comercial, name='portal_direccion_comercial'),

    # Portal Lider de Operaciones Clinicas
    path('portal-operaciones-clinicas/', clinica_views.portal_lider_operaciones_clinicas, name='portal_lider_operaciones_clinicas'),

    # Catálogo de Terapeutas
    path('catalogo-terapeutas/', clinica_views.catalogo_terapeutas, name='catalogo_terapeutas'),
    path('api/catalogo/', clinica_views.api_catalogo_list, name='api_catalogo_list'),
    path('api/catalogo/<int:perfil_id>/', clinica_views.api_catalogo_detail, name='api_catalogo_detail'),
    path('api/terapeutas-activos/', clinica_views.api_terapeutas_activos, name='api_terapeutas_activos'),

    # Notas de Recepción
    path('notas-recepcion/agregar/', clinica_views.agregar_nota_recepcion, name='agregar_nota_recepcion'),
    path('notas-recepcion/<int:nota_id>/eliminar/', clinica_views.eliminar_nota_recepcion, name='eliminar_nota_recepcion'),
    path('notas-recepcion/<int:nota_id>/reaccion/', clinica_views.toggle_reaccion_nota, name='toggle_reaccion_nota'),
    path('notas-recepcion/<int:nota_id>/comentar/', clinica_views.agregar_comentario_nota, name='agregar_comentario_nota'),

    # Notificaciones terapeuta
    path('api/notificaciones-terapeuta/', clinica_views.api_notificaciones_terapeuta, name='api_notificaciones_terapeuta'),
    path('api/notificaciones-terapeuta/leer/', clinica_views.marcar_notificaciones_leidas, name='marcar_notificaciones_leidas'),

    # API endpoints externos (protegidos con X-API-Key)
    path('api/notas-recepcion/', clinica_views.api_notas_recepcion, name='api_notas_recepcion'),
    path('api/notas-recepcion/<int:nota_id>/', clinica_views.api_nota_recepcion_detail, name='api_nota_recepcion_detail'),
    path('api/nomina-semanal/', clinica_views.api_nomina_semanal, name='api_nomina_semanal'),
    path('api/reporte-general/', clinica_views.api_reporte_general, name='api_reporte_general'),
    path('api/disponibilidad-semanal/', clinica_views.api_disponibilidad_semanal, name='api_disponibilidad_semanal'),

    # Trazabilidad
    path('trazabilidad/', clinica_views.trazabilidad_admin, name='trazabilidad_admin'),

    # WhatsApp
    path('api/whatsapp/webhook/',
         clinica_views.whatsapp_webhook, name='whatsapp_webhook'),
    path('api/whatsapp/trigger-cron/',
         clinica_views.whatsapp_trigger_cron, name='whatsapp_trigger_cron'),
    path('api/whatsapp/manual/<int:cita_id>/<str:tipo>/',
         clinica_views.whatsapp_enviar_manual, name='whatsapp_manual'),
    path('api/whatsapp/reactivacion/',
         clinica_views.whatsapp_reactivacion_seguimiento, name='whatsapp_reactivacion'),
    path('api/whatsapp/lote/',
         clinica_views.whatsapp_enviar_lote, name='whatsapp_enviar_lote'),
    path('pacientes/sin-seguimiento/',
         clinica_views.pacientes_sin_seguimiento, name='pacientes_sin_seguimiento'),
    path('whatsapp/recordatorios/',
         clinica_views.whatsapp_recordatorios, name='whatsapp_recordatorios'),
    path('api/whatsapp/automatizacion/toggle/',
         clinica_views.whatsapp_toggle_automatizacion, name='whatsapp_toggle_automatizacion'),
    path('api/whatsapp/conversacion/',
         clinica_views.whatsapp_conversacion, name='whatsapp_conversacion'),
    path('api/whatsapp/conversacion/atendido/',
         clinica_views.whatsapp_marcar_atendido, name='whatsapp_marcar_atendido'),


     # Demos WhatsApp (acceso exclusivo SUPERADMIN)
     path('demos/whatsapp/',
          clinica_views.demos_whatsapp, name='demos_whatsapp'),
     path('api/demos/whatsapp/lote/',
          clinica_views.demos_whatsapp_enviar_lote, name='demos_whatsapp_enviar_lote'),
     path('demos/pago/dorothea/',
          clinica_views.demo_pago_dorothea, name='demo_pago_dorothea'),



     # URL para dar de alta al paciente
     path('pacientes/<int:paciente_id>/toggle-alta/',
          clinica_views.toggle_alta_paciente, name='toggle_alta_paciente'),

     # URL para suspender a un paciente
     path('paciente/suspender/<int:id>/',
          clinica_views.suspender_paciente, name='suspender_paciente'),


]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
