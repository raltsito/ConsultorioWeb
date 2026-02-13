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
from .models import Cita, Horario



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
# En clinica/views.py

def detalle_paciente(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    
    # 👇 AQUÍ ESTÁ LA CLAVE: Traer TODAS las citas de este paciente, 
    # ordenadas de la más reciente (o futura) a la más antigua.
    historial = Cita.objects.filter(paciente=paciente).order_by('-fecha', '-hora')

    context = {
        'paciente': paciente,
        'historial': historial, # <--- Pasamos la lista completa al HTML
    }
    return render(request, 'clinica/detalle_paciente.html', context)
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
            messages.success(request, '¡Cita agendada correctamente! ')
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

# En clinica/views.py

def verificar_disponibilidad(request):
    fecha_str = request.GET.get('fecha')
    hora_str = request.GET.get('hora')
    consultorio_id = request.GET.get('consultorio')
    terapeuta_id = request.GET.get('terapeuta')
    exclude_id = request.GET.get('exclude_id') # <--- CLAVE PARA EDITAR

    # 1. Validación básica de datos
    if not (fecha_str and hora_str and consultorio_id and terapeuta_id):
        # Si falta algún dato, no validamos nada todavía, devolvemos success silencioso
        # o un mensaje neutro para no mostrar errores rojos prematuros.
        return JsonResponse({'available': False, 'msg': ''})

    try:
        # 2. Limpieza de formatos (Aquí arreglamos el error de la imagen)
        # Si la hora trae segundos (Ej: "14:30:00"), nos quedamos solo con los primeros 5 caracteres
        if len(hora_str) > 5:
            hora_str = hora_str[:5]

        fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        hora_obj = datetime.strptime(hora_str, '%H:%M').time()
        dia_semana = fecha_obj.weekday()

        # 3. Validar Horario Laboral del Terapeuta
        trabaja = Horario.objects.filter(
            terapeuta_id=terapeuta_id,
            dia=dia_semana,
            hora_inicio__lte=hora_obj,
            hora_fin__gt=hora_obj
        ).exists()

        if not trabaja:
            return JsonResponse({'available': False, 'msg': ' El terapeuta no trabaja en este horario.'})

        # 4. Validar Choque de Consultorio
        query_consultorio = Cita.objects.filter(
            consultorio_id=consultorio_id,
            fecha=fecha_obj,
            hora=hora_obj,
            estatus='programada'
        )
        # ¡MAGIA! Si estamos editando, excluimos esta cita del conteo
        if exclude_id and exclude_id != 'None' and exclude_id != '':
            query_consultorio = query_consultorio.exclude(id=int(exclude_id))

        if query_consultorio.exists():
             return JsonResponse({'available': False, 'msg': ' El consultorio está ocupado.'})

        # 5. Validar Choque de Terapeuta (misma lógica de exclusión)
        query_terapeuta = Cita.objects.filter(
            terapeuta_id=terapeuta_id,
            fecha=fecha_obj,
            hora=hora_obj,
            estatus='programada'
        )
        if exclude_id and exclude_id != 'None' and exclude_id != '':
            query_terapeuta = query_terapeuta.exclude(id=int(exclude_id))

        if query_terapeuta.exists():
            return JsonResponse({'available': False, 'msg': ' El terapeuta ya tiene otra cita.'})

        return JsonResponse({'available': True, 'msg': ' Disponible'})

    except ValueError as e:
        # Esto captura errores de formato raros y nos dice cuál es en la consola
        print(f"Error de formato: {e}") 
        return JsonResponse({'available': False, 'msg': 'Error en formato de fecha/hora'})
    
# En clinica/views.py

@login_required
def editar_cita(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    
    if request.method == 'POST':
        form = CitaForm(request.POST, instance=cita)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Cita actualizada correctamente! ')
            
            origen = request.GET.get('next', 'home')
            if origen == 'paciente':
                return redirect('detalle_paciente', paciente_id=cita.paciente.id)
            return redirect('home')
        else:
            # 👇 AQUÍ ESTÁ LA MAGIA: Mostramos el error exacto
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, f" {error}")
                    else:
                        messages.error(request, f"Error en {field}: {error}")
    else:
        form = CitaForm(instance=cita)

    return render(request, 'clinica/editar_cita.html', {
        'form': form, 
        'cita': cita
    })