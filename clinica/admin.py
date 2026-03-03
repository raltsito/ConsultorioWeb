from django.contrib import admin
from .models import Paciente, Cita, Terapeuta, Consultorio, Division, Servicio
from .models import Horario

admin.site.register(Terapeuta)
admin.site.register(Consultorio)
admin.site.register(Division)
admin.site.register(Servicio)

class PacienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'telefono', 'servicio_inicial', 'fecha_registro')
    search_fields = ('nombre',)

class CitaAdmin(admin.ModelAdmin):
    list_display = ('paciente', 'fecha', 'hora', 'terapeuta', 'estatus')
    list_filter = ('fecha', 'estatus', 'terapeuta', 'consultorio')

admin.site.register(Paciente, PacienteAdmin)
admin.site.register(Cita, CitaAdmin)

@admin.register(Horario)
class HorarioAdmin(admin.ModelAdmin):
    list_display = ('terapeuta', 'dia', 'hora_inicio', 'hora_fin')
    list_filter = ('terapeuta', 'dia')