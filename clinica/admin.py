from django.contrib import admin
from .models import Empresa, Paciente, Cita, Terapeuta, Consultorio, Division, Servicio, BloqueoAgendaTerapeuta
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
