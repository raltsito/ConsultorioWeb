from django.shortcuts import render, redirect, get_object_or_404
from .models import Paciente, Cita
from .forms import PacienteForm , CitaForm
from django.utils import timezone  
from django.db.models import Q    
from .utils import sincronizar_google_sheet 
from django.contrib.auth.decorators import login_required
import unicodedata
from .forms import CitaForm
from django.contrib import messages 
from django.http import JsonResponse
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
def quitar_tildes(texto):
    if not texto:
        return ""
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto))
                   if unicodedata.category(c) != 'Mn').lower()

@login_required
def home(request):
    from django.utils import timezone
    hoy = timezone.now().date()
    mes_actual = timezone.now().month
    
    # IMPORTANTE: Asegúrate de importar CitaForm si vas a usar el modal
    from .forms import CitaForm 

    # 1. ESTADÍSTICAS
    citas_hoy_count = Cita.objects.filter(fecha=hoy).count()
    
    # CORRECCIÓN 1: Usamos 'estatus' en lugar de 'estado'
    pendientes_count = Cita.objects.filter(
        fecha__lte=hoy, 
        estatus='programada' # <--- AQUÍ CAMBIÓ
    ).count()
    
    pacientes_nuevos = Paciente.objects.filter(
        fecha_registro__month=mes_actual
    ).count()

    # 2. PRÓXIMAS CITAS
    # CORRECCIÓN 2: Usamos 'estatus' y ordenamos por 'hora' (no hora_inicio)
    proximas_citas = Cita.objects.filter(
        fecha__gte=hoy,
        estatus='programada' # <--- AQUÍ CAMBIÓ
    ).order_by('fecha', 'hora')[:5] # <--- AQUÍ CAMBIÓ (era hora_inicio)

    return render(request, 'clinica/home.html', {
        'citas_hoy': citas_hoy_count,
        'pendientes': pendientes_count,
        'pacientes_nuevos': pacientes_nuevos,
        'proximas_citas': proximas_citas,
        'hoy': hoy,
        'form': CitaForm()
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

# --- Agrega esto al final de clinica/views.py ---

@login_required
def vista_calendario(request):
    return render(request, 'clinica/calendario.html')

@login_required
def calendario_citas(request):
    """API que devuelve las citas en formato JSON para FullCalendar"""
    from django.http import JsonResponse
    from datetime import datetime
    
    # Obtenemos todas las citas activas
    citas = Cita.objects.filter(estatus__in=['programada', 'confirmada', 'asistio'])
    
    eventos = []
    for cita in citas:
        # FullCalendar necesita fecha y hora combinadas
        start = datetime.combine(cita.fecha, cita.hora)
        
        # Si no tienes hora_fin, calculamos 1 hora por defecto
        # (Si ya tienes hora_fin en tu modelo, úsalo: cita.hora_fin)
        from datetime import timedelta
        end = start + timedelta(hours=1) 

        # Colores según estatus
        color = '#3788d8' # Azul default
        if cita.estatus == 'asistio':
            color = '#28a745' # Verde
        elif cita.estatus == 'programada':
            color = '#26C6DA' # Tu color INTRA Primary

        eventos.append({
            'title': f"{cita.paciente.nombre} ({cita.terapeuta})",
            'start': start.isoformat(),
            'end': end.isoformat(),
            'color': color,
            'url': f"/pacientes/{cita.paciente.id}/" # Al dar click, lleva al paciente
        })

    return JsonResponse(eventos, safe=False)
# En clinica/views.py

@login_required
def crear_cita(request):
    if request.method == 'POST':
        form = CitaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Cita agendada correctamente! ✅')
            return redirect('home')
        else:
            # 👇 AGREGAMOS ESTO PARA VERIFICAR EN CONSOLA
            print("ERRORES DETECTADOS:", form.errors) 
            
            # Recorremos los errores y los mandamos a la pantalla
            for field, errors in form.errors.items():
                for error in errors:
                    # Mensaje limpio para el usuario
                    messages.error(request, f" {error}")
    
    return redirect('home')

def verificar_disponibilidad(request):
    """
    API ultra-rápida para consultar disponibilidad en tiempo real via AJAX.
    """
    fecha = request.GET.get('fecha')
    hora = request.GET.get('hora')
    consultorio_id = request.GET.get('consultorio')
    terapeuta_id = request.GET.get('terapeuta')
    exclude_id = request.GET.get('exclude_id')
    if not (fecha and hora and consultorio_id):
        return JsonResponse({'status': 'error', 'msg': 'Faltan datos'})

    # 1. Validar Horario Laboral (Ejemplo: Lunes a Sábado, 8am a 8pm)
    # Convertimos la hora string a objeto time
    hora_obj = datetime.strptime(hora, '%H:%M').time()
    hora_apertura = datetime.strptime('08:00', '%H:%M').time()
    hora_cierre = datetime.strptime('20:00', '%H:%M').time()
    
    if not (hora_apertura <= hora_obj <= hora_cierre):
        return JsonResponse({
            'available': False, 
            'msg': ' Fuera de horario laboral (8:00 AM - 8:00 PM)'
        })

    # 2. Validar Choque de Consultorio
    ocupado = Cita.objects.filter(
        consultorio_id=consultorio_id,
        fecha=fecha,
        hora=hora,
        estatus='programada'
    ).exists()

    if ocupado:
        return JsonResponse({
            'available': False, 
            'msg': 'Consultorio ocupado a esta hora.'
        })
        return JsonResponse({'available': True, 'msg': 'Disponible'})
    query_consultorio = Cita.objects.filter(
        consultorio_id=consultorio_id,
        fecha=fecha_obj,
        hora=hora_obj,
        estatus='programada'
    )
    if exclude_id: # Si nos pasaron un ID, lo excluimos
        query_consultorio = query_consultorio.exclude(id=exclude_id)
        
    if query_consultorio.exists():
         return JsonResponse({'available': False, 'msg': '⛔ El consultorio está ocupado.'})

    # AL VALIDAR EL TERAPEUTA:
    query_terapeuta = Cita.objects.filter(
        terapeuta_id=terapeuta_id,
        fecha=fecha_obj,
        hora=hora_obj,
        estatus='programada'
    )
    if exclude_id:
        query_terapeuta = query_terapeuta.exclude(id=exclude_id)

    if query_terapeuta.exists():
        return JsonResponse({'available': False, 'msg': '⚠️ El terapeuta ya tiene otra cita.'})

    return JsonResponse({'available': True, 'msg': '✅ Disponible'})

@login_required
def editar_cita(request, cita_id):
    # 1. Buscamos la cita o damos error 404 si no existe
    cita = get_object_or_404(Cita, id=cita_id)
    
    if request.method == 'POST':
        # 2. Cargamos el formulario con los datos nuevos (POST) y la instancia vieja (cita)
        form = CitaForm(request.POST, instance=cita)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Cita actualizada correctamente! 🔄')
            
            # Inteligencia: ¿A dónde regresamos?
            # Si venimos del expediente del paciente, regresamos ahí. Si no, al home.
            origen = request.GET.get('next', 'home')
            if origen == 'paciente':
                return redirect('detalle_paciente', paciente_id=cita.paciente.id)
            return redirect('home')
        else:
             messages.error(request, '⚠️ Corrige los errores en el formulario.')
    else:
        # 3. Si es GET, mostramos el formulario lleno con los datos actuales
        form = CitaForm(instance=cita)

    return render(request, 'clinica/editar_cita.html', {
        'form': form, 
        'cita': cita
    })