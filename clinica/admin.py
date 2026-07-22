from django import forms
from django.contrib import admin
from .models import AccesoDirectoPortal, Consultoria, DireccionComercial, LiderOperacionesClinicas, Empresa, Host, HostChecklistTask, Paciente, Cita, Terapeuta, Consultorio, Division, Servicio, BloqueoAgendaTerapeuta, RecursoPropio, MensajeWhatsApp, ConfiguracionWhatsApp, MensajeWhatsAppDemo
from .models import Horario
from .models import Instrumento, PreguntaInstrumento, EnvioInstrumento, RespuestaInstrumento

admin.site.register(Terapeuta)
admin.site.register(Consultorio)
admin.site.register(Division)
admin.site.register(Servicio)


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'usuario', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre',)


@admin.register(Host)
class HostAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'usuario', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre', 'usuario__username')


@admin.register(Consultoria)
class ConsultoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'usuario', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre', 'usuario__username')


@admin.register(DireccionComercial)
class DireccionComercialAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'usuario', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre', 'usuario__username')
    filter_horizontal = ('divisiones',)


@admin.register(LiderOperacionesClinicas)
class LiderOperacionesClinicasAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'usuario', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre', 'usuario__username')


@admin.register(HostChecklistTask)
class HostChecklistTaskAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'etiqueta', 'urgente', 'activo', 'orden')
    list_filter = ('activo', 'urgente')
    search_fields = ('titulo', 'subtitulo', 'etiqueta')
    filter_horizontal = ('hosts',)


class PacienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'telefono', 'empresa', 'servicio_inicial', 'fecha_registro','dado_de_alta','fecha_alta')
    list_filter = ('empresa',)
    search_fields = ('nombre',)

class CitaAdmin(admin.ModelAdmin):
    list_display = ('paciente', 'fecha', 'hora', 'tipo_paciente', 'terapeuta', 'estatus')
    list_filter = ('fecha', 'tipo_paciente', 'estatus', 'terapeuta', 'consultorio')

admin.site.register(Paciente, PacienteAdmin)
admin.site.register(Cita, CitaAdmin)


@admin.register(MensajeWhatsApp)
class MensajeWhatsAppAdmin(admin.ModelAdmin):
    list_display = ('paciente', 'tipo', 'origen', 'telefono', 'exitoso', 'enviado_en')
    list_filter = ('tipo', 'origen', 'exitoso')
    search_fields = ('paciente__nombre', 'telefono')
    readonly_fields = ('cita', 'paciente', 'telefono', 'tipo', 'origen', 'enviado_en',
                        'exitoso', 'respuesta_api', 'enviado_por')

    def has_add_permission(self, request):
        return False


@admin.register(MensajeWhatsAppDemo)
class MensajeWhatsAppDemoAdmin(admin.ModelAdmin):
    list_display = ('campana', 'tipo', 'nombre_contacto', 'telefono', 'exitoso', 'enviado_en')
    list_filter = ('campana', 'tipo', 'exitoso')
    search_fields = ('nombre_contacto', 'telefono')
    readonly_fields = ('campana', 'tipo', 'telefono', 'nombre_contacto', 'texto', 'enviado_en',
                        'exitoso', 'respuesta_api', 'enviado_por')

    def has_add_permission(self, request):
        return False


@admin.register(ConfiguracionWhatsApp)
class ConfiguracionWhatsAppAdmin(admin.ModelAdmin):
    list_display = ('automatizacion_activa',)

    def has_add_permission(self, request):
        return not ConfiguracionWhatsApp.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Horario)
class HorarioAdmin(admin.ModelAdmin):
    list_display = ('terapeuta', 'dia', 'hora_inicio', 'hora_fin')
    list_filter = ('terapeuta', 'dia')


@admin.register(BloqueoAgendaTerapeuta)
class BloqueoAgendaTerapeutaAdmin(admin.ModelAdmin):
    list_display = ('terapeuta', 'tipo_bloqueo', 'fecha_inicio', 'fecha_fin', 'activo')
    list_filter = ('tipo_bloqueo', 'activo', 'terapeuta')
    search_fields = ('terapeuta__nombre', 'motivo')


class AccesoDirectoPortalAdminForm(forms.ModelForm):
    archivo = forms.FileField(
        required=False,
        help_text='Sube aqui el archivo vigente del manual del sistema.',
    )

    class Meta:
        model = AccesoDirectoPortal
        fields = ('clave', 'titulo', 'activo')

    def save(self, commit=True):
        instance = super().save(commit=False)
        archivo = self.cleaned_data.get('archivo')
        if archivo:
            instance.nombre_archivo = archivo.name
            instance.tipo_mime = getattr(archivo, 'content_type', '') or 'application/octet-stream'
            instance.contenido = archivo.read()
        if commit:
            instance.save()
        return instance


@admin.register(AccesoDirectoPortal)
class AccesoDirectoPortalAdmin(admin.ModelAdmin):
    form = AccesoDirectoPortalAdminForm
    list_display = ('clave', 'titulo', 'activo', 'actualizado_en')
    list_filter = ('activo', 'clave')
    search_fields = ('titulo', 'nombre_archivo')
    fieldsets = (
        ('Acceso directo', {
            'fields': ('clave', 'titulo', 'activo'),
        }),
        ('Actualizar manual', {
            'fields': ('archivo',),
            'description': 'Sube aqui el archivo que descargaran los terapeutas desde el portal medico.',
        }),
    )
    readonly_fields = ('resumen_archivo',)

    def resumen_archivo(self, obj):
        if obj and obj.nombre_archivo:
            kb = len(obj.contenido) // 1024 if obj.contenido else 0
            return f'{obj.nombre_archivo} ({kb} KB)'
        return '—'
    resumen_archivo.short_description = 'Archivo actual'

    def has_add_permission(self, request):
        return not AccesoDirectoPortal.objects.exists() or super().has_add_permission(request)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.nombre_archivo:
            return ('resumen_archivo',)
        return ()

    def get_fieldsets(self, request, obj=None):
        fieldsets = [
            ('Acceso directo', {
                'fields': ('clave', 'titulo', 'activo'),
            }),
            ('Actualizar manual', {
                'fields': ('archivo',),
                'description': 'Sube aqui el archivo que descargaran los terapeutas desde el portal medico.',
            }),
        ]
        if obj and obj.nombre_archivo:
            fieldsets.append(('Archivo actual', {'fields': ('resumen_archivo',)}))
        return fieldsets



class RespuestaInstrumentoInline(admin.TabularInline):
    model = RespuestaInstrumento
    extra = 0
    fields = ('pregunta', 'valor', 'valor_numerico')
    readonly_fields = ('pregunta', 'valor', 'valor_numerico')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(EnvioInstrumento)
class EnvioInstrumentoAdmin(admin.ModelAdmin):
    list_display = ('instrumento', 'paciente', 'estado', 'puntaje_total', 'creado_en', 'respondido_en')
    list_filter = ('estado', 'instrumento')
    search_fields = ('paciente__nombre', 'instrumento__nombre', 'token')
    readonly_fields = (
        'token', 'instrumento', 'paciente', 'generado_por', 'creado_en', 'respondido_en',
        'puntaje_total', 'interpretacion', 'resultado_detalle',
    )
    inlines = [RespuestaInstrumentoInline]

    def has_add_permission(self, request):
        return False


@admin.register(RecursoPropio)
class RecursoPropioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'nombre_archivo', 'subido_por', 'creado_en')
    search_fields = ('nombre', 'descripcion', 'nombre_archivo')

    @admin.display(description='Archivo actual')
    def resumen_archivo(self, obj):
        if not obj or not obj.nombre_archivo:
            return 'No hay archivo cargado.'
        return f'{obj.nombre_archivo} | {obj.actualizado_en:%d/%m/%Y %H:%M}'

# --- Registro forzado para que aparezcan ---
@admin.register(Instrumento)
class InstrumentoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'clave', 'activo')

@admin.register(PreguntaInstrumento)
class PreguntaInstrumentoAdmin(admin.ModelAdmin):
    list_display = ('instrumento', 'texto', 'orden')


