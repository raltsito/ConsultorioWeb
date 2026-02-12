from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from clinica import views as clinica_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    
    path('accounts/', include('django.contrib.auth.urls')),
    
    
    path('', clinica_views.home, name='home'),
    path('pacientes/', clinica_views.lista_pacientes, name='lista_pacientes'),
    path('pacientes/nuevo/', clinica_views.registrar_paciente, name='registrar_paciente'),
    path('pacientes/<int:paciente_id>/', clinica_views.detalle_paciente, name='detalle_paciente'),
    path('pacientes/<int:paciente_id>/editar/', clinica_views.editar_paciente, name='editar_paciente'),
    path('pacientes/<int:paciente_id>/agendar/', clinica_views.agendar_cita, name='agendar_cita'),
    path('crear-cita/', clinica_views.crear_cita, name='crear_cita'),
    path('calendario/', clinica_views.vista_calendario, name='vista_calendario'),
    path('api/citas/', clinica_views.calendario_citas, name='calendario_citas'),
    path('api/verificar-disponibilidad/', clinica_views.verificar_disponibilidad, name='verificar_disponibilidad'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)