#Librerias estandar de Python
import unicodedata
from datetime import date, datetime, timedelta

#Herramientas base de Django
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse

#Modelos, Formularios y Utilidades de nuestra App
from .models import Paciente, Cita, Horario
from .models import SolicitudCita, Terapeuta # Asegurate de importar SolicitudCita
from .models import Paciente, Terapeuta, Cita, Horario, SolicitudCita
from .forms import PacienteForm, CitaForm
#from .utils import sincronizar_google_sheet

def quitar_tildes(texto):
    if not texto:
        return ""
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto))
                   if unicodedata.category(c) != 'Mn').lower()


SERVICIOS_GRUPALES = {
    'terapia de pareja',
    'terapia familiar',
    'terapia infantil',
}


def es_servicio_grupal(servicio):
    nombre = quitar_tildes(servicio.nombre if servicio else '').strip()
    return any(base in nombre for base in SERVICIOS_GRUPALES)


def obtener_configuracion_estatus_cita(estatus):
    configuraciones = {
        Cita.ESTATUS_CONFIRMADA: {
            'label': 'Confirmada',
            'color': '#22c55e',
            'bg': '#dcfce7',
            'border': '#16a34a',
            'text': '#14532d',
        },
        Cita.ESTATUS_SIN_CONFIRMAR: {
            'label': 'Sin confirmar',
            'color': '#06b6d4',
            'bg': '#cffafe',
            'border': '#0891b2',
            'text': '#164e63',
        },
        Cita.ESTATUS_REAGENDO: {
            'label': 'Reagendo',
            'color': '#f59e0b',
            'bg': '#fef3c7',
            'border': '#d97706',
            'text': '#78350f',
        },
        Cita.ESTATUS_CANCELO: {
            'label': 'Cancelo',
            'color': '#ef4444',
            'bg': '#fee2e2',
            'border': '#dc2626',
            'text': '#7f1d1d',
        },
        Cita.ESTATUS_SI_ASISTIO: {
            'label': 'Si asistio',
            'color': '#16a34a',
            'bg': '#dcfce7',
            'border': '#15803d',
            'text': '#14532d',
        },
        Cita.ESTATUS_NO_ASISTIO: {
            'label': 'No asistio',
            'color': '#7c3aed',
            'bg': '#ede9fe',
            'border': '#6d28d9',
            'text': '#4c1d95',
        },
        Cita.ESTATUS_INCIDENCIA: {
            'label': 'Incidencia',
            'color': '#64748b',
            'bg': '#e2e8f0',
            'border': '#475569',
            'text': '#1e293b',
        },
    }
    return configuraciones.get(
        estatus,
        {
            'label': estatus or 'Sin estatus',
            'color': '#334155',
            'bg': '#e2e8f0',
            'border': '#334155',
            'text': '#0f172a',
        },
    )

@login_required
def home(request):
    # --- EL SEMAFORO INTELIGENTE ---
    if hasattr(request.user, 'perfil_terapeuta'):
        return redirect('portal_terapeuta')
    
    if hasattr(request.user, 'perfil_paciente'):
        return redirect('portal_paciente')
    
    from django.utils import timezone
    from .forms import CitaForm 
    from .models import SolicitudCita # <-- Importamos la sala de espera por si acaso
    
    hoy = timezone.now().date()
    mes_actual = timezone.now().month
    
    # --- NUEVO: Traemos la bandeja de entrada de solicitudes pendientes ---
    solicitudes_pendientes = SolicitudCita.objects.filter(estado='pendiente').order_by('fecha_creacion')
    
    # 1. ESTADÍSTICAS
    citas_hoy_count = Cita.objects.filter(fecha=hoy).count()
    
    # CORRECCIÓN 1: Usamos 'estatus' en lugar de 'estado'
    pendientes_count = Cita.objects.filter(
        fecha__lte=hoy,
        estatus__in=Cita.ESTATUS_ACTIVOS,
    ).count()
    
    pacientes_nuevos = Paciente.objects.filter(
        fecha_registro__month=mes_actual
    ).count()

    # 2. PRÓXIMAS CITAS
    # CORRECCIÓN 2: Usamos 'estatus' y ordenamos por 'hora' (no hora_inicio)
    proximas_citas = Cita.objects.filter(
        fecha__gte=hoy,
        estatus__in=Cita.ESTATUS_ACTIVOS,
        paciente__isnull=False,
    ).order_by('fecha', 'hora')

    dia_tablero = request.GET.get('dia', 'hoy')
    if dia_tablero == 'manana':
        fecha_tablero = hoy + timedelta(days=1)
    else:
        dia_tablero = 'hoy'
        fecha_tablero = hoy

    citas_tablero = Cita.objects.filter(
        fecha=fecha_tablero,
        paciente__isnull=False,
    ).select_related(
        'division', 'servicio', 'terapeuta', 'consultorio', 'paciente'
    ).prefetch_related(
        'pacientes_adicionales'
    ).order_by('fecha', 'hora')

    return render(request, 'clinica/home.html', {
        'citas_hoy': citas_hoy_count,
        'pendientes': pendientes_count,
        'pacientes_nuevos': pacientes_nuevos,
        'proximas_citas': proximas_citas,
        'citas_tablero': citas_tablero,
        'dia_tablero': dia_tablero,
        'fecha_tablero': fecha_tablero,
        'hoy': hoy,
        'form': CitaForm(),
        'solicitudes_pendientes': solicitudes_pendientes, # <--- AQUI YA ESTA INCLUIDO EN EL PAQUETE
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

# En clinica/views.py (dentro de detalle_paciente)

def detalle_paciente(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    historial = Cita.objects.filter(
        Q(paciente=paciente) | Q(pacientes_adicionales=paciente)
    ).distinct().order_by('-fecha', '-hora')
    
    # Extraemos los terapeutas unicos que han atendido a este paciente
    terapeutas_previos = set(cita.terapeuta for cita in historial if cita.terapeuta)

    context = {
        'paciente': paciente,
        'historial': historial,
        'terapeutas_previos': terapeutas_previos, # Pasamos la lista al HTML
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
            if es_servicio_grupal(cita.servicio):
                pacientes_extra = form.cleaned_data.get('pacientes_extra')
                cita.pacientes_adicionales.set(
                    (pacientes_extra or Paciente.objects.none()).exclude(pk=cita.paciente_id)
                )
            else:
                cita.pacientes_adicionales.clear()
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
            if es_servicio_grupal(cita.servicio):
                pacientes_extra = form.cleaned_data.get('pacientes_extra')
                cita.pacientes_adicionales.set(
                    (pacientes_extra or Paciente.objects.none()).exclude(pk=cita.paciente_id)
                )
            else:
                cita.pacientes_adicionales.clear()
            
           
            try:
                sincronizar_google_sheet(cita)
                print("✅ Sincronización exitosa")
            except Exception as e:
                print(f" Error al sincronizar con Google: {e}")
            

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
    citas = Cita.objects.filter(estatus__in=Cita.ESTATUS_ACTIVOS)
    
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
        if cita.estatus == Cita.ESTATUS_CONFIRMADA:
            color = '#28a745' # Verde
        elif cita.estatus == Cita.ESTATUS_SIN_CONFIRMAR:
            color = '#26C6DA' # Tu color INTRA Primary
        elif cita.estatus == Cita.ESTATUS_REAGENDO:
            color = '#f59f00'
        elif cita.estatus == Cita.ESTATUS_INCIDENCIA:
            color = '#6c757d'

        eventos.append({
            'title': f"{cita.pacientes_display()} ({cita.terapeuta})",
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
            cita = form.save()

            # Para servicios grupales guardamos pacientes adicionales en la misma cita.
            if es_servicio_grupal(cita.servicio):
                pacientes_extra = form.cleaned_data.get('pacientes_extra')
                if pacientes_extra:
                    cita.pacientes_adicionales.set(
                        pacientes_extra.exclude(pk=cita.paciente_id)
                    )
            else:
                cita.pacientes_adicionales.clear()
            
            # --- NUEVA MAGIA: Limpieza de la bandeja de entrada ---
            # Atrapamos el ID de la solicitud que sigue en la URL
            solicitud_id = request.GET.get('solicitud')
            if solicitud_id:
                try:
                  
                    # Buscamos el ticket en la sala de espera
                    solicitud = SolicitudCita.objects.get(id=solicitud_id)
                    # Lo marcamos como aceptado para que desaparezca del Dashboard
                    solicitud.estado = 'aceptada'
                    solicitud.save()
                except SolicitudCita.DoesNotExist:
                    pass
            # ------------------------------------------------------
            
            messages.success(request, 'Cita agendada correctamente.')
            return redirect('home')
        else:
            # Tu logica de rastreo de errores intacta
            print("ERRORES DETECTADOS:", form.errors) 
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
            
            # ATENCION: Aqui NO hacemos redirect. Dejamos que el flujo continue 
            # hacia abajo para que vuelva a mostrar el formulario, pero ahora 
            # marcado con los errores y conservando lo que el usuario escribio.
            
    else:
        # Peticion GET: El usuario apenas va a abrir la pagina
        datos_iniciales = {}
        
        if 'fecha' in request.GET:
            datos_iniciales['fecha'] = request.GET.get('fecha')
        if 'hora' in request.GET:
            datos_iniciales['hora'] = request.GET.get('hora')
        if 'paciente' in request.GET:
            datos_iniciales['paciente'] = request.GET.get('paciente')
            
        # TRUCO: Lo convertimos a entero para que el campo Choice de Django lo acepte sin quejarse
        if 'terapeuta' in request.GET:
            try:
                datos_iniciales['terapeuta'] = int(request.GET.get('terapeuta'))
            except ValueError:
                pass
            
        solicitud_id = request.GET.get('solicitud')
        if solicitud_id:
            try:
                solicitud = SolicitudCita.objects.get(id=solicitud_id)
                # Llenamos el formulario con lo que pidió el paciente
                datos_iniciales['fecha'] = solicitud.fecha_deseada
                
                if solicitud.hora_deseada:
                    datos_iniciales['hora'] = solicitud.hora_deseada
                    
                if solicitud.terapeuta:
                    datos_iniciales['terapeuta'] = solicitud.terapeuta.id
                    
                    from .models import Paciente 
                
                # Buscamos si hay algún paciente en la BD que se llame igual
                paciente_match = Paciente.objects.filter(nombre__icontains=solicitud.paciente_nombre).first()
                if paciente_match:
                    datos_iniciales['paciente'] = paciente_match.id
            except SolicitudCita.DoesNotExist:
                pass
        form = CitaForm(initial=datos_iniciales)

    # ESTO ES VITAL: Renderizamos la plantilla HTML en lugar de redirigir.
    # Asi el usuario puede ver el formulario para llenarlo o corregirlo.
    return render(request, 'clinica/crear_cita.html', {'form': form})


@login_required
def api_pacientes_relacionados(request):
    paciente_id = request.GET.get('paciente_id')
    if not paciente_id:
        return JsonResponse({'relacionados': []})

    try:
        paciente = Paciente.objects.get(id=paciente_id)
    except Paciente.DoesNotExist:
        return JsonResponse({'relacionados': []})

    relacionados = paciente.pacientes_relacionados.order_by('nombre').values('id', 'nombre')
    return JsonResponse({'relacionados': list(relacionados)})

# En clinica/views.py

def verificar_disponibilidad(request):
    # CAMBIO: Permitir cualquier combinación sin validar conflictos
    # Las citas se pueden agendar sin restricción
    
    fecha_str = request.GET.get('fecha')
    hora_str = request.GET.get('hora')
    consultorio_id = request.GET.get('consultorio')
    terapeuta_id = request.GET.get('terapeuta')
    exclude_id = request.GET.get('exclude_id')

    if not (fecha_str and hora_str and consultorio_id and terapeuta_id):
        return JsonResponse({'available': True, 'msg': ''})

    try:
        if len(hora_str) > 5:
            hora_str = hora_str[:5]

        # CAMBIO: Siempre devolver disponibilidad sin validar conflictos
        return JsonResponse({'available': True, 'msg': 'Disponible para agendar'})

    except ValueError as e:
        print(f"Error de formato: {e}") 
        return JsonResponse({'available': True, 'msg': 'Disponible'})
    
# En clinica/views.py

@login_required
def editar_cita(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    
    if request.method == 'POST':
        form = CitaForm(request.POST, instance=cita)
        if form.is_valid():
            cita = form.save()
            if es_servicio_grupal(cita.servicio):
                pacientes_extra = form.cleaned_data.get('pacientes_extra')
                cita.pacientes_adicionales.set(
                    (pacientes_extra or Paciente.objects.none()).exclude(pk=cita.paciente_id)
                )
            else:
                cita.pacientes_adicionales.clear()
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
    }
    )


@login_required
def eliminar_cita(request, cita_id):
    if request.method != 'POST':
        return redirect('editar_cita', cita_id=cita_id)

    cita = get_object_or_404(Cita, id=cita_id)
    paciente_id = cita.paciente_id
    cita.delete()
    messages.success(request, 'Cita eliminada correctamente.')

    origen = request.GET.get('next', 'home')
    if origen == 'paciente' and paciente_id:
        return redirect('detalle_paciente', paciente_id=paciente_id)
    return redirect('home')


def api_citas_calendario(request):
    citas = Cita.objects.select_related(
        'division', 'servicio', 'terapeuta', 'consultorio', 'paciente'
    ).prefetch_related(
        'pacientes_adicionales'
    ).all()
    eventos = []
    
    for cita in citas:
        # FullCalendar necesita fecha y hora juntas en formato ISO
        start_datetime = datetime.combine(cita.fecha, cita.hora)
        # Asumimos que la cita dura 1 hora por defecto para pintar el bloque
        end_datetime = start_datetime + timedelta(hours=1)
        configuracion_estatus = obtener_configuracion_estatus_cita(cita.estatus)
        pacientes = cita.titulo_cita()
        consultorio = str(cita.consultorio) if cita.consultorio else 'Sin consultorio'
        terapeuta = str(cita.terapeuta) if cita.terapeuta else 'Sin terapeuta'
        servicio = str(cita.servicio) if cita.servicio else 'Sin servicio'
        division = str(cita.division) if cita.division else 'Sin division'
        costo = str(cita.costo) if cita.costo is not None else ''

        eventos.append({
            'id': cita.id,
            'title': pacientes,
            'start': start_datetime.isoformat(),
            'end': end_datetime.isoformat(),
            'backgroundColor': configuracion_estatus['bg'],
            'borderColor': configuracion_estatus['border'],
            'textColor': configuracion_estatus['text'],
            'classNames': ['evento-cita'],
            'extendedProps': {
                'paciente': pacientes,
                'paciente_upper': pacientes.upper(),
                'terapeuta': terapeuta,
                'servicio': servicio,
                'consultorio': consultorio,
                'division': division,
                'situacion': configuracion_estatus['label'],
                'situacion_color': configuracion_estatus['color'],
                'situacion_bg': configuracion_estatus['bg'],
                'situacion_border': configuracion_estatus['border'],
                'situacion_text': configuracion_estatus['text'],
                'tipo_paciente': cita.tipo_paciente,
                'tipo_paciente_label': cita.get_tipo_paciente_display(),
                'costo': costo,
                'notas': cita.notas or '',
                'editar_url': f"/citas/{cita.id}/editar/?next=calendario",
            },
        })
        
    return JsonResponse(eventos, safe=False)
# En clinica/views.py (al final del archivo)
from django.http import JsonResponse

def api_terapeutas_paciente(request):
    paciente_id = request.GET.get('paciente_id')
    if not paciente_id:
        return JsonResponse({'terapeutas': []})
    
    # Buscamos todas las citas del paciente y sacamos los terapeutas
    citas = Cita.objects.filter(
        Q(paciente_id=paciente_id) | Q(pacientes_adicionales__id=paciente_id)
    ).select_related('terapeuta').distinct()
    
    terapeutas_unicos = set()
    for cita in citas:
        if cita.terapeuta:
            terapeutas_unicos.add(str(cita.terapeuta))
            
    return JsonResponse({'terapeutas': list(terapeutas_unicos)})

@login_required
def portal_terapeuta(request):
    if not hasattr(request.user, 'perfil_terapeuta'):
        return redirect('home') 
    
    mi_perfil = request.user.perfil_terapeuta
    hoy = date.today()
    
    # --- TRUCO PARA LA FECHA PERFECTA EN ESPAÑOL ---
    meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    fecha_bonita = f"{hoy.day} de {meses[hoy.month - 1]} del {hoy.year}"
    
    citas_hoy = Cita.objects.filter(
        terapeuta=mi_perfil, 
        fecha=hoy,
        paciente__isnull=False,
    ).order_by('hora')
    
    citas_proximas = Cita.objects.filter(
        terapeuta=mi_perfil, 
        fecha__gt=hoy,
        paciente__isnull=False,
    ).order_by('fecha', 'hora')[:10] 
    
    mis_solicitudes = SolicitudCita.objects.filter(
        terapeuta=mi_perfil
    ).order_by('-fecha_creacion')[:5]
    context = {
        'terapeuta': mi_perfil,
        'citas_hoy': citas_hoy,
        'citas_proximas': citas_proximas,
        'fecha_bonita': fecha_bonita, # <--- Pasamos la fecha arreglada
        'mis_solicitudes': mis_solicitudes, 
    }
    
    return render(request, 'clinica/portal_terapeuta.html', context)

@login_required
def portal_paciente(request):
    # 1. Verificamos si el usuario actual tiene un perfil de paciente
    if not hasattr(request.user, 'perfil_paciente'):
        return redirect('home') 
    
    # 2. Identificamos al paciente exacto
    mi_perfil = request.user.perfil_paciente
    hoy = date.today()
    
    # 3. Filtramos sus citas futuras y pasadas
    citas_proximas = Cita.objects.filter(
        Q(paciente=mi_perfil) | Q(pacientes_adicionales=mi_perfil),
        fecha__gte=hoy
    ).distinct().order_by('fecha', 'hora')
    
    historial = Cita.objects.filter(
        Q(paciente=mi_perfil) | Q(pacientes_adicionales=mi_perfil),
        fecha__lt=hoy
    ).distinct().order_by('-fecha', '-hora')
    
  
    mis_solicitudes = SolicitudCita.objects.filter(
        paciente_nombre=mi_perfil.nombre
    ).order_by('-fecha_creacion')[:5] 
    
    context = {
        'paciente': mi_perfil,
        'citas_proximas': citas_proximas,
        'historial': historial,
        'mis_solicitudes': mis_solicitudes, # <--- Lo agregamos al paquete
    }
    
    return render(request, 'clinica/portal_paciente.html', context)

@login_required
def solicitar_cita_paciente(request):
    # Verificamos que sea un paciente
    if not hasattr(request.user, 'perfil_paciente'):
        return redirect('home')
        
    mi_perfil = request.user.perfil_paciente
    
    if request.method == 'POST':
        # Atrapamos lo que el paciente lleno en el formulario HTML
        fecha = request.POST.get('fecha_deseada')
        hora = request.POST.get('hora_deseada')
        terapeuta_id = request.POST.get('terapeuta')
        notas = request.POST.get('notas_paciente')
        
        # Creamos el ticket en nuestra "Sala de Espera" (SolicitudCita)
        SolicitudCita.objects.create(
            paciente_nombre=mi_perfil.nombre,
            telefono=mi_perfil.telefono, # Asumiendo que tu modelo Paciente tiene campo telefono
            fecha_deseada=fecha,
            hora_deseada=hora if hora else None,
            terapeuta_id=terapeuta_id if terapeuta_id else None,
            notas_paciente=notas,
            estado='pendiente'
        )
        
        # Le avisamos que todo salio bien y lo regresamos a su portal
        messages.success(request, '¡Tu solicitud ha sido enviada! Recepción la revisará y te confirmará pronto.')
        return redirect('portal_paciente')
        
    # Si apenas va a abrir la pagina (GET), le mandamos la lista de terapeutas activos
    terapeutas = Terapeuta.objects.filter(activo=True)
    return render(request, 'clinica/solicitar_cita.html', {'terapeutas': terapeutas})

@login_required
def rechazar_solicitud(request, solicitud_id):
    if request.method == 'POST':
        try:
            from .models import SolicitudCita # Aseguramos que este import global funcione
            solicitud = SolicitudCita.objects.get(id=solicitud_id)
            
            # Atrapamos lo que escribio la recepcionista
            motivo = request.POST.get('motivo_rechazo', '')
            
            solicitud.estado = 'rechazada'
            solicitud.motivo_rechazo = motivo
            solicitud.save()
            
            messages.warning(request, f'La solicitud de {solicitud.paciente_nombre} fue rechazada correctamente.')
        except SolicitudCita.DoesNotExist:
            pass
            
    return redirect('home')

@login_required
def solicitar_cita_terapeuta(request):
    if not hasattr(request.user, 'perfil_terapeuta'):
        return redirect('home')
        
    mi_perfil = request.user.perfil_terapeuta
    
    # Importamos los modelos necesarios
    from .models import SolicitudCita, Paciente
    
    if request.method == 'POST':
        # Ahora este dato vendra del menu desplegable (exactamente como esta escrito en la BD)
        paciente = request.POST.get('paciente_nombre') 
        telefono = request.POST.get('telefono', '')
        fecha = request.POST.get('fecha_deseada')
        hora = request.POST.get('hora_deseada')
        notas = request.POST.get('notas_terapeuta', '')
        
        SolicitudCita.objects.create(
            paciente_nombre=paciente,
            telefono=telefono,
            fecha_deseada=fecha,
            hora_deseada=hora if hora else None,
            terapeuta=mi_perfil, 
            notas_paciente=f"SOLICITADO POR TERAPEUTA: {notas}", 
            estado='pendiente'
        )
        
        messages.success(request, 'Solicitud enviada a Recepción. Espera su confirmación.')
        return redirect('portal_terapeuta')
        
    # --- NUEVO: Traemos la lista de pacientes ordenados alfabeticamente ---
    pacientes = Paciente.objects.all().order_by('nombre')
    
    # Pasamos los pacientes al contexto del HTML
    return render(request, 'clinica/solicitar_cita_terapeuta.html', {
        'pacientes': pacientes
    })

def api_disponibilidad_terapeuta(request):
    fecha_str = request.GET.get('fecha')
    terapeuta_id = request.GET.get('terapeuta')

    if not (fecha_str and terapeuta_id):
        return JsonResponse({'horarios': []})

    try:
        from datetime import datetime, timedelta
        from .models import Horario, Cita
        
        fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        dia_semana = fecha_obj.weekday()

        # 1. Buscar si el terapeuta trabaja ese dia
        horarios_laborales = Horario.objects.filter(
            terapeuta_id=terapeuta_id, 
            dia=dia_semana
        )

        if not horarios_laborales.exists():
            return JsonResponse({'mensaje': 'El terapeuta no tiene horario laboral registrado para este dia.', 'horarios': []})

        # 2. Generar todos los bloques de 1 hora posibles en su turno
        slots_posibles = []
        for hl in horarios_laborales:
            hora_actual = datetime.combine(fecha_obj, hl.hora_inicio)
            hora_fin = datetime.combine(fecha_obj, hl.hora_fin)
            
            while hora_actual < hora_fin:
                slots_posibles.append(hora_actual.time())
                hora_actual += timedelta(minutes=60)

        # 3. Buscar las horas que ya tiene ocupadas
        citas_ocupadas = Cita.objects.filter(
            terapeuta_id=terapeuta_id,
            fecha=fecha_obj,
            estatus__in=Cita.ESTATUS_ACTIVOS,
        ).values_list('hora', flat=True)

        # 4. Restar las ocupadas a las posibles
        horarios_libres = []
        for slot in slots_posibles:
            if slot not in citas_ocupadas:
                horarios_libres.append(slot.strftime('%H:%M'))

        # Devolver la lista ordenada y sin duplicados
        return JsonResponse({'horarios': sorted(list(set(horarios_libres)))})

    except Exception as e:
        print(f"Error en radar: {e}")
        return JsonResponse({'horarios': [], 'error': 'Error procesando datos'})
