from django.contrib import admin

from .models import (
    Captacion,
    Captador,
    CodigoCaptacion,
    ComisionCaptacion,
    EventoCaptacion,
    EventoCaptador,
    IntentoCaptacionRechazado,
)


class CodigoCaptacionInline(admin.TabularInline):
    model = CodigoCaptacion
    extra = 0
    can_delete = False
    readonly_fields = (
        "token",
        "activo",
        "creado_en",
        "revocado_en",
        "motivo_revocacion",
    )


@admin.register(Captador)
class CaptadorAdmin(admin.ModelAdmin):
    list_display = ("nombre_display", "tipo", "activo", "creado_en")
    list_filter = ("tipo", "activo")
    search_fields = ("usuario__username", "empresa__nombre", "nombre_externo")
    readonly_fields = ("creado_en", "desactivado_en")
    inlines = [CodigoCaptacionInline]


@admin.register(CodigoCaptacion)
class CodigoCaptacionAdmin(admin.ModelAdmin):
    list_display = ("captador", "activo", "creado_en", "revocado_en")
    list_filter = ("activo",)
    readonly_fields = (
        "captador",
        "token",
        "activo",
        "creado_en",
        "revocado_en",
        "motivo_revocacion",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EventoCaptador)
class EventoCaptadorAdmin(admin.ModelAdmin):
    list_display = ("captador", "accion", "usuario", "creado_en")
    readonly_fields = ("captador", "accion", "usuario", "detalle", "creado_en")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Captacion)
class CaptacionAdmin(admin.ModelAdmin):
    list_display = (
        "paciente",
        "captador_nombre_snapshot",
        "captador_tipo_snapshot",
        "fecha_captacion",
        "estado",
    )
    list_filter = ("estado", "captador__tipo", "fecha_captacion")
    search_fields = ("paciente__nombre", "captador_nombre_snapshot", "codigo__token")
    readonly_fields = (
        "paciente",
        "captador",
        "codigo",
        "fecha_captacion",
        "registrado_por",
        "estado",
        "canal",
        "captador_nombre_snapshot",
        "captador_tipo_snapshot",
        "creado_en",
        "actualizado_en",
        "porcentaje_comision",
        "decidido_por",
        "decidido_en",
        "motivo_rechazo",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IntentoCaptacionRechazado)
class IntentoCaptacionRechazadoAdmin(admin.ModelAdmin):
    list_display = ("paciente", "motivo", "registrado_por", "creado_en")
    list_filter = ("motivo", "creado_en")
    search_fields = ("paciente__nombre", "registrado_por__username")
    readonly_fields = ("paciente", "motivo", "registrado_por", "creado_en")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EventoCaptacion)
class EventoCaptacionAdmin(admin.ModelAdmin):
    list_display = (
        "captacion",
        "accion",
        "estado_anterior",
        "estado_nuevo",
        "usuario",
        "creado_en",
    )
    list_filter = ("accion", "estado_nuevo", "creado_en")
    readonly_fields = (
        "captacion",
        "accion",
        "usuario",
        "estado_anterior",
        "estado_nuevo",
        "porcentaje_comision",
        "motivo",
        "creado_en",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ComisionCaptacion)
class ComisionCaptacionAdmin(admin.ModelAdmin):
    list_display = (
        "captacion",
        "captador_nombre_snapshot",
        "paciente_nombre_snapshot",
        "porcentaje_aplicado",
        "monto_calculado",
        "moneda",
        "estado",
        "generada_en",
    )
    list_filter = ("estado", "moneda", "generada_en")
    search_fields = (
        "captador_nombre_snapshot",
        "paciente_nombre_snapshot",
        "captacion__paciente__nombre",
    )
    readonly_fields = (
        "captacion",
        "cita_generadora",
        "captador_nombre_snapshot",
        "paciente_nombre_snapshot",
        "porcentaje_aplicado",
        "base_calculo",
        "monto_calculado",
        "moneda",
        "generada_en",
        "estado",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
