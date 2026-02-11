from django.shortcuts import render, redirect, get_object_or_404
from .models import Paciente, Cita
from .forms import PacienteForm , CitaForm
from django.utils import timezone  
from django.db.models import Q    
from .utils import sincronizar_google_sheet 
from django.contrib.auth.decorators import login_required
import unicodedata

def quitar_tildes(texto):
    if not texto:
        return ""
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto))
                   if unicodedata.category(c) != 'Mn').lower()

@login_required
def home(request):
    hoy = timezone.now().date()
    
    citas_hoy = Cita.objects.filter(fecha=hoy, estatus='programada').count()
    
    pacientes_nuevos = Paciente.objects.filter(fecha_registro__month=hoy.month).count()
    
    reportes_pendientes = Cita.objects.filter(fecha__lt=hoy, estatus='programada').count()

    return render(request, 'clinica/home.html', {
        'citas_hoy': citas_hoy,
        'pacientes_nuevos': pacientes_nuevos,
        'reportes_pendientes': reportes_pendientes
    })
# Asegúrate de tener esto arriba: from django.db.models import Q

@login_required
def lista_pacientes(request):
    query = request.GET.get('q') 
    
    if query:
        # A. Limpiamos lo que escribió el usuario (Ej: "Ángel" -> "angel")
        q_limpio = quitar_tildes(query)

        # B. Buscamos:
        # - En 'nombre_normalizado' usamos la versión limpia ('angel')
        # - En 'telefono' usamos la versión original (números)
        pacientes = Paciente.objects.filter(
            Q(nombre_normalizado__icontains=q_limpio) | 
            Q(telefono__icontains=query)
        ).order_by('-fecha_registro')
    else:
        pacientes = Paciente.objects.all().order_by('-fecha_registro')

    return render(request, 'clinica/lista_pacientes.html', {'pacientes': pacientes})
@login_required
def registrar_paciente(request):
    if request.method == 'POST':
        form = PacienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('lista_pacientes')
    else:
        form = PacienteForm()
    return render(request, 'clinica/registro_paciente.html', {'form': form})
@login_required
def detalle_paciente(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    citas = paciente.citas.all()
    return render(request, 'clinica/detalle_paciente.html', {
        'paciente': paciente,
        'citas': citas
    })
@login_required
def agendar_cita(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    
    if request.method == 'POST':
        form = CitaForm(request.POST)
        if form.is_valid():
            cita = form.save(commit=False)
            cita.paciente = paciente  # Aquí vinculamos la cita al paciente automáticamente
            cita.save()
            return redirect('detalle_paciente', paciente_id=paciente.id)
    else:
        # Pre-llenamos el terapeuta por defecto si quieres, o lo dejamos vacío
        form = CitaForm(initial={'costo': 500})
    
    return render(request, 'clinica/agendar_cita.html', {'form': form, 'paciente': paciente})
@login_required
def editar_paciente(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    
    if request.method == 'POST':
        # FILES es necesario para recibir archivos (PDFs, fotos)
        form = PacienteForm(request.POST, request.FILES, instance=paciente)
        if form.is_valid():
            form.save()
            return redirect('detalle_paciente', paciente_id=paciente.id)
    else:
        form = PacienteForm(instance=paciente)
    
    return render(request, 'clinica/editar_paciente.html', {'form': form, 'paciente': paciente})
@login_required
def agendar_cita(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    
    if request.method == 'POST':
        form = CitaForm(request.POST)
        if form.is_valid():
            cita = form.save(commit=False)
            cita.paciente = paciente
            cita.save()
            
           
            try:
                sincronizar_google_sheet(cita)
                print("✅ Sincronización exitosa")
            except Exception as e:
                print(f"⚠️ Error al sincronizar con Google: {e}")
            

            return redirect('detalle_paciente', paciente_id=paciente.id)
    else:
        form = CitaForm(initial={'costo': 500})
    
    return render(request, 'clinica/agendar_cita.html', {'form': form, 'paciente': paciente})