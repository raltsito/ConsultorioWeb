from django import forms
from django.contrib import admin
from .models import AccesoDirectoPortal, Empresa, Host, HostChecklistTask, Paciente, Cita, Terapeuta, Consultorio, Division, Servicio, BloqueoAgendaTerapeuta, RecursoPropio
from .models import Horario

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


@admin.register(HostChecklistTask)
class HostChecklistTaskAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'etiqueta', 'urgente', 'activo', 'orden')
    list_filter = ('activo', 'urgente')
    search_fields = ('titulo', 'subtitulo', 'etiqueta')
    filter_horizontal = ('hosts',)


class PacienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'telefono', 'empresa', 'servicio_inicial', 'fecha_registro')
    list_filter = ('empresa',)
    search_fields = ('nombre',)

class CitaAdmin(admin.ModelAdmin):
    list_display = ('paciente', 'fecha', 'hora', 'tipo_paciente', 'terapeuta', 'estatus')
    list_filter = ('fecha', 'tipo_paciente', 'estatus', 'terapeuta', 'consultorio')

admin.site.register(Paciente, PacienteAdmin)
admin.site.register(Cita, CitaAdmin)

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


@admin.register(RecursoPropio)
class RecursoPropioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'nombre_archivo', 'subido_por', 'creado_en')
    search_fields = ('nombre', 'descripcion', 'nombre_archivo')

    @admin.display(description='Archivo actual')
    def resumen_archivo(self, obj):
        if not obj or not obj.nombre_archivo:
            return 'No hay archivo cargado.'
        return f'{obj.nombre_archivo} | {obj.actualizado_en:%d/%m/%Y %H:%M}'
