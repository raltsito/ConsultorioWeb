from django.urls import path

from . import views

app_name = "ventas"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("captadores/", views.captadores_lista, name="captadores_lista"),
    path("captadores/nuevo/", views.captador_nuevo, name="captador_nuevo"),
    path("captadores/<int:pk>/", views.captador_detalle, name="captador_detalle"),
    path("captadores/<int:pk>/editar/", views.captador_editar, name="captador_editar"),
    path("captadores/<int:pk>/desactivar/", views.captador_desactivar, name="captador_desactivar"),
    path("captadores/<int:pk>/reactivar/", views.captador_reactivar, name="captador_reactivar"),
    path("captadores/<int:pk>/qr.png", views.captador_qr, name="captador_qr"),
    path("mi-qr/", views.mi_qr, name="mi_qr"),
    path("validar/", views.validar_codigo, name="validar_codigo"),
    path("captacion/<str:token>/", views.validar_token, name="validar_token"),
    path("captaciones/", views.captaciones_lista, name="captaciones_lista"),
    path("captaciones/nueva/", views.captacion_nueva, name="captacion_nueva"),
    path("captaciones/<int:pk>/", views.captacion_detalle, name="captacion_detalle"),
    path(
        "captaciones/<int:pk>/aprobar/",
        views.captacion_aprobar,
        name="captacion_aprobar",
    ),
    path(
        "captaciones/<int:pk>/rechazar/",
        views.captacion_rechazar,
        name="captacion_rechazar",
    ),
    path(
        "captaciones/elegibilidad/<int:paciente_id>/",
        views.elegibilidad_paciente,
        name="elegibilidad_paciente",
    ),
    path(
        "comisiones/",
        views.comisiones_panel,
        name="comisiones_panel",
    ),
    path(
        "comisiones/<int:pk>/",
        views.comision_detalle,
        name="comision_detalle",
    ),
    path(
        "liquidaciones/crear/",
        views.liquidacion_crear,
        name="liquidacion_crear",
    ),
    path(
        "liquidaciones/",
        views.liquidaciones_panel,
        name="liquidaciones_panel",
    ),
    path(
        "liquidaciones/<int:pk>/",
        views.liquidacion_detalle,
        name="liquidacion_detalle",
    ),
    path(
        "liquidaciones/<int:pk>/agregar/",
        views.liquidacion_agregar,
        name="liquidacion_agregar",
    ),
    path(
        "liquidaciones/<int:pk>/retirar/<int:comision_id>/",
        views.liquidacion_retirar,
        name="liquidacion_retirar",
    ),
    path(
        "liquidaciones/<int:pk>/cancelar/",
        views.liquidacion_cancelar,
        name="liquidacion_cancelar",
    ),
    path(
        "liquidaciones/<int:pk>/registrar-pago/",
        views.liquidacion_registrar_pago,
        name="liquidacion_registrar_pago",
    ),
]
