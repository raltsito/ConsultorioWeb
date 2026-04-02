#Librerias estandar de Python
import unicodedata
import csv
import io
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

#Herramientas base de Django
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db.models import Q, Sum, Count
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.urls import reverse

#Excel
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

#Modelos, Formularios y Utilidades de nuestra App
from .models import (
    AperturaExpediente,
    BloqueoAgendaTerapeuta,
    DocumentoPaciente,
    Empresa,
    Paciente,
    NotaTerapeutaPaciente,
    ReporteSesion,
    Terapeuta,
    Cita,
    Horario,
    SolicitudCita,
    obtener_bloqueo_terapeuta_en_fecha,
)
from .models import CorteSemanal, LineaNomina, BonoExtra
from .forms import (
    AperturaExpedienteForm,
    BloqueoAgendaTerapeutaForm,
    CitaEmpresaForm,
    PacienteEmpresaForm,
    PacienteForm,
    CitaForm,
    DocumentoPacienteForm,
    NotaTerapeutaPacienteForm,
    CheckoutCitaForm,
    ReporteSesionForm,
)
from .services import calcular_nomina_semanal, preview_nomina_semanal, aprobar_corte_semanal
#from .utils import sincronizar_google_sheet

def quitar_tildes(texto):
    if not texto:
        return ""
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto))
                   if unicodedata.category(c) != 'Mn').lower()


def resolver_paciente_por_nombre(nombre):
    nombre_normalizado = quitar_tildes(nombre).strip()
    if not nombre_normalizado:
        return None

    paciente = Paciente.objects.filter(nombre__iexact=str(nombre).strip()).first()
    if paciente:
        return paciente

    paciente = Paciente.objects.filter(nombre_normalizado=nombre_normalizado).first()
    if paciente:
        return paciente

    tokens = [token for token in nombre_normalizado.split() if token]
    if tokens:
        filtro_normalizado = Q()
        filtro_nombre = Q()
        for token in tokens:
            filtro_normalizado &= Q(nombre_normalizado__icontains=token)
            filtro_nombre &= Q(nombre__icontains=token)
        paciente = Paciente.objects.filter(
            filtro_normalizado | filtro_nombre
        ).order_by('nombre').first()
        if paciente:
            return paciente

    return Paciente.objects.filter(
        Q(nombre_normalizado__icontains=nombre_normalizado) |
        Q(nombre__icontains=str(nombre).strip())
    ).order_by('nombre').first()


# ─── Excel helper ─────────────────────────────────────────────────────────────
_TEAL_FILL  = PatternFill("solid", fgColor="26C6DA")
_HEADER_FONT = Font(bold=True, color="FFFFFF", name="Calibri", size=11)
_BODY_FONT   = Font(name="Calibri", size=10)
_ALT_FILL    = PatternFill("solid", fgColor="F0F4F8")

def _build_excel_response(filename, sheet_title, headers, rows, col_widths=None):
    """
    Genera un HttpResponse con un .xlsx estilizado.
    headers: lista de str
    rows: lista de listas (valores de celda)
    col_widths: lista opcional de anchos de columna
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_title

    # Fila de encabezado
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = _HEADER_FONT
        cell.fill = _TEAL_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")

    ws.row_dimensions[1].height = 20

    # Filas de datos
    for row_idx, row in enumerate(rows, start=2):
        fill = _ALT_FILL if row_idx % 2 == 0 else None
        for col_idx, value in enumerate(row, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = _BODY_FONT
            if fill:
                cell.fill = fill

    # Anchos de columna
    if col_widths:
        for idx, w in enumerate(col_widths, start=1):
            ws.column_dimensions[get_column_letter(idx)].width = w
    else:
        for col_idx in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = 18

    # Freeze panes (encabezado fijo)
    ws.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    response = HttpResponse(
        buf.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
# ──────────────────────────────────────────────────────────────────────────────


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

    if hasattr(request.user, 'perfil_empresa'):
        return redirect('portal_empresa')

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
    ).order_by('fecha', 'hora')

    dia_tablero = request.GET.get('dia', 'hoy')
    if dia_tablero == 'manana':
        fecha_tablero = hoy + timedelta(days=1)
    else:
        dia_tablero = 'hoy'
        fecha_tablero = hoy

    citas_tablero = Cita.objects.filter(
        fecha=fecha_tablero,
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

def _generar_pdf_apertura(apertura):
    """Genera los bytes del PDF de apertura de expediente usando reportlab."""
    from io import BytesIO
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=2 * cm, leftMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    blue  = colors.HexColor('#003087')
    gray  = colors.HexColor('#546E7A')
    lblue = colors.HexColor('#90CAF9')

    T_HEADING = ParagraphStyle('heading', parent=styles['Normal'],
                               fontSize=12, fontName='Helvetica-Bold',
                               alignment=TA_CENTER, textColor=blue, spaceAfter=3)
    T_SUB     = ParagraphStyle('sub', parent=styles['Normal'],
                               fontSize=9, alignment=TA_CENTER, spaceAfter=8)
    T_SECTION = ParagraphStyle('section', parent=styles['Normal'],
                               fontSize=8, fontName='Helvetica-Bold',
                               textColor=blue, spaceBefore=8, spaceAfter=3)
    T_LABEL   = ParagraphStyle('label', parent=styles['Normal'],
                               fontSize=7, fontName='Helvetica-Bold', textColor=gray)
    T_VALUE   = ParagraphStyle('value', parent=styles['Normal'],
                               fontSize=9, fontName='Helvetica', spaceAfter=3)
    T_PRIVACY = ParagraphStyle('privacy', parent=styles['Normal'],
                               fontSize=6.5, textColor=gray, leading=9, spaceBefore=6)

    def lbl(text):
        return Paragraph(text.upper(), T_LABEL)

    def val(v):
        return Paragraph(str(v) if v else '—', T_VALUE)

    def grid(rows):
        """Crea una tabla de 4 columnas label/valor, label/valor."""
        tbl = Table(rows, colWidths=['18%', '32%', '18%', '32%'])
        tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
        ]))
        return tbl

    p = apertura.paciente
    elems = []

    # ── Encabezado ──────────────────────────────────────────────────────────
    elems.append(Paragraph('INSTITUTO DE ATENCIÓN INTEGRAL Y DESARROLLO HUMANO A.C.', T_HEADING))
    elems.append(Paragraph('Información Personal del Paciente — Apertura de Expediente', T_SUB))
    elems.append(HRFlowable(width='100%', thickness=1.5, color=blue, spaceAfter=6))

    # Expediente No / fecha
    elems.append(grid([
        [lbl('Expediente No.'), val(apertura.expediente_no or '—'),
         lbl('Fecha de apertura'), val(apertura.creado_en.strftime('%d/%m/%Y'))],
    ]))
    elems.append(Spacer(1, 6))

    # ── Datos Personales ────────────────────────────────────────────────────
    elems.append(Paragraph('Datos Personales', T_SECTION))
    elems.append(HRFlowable(width='100%', thickness=0.5, color=lblue, spaceAfter=3))
    elems.append(grid([
        [lbl('Nombre completo'), val(p.nombre),
         lbl('Fecha de Nacimiento'),
         val(p.fecha_nacimiento.strftime('%d/%m/%Y') if p.fecha_nacimiento else '—')],
        [lbl('Ocupación'), val(apertura.ocupacion),
         lbl('Estado Civil'), val(apertura.get_estado_civil_display() if apertura.estado_civil else '—')],
        [lbl('Lugar de Trabajo'), val(apertura.lugar_de_trabajo),
         lbl('Cargo'), val(apertura.cargo)],
        [lbl('Calle'), val(apertura.calle),
         lbl('Núm.'), val(apertura.num_exterior)],
        [lbl('Colonia'), val(apertura.colonia),
         lbl('División'), val(str(apertura.division) if apertura.division else '—')],
        [lbl('Número de Celular'), val(p.telefono or '—'),
         lbl('Religión'), val(apertura.religion or 'No especificada')],
    ]))

    # ── Convivencia e Hijos ─────────────────────────────────────────────────
    elems.append(Paragraph('Convivencia', T_SECTION))
    elems.append(HRFlowable(width='100%', thickness=0.5, color=lblue, spaceAfter=3))
    elems.append(grid([
        [lbl('Vive con'), val(apertura.vive_con or '—'),
         lbl('Tiene hijos'), val('Sí' if apertura.tiene_hijos else 'No')],
        [lbl('No. de Hijos'), val(str(apertura.num_hijos) if apertura.num_hijos is not None else '—'),
         lbl(''), val('')],
    ]))
    if apertura.tiene_hijos:
        hijos = [
            (1, apertura.hijo_1), (2, apertura.hijo_2),
            (3, apertura.hijo_3), (4, apertura.hijo_4),
        ]
        h_rows = [[lbl(f'Hijo {i}'), val(h), lbl(''), val('')]
                  for i, h in hijos if h]
        if h_rows:
            elems.append(grid(h_rows))

    # ── Motivo de Consulta ──────────────────────────────────────────────────
    elems.append(Paragraph('Motivo de Consulta', T_SECTION))
    elems.append(HRFlowable(width='100%', thickness=0.5, color=lblue, spaceAfter=3))
    elems.append(Paragraph(apertura.motivo_consulta or '—', T_VALUE))

    # ── Emergencia ──────────────────────────────────────────────────────────
    elems.append(Paragraph('Contacto de Emergencia', T_SECTION))
    elems.append(HRFlowable(width='100%', thickness=0.5, color=lblue, spaceAfter=3))
    emg = Table(
        [[lbl('En caso de emergencia llamar a'), val(apertura.emergencia_contacto),
          lbl('Teléfono'), val(apertura.emergencia_telefono)]],
        colWidths=['22%', '28%', '14%', '36%'],
    )
    emg.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elems.append(emg)

    # ── Cómo se enteró ──────────────────────────────────────────────────────
    elems.append(Spacer(1, 6))
    elems.append(Table(
        [[lbl('¿Cómo se enteró de nosotros?'), val(apertura.como_se_entero or '—')]],
        colWidths=['28%', '72%'],
    ))

    # ── Aviso de Privacidad ─────────────────────────────────────────────────
    elems.append(Spacer(1, 10))
    elems.append(HRFlowable(width='100%', thickness=0.5, color=gray))
    elems.append(Paragraph(
        '<b>Aviso de Privacidad</b> — De acuerdo con lo establecido en la Constitución Política de los '
        'Estados Unidos Mexicanos, la Ley Federal De Protección de Datos Personales y en el Código Ético '
        'del Psicólogo, la totalidad de la información como de los registros e historias clínicas, están '
        'cubiertas por el secreto profesional del Instituto de Atención Integral y Desarrollo Humano A.C. '
        'y sus colaboradores. WhatsApp: 844 443 99 87 | ANA CECILIA TREVIÑO No. 158 COL. IGNACIO ZARAGOZA',
        T_PRIVACY,
    ))

    doc.build(elems)
    return buffer.getvalue()


def detalle_paciente(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    historial = Cita.objects.filter(
        Q(paciente=paciente) | Q(pacientes_adicionales=paciente)
    ).distinct().order_by('-fecha', '-hora')
    
    # Extraemos los terapeutas unicos que han atendido a este paciente
    terapeutas_previos = set(cita.terapeuta for cita in historial if cita.terapeuta)
    notas_historial = NotaTerapeutaPaciente.objects.filter(
        paciente=paciente
    ).select_related('terapeuta').order_by('-creado_en')
    documentos_historial = DocumentoPaciente.objects.filter(
        paciente=paciente
    ).select_related('terapeuta', 'subido_por').order_by('-creado_en')
    reportes_historial = ReporteSesion.objects.filter(
        paciente=paciente
    ).select_related('terapeuta').order_by('-fecha', '-creado_en')

    apertura = getattr(paciente, 'apertura_expediente_obj', None)

    context = {
        'paciente': paciente,
        'historial': historial,
        'terapeutas_previos': terapeutas_previos,
        'notas_historial': notas_historial,
        'documentos_historial': documentos_historial,
        'reportes_historial': reportes_historial,
        'apertura': apertura,
    }
    return render(request, 'clinica/detalle_paciente.html', context)


def _pacientes_ids_terapeuta(terapeuta):
    ids = set(
        Cita.objects.filter(
            terapeuta=terapeuta,
            paciente__isnull=False,
        ).values_list('paciente_id', flat=True)
    )
    ids.update(
        Cita.objects.filter(
            terapeuta=terapeuta,
            pacientes_adicionales__isnull=False,
        ).values_list('pacientes_adicionales__id', flat=True)
    )
    return {pid for pid in ids if pid}


@login_required
def expedientes_terapeuta(request):
    if not hasattr(request.user, 'perfil_terapeuta'):
        return redirect('home')

    terapeuta = request.user.perfil_terapeuta
    paciente_ids = _pacientes_ids_terapeuta(terapeuta)
    pacientes = Paciente.objects.filter(id__in=paciente_ids).order_by('nombre')

    return render(request, 'clinica/expedientes_terapeuta.html', {
        'terapeuta': terapeuta,
        'pacientes': pacientes,
    })


@login_required
def expediente_terapeuta_detalle(request, paciente_id):
    if not hasattr(request.user, 'perfil_terapeuta'):
        return redirect('home')

    terapeuta = request.user.perfil_terapeuta
    paciente_ids = _pacientes_ids_terapeuta(terapeuta)
    if paciente_id not in paciente_ids:
        messages.error(request, 'Solo puedes abrir expedientes de pacientes agendados contigo.')
        return redirect('expedientes_terapeuta')

    paciente = get_object_or_404(Paciente, id=paciente_id)
    historial = Cita.objects.filter(
        terapeuta=terapeuta
    ).filter(
        Q(paciente=paciente) | Q(pacientes_adicionales=paciente)
    ).distinct().order_by('-fecha', '-hora')
    notas_historial = NotaTerapeutaPaciente.objects.filter(
        terapeuta=terapeuta,
        paciente=paciente,
    ).order_by('-creado_en')
    documentos_historial = DocumentoPaciente.objects.filter(
        paciente=paciente
    ).select_related('terapeuta', 'subido_por').order_by('-creado_en')
    reportes_historial = ReporteSesion.objects.filter(
        terapeuta=terapeuta,
        paciente=paciente,
    ).order_by('-fecha', '-creado_en')

    apertura = getattr(paciente, 'apertura_expediente_obj', None)

    # --- Auto-calc: número de sesión = citas completadas (si_asistio) + 1 ---
    sesiones_completadas = Cita.objects.filter(
        terapeuta=terapeuta,
        estatus=Cita.ESTATUS_SI_ASISTIO,
    ).filter(
        Q(paciente=paciente) | Q(pacientes_adicionales=paciente)
    ).distinct().count()
    numero_sesion_sugerido = sesiones_completadas + 1

    # --- Auto-calc: hora de la cita más reciente de hoy como hora_inicio ---
    hoy = date.today()
    cita_hoy = historial.filter(fecha=hoy).order_by('hora').last()
    hora_inicio_sugerida = cita_hoy.hora if cita_hoy else None
    cita_sugerida = cita_hoy

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'guardar_apertura':
            form_apertura = AperturaExpedienteForm(request.POST, instance=apertura)
            form_reporte = ReporteSesionForm()
            form = NotaTerapeutaPacienteForm()
            form_documento = DocumentoPacienteForm()
            if form_apertura.is_valid():
                ap = form_apertura.save(commit=False)
                ap.paciente = paciente
                ap.save()

                nombre_completo = (form_apertura.cleaned_data.get('nombre') or '').strip()

                # Los apellidos ya no se capturan por separado en la UI.
                # Conservamos el modelo satisfecho con un valor de respaldo,
                # pero la fuente real del nombre visible/PDF es paciente.nombre.
                ap.apellido_paterno = ap.apellido_paterno or nombre_completo or '-'
                ap.apellido_materno = ap.apellido_materno or ''
                ap.save(update_fields=['apellido_paterno', 'apellido_materno'])

                paciente.nombre = nombre_completo or paciente.nombre
                paciente.fecha_nacimiento = form_apertura.cleaned_data.get('fecha_nacimiento') or paciente.fecha_nacimiento
                paciente.telefono = form_apertura.cleaned_data.get('telefono') or paciente.telefono
                paciente.save(update_fields=['nombre', 'fecha_nacimiento', 'telefono'])

                # Generar PDF y enlazar como DocumentoPaciente
                pdf_bytes = _generar_pdf_apertura(ap)
                nombre_pdf = f'apertura_expediente_{paciente.id}.pdf'
                if ap.documento:
                    doc_obj = ap.documento
                    doc_obj.contenido = pdf_bytes
                    doc_obj.nombre_archivo = nombre_pdf
                    doc_obj.save(update_fields=['contenido', 'nombre_archivo'])
                else:
                    doc_obj = DocumentoPaciente.objects.create(
                        paciente=paciente,
                        terapeuta=terapeuta,
                        subido_por=request.user,
                        tipo_documento='apertura',
                        nombre_archivo=nombre_pdf,
                        tipo_mime='application/pdf',
                        contenido=pdf_bytes,
                        descripcion='Apertura de expediente generada automáticamente.',
                    )
                    ap.documento = doc_obj
                    ap.save(update_fields=['documento'])
                messages.success(request, 'Apertura de expediente guardada y PDF generado correctamente.')
                return redirect('expediente_terapeuta_detalle', paciente_id=paciente.id)
            else:
                messages.error(request, 'Revisa los campos de la apertura.')

        elif accion == 'guardar_reporte':
            form_apertura = AperturaExpedienteForm(instance=apertura)
            form_reporte = ReporteSesionForm(request.POST)
            form = NotaTerapeutaPacienteForm()
            form_documento = DocumentoPacienteForm()
            if form_reporte.is_valid():
                reporte = form_reporte.save(commit=False)
                reporte.paciente = paciente
                reporte.terapeuta = terapeuta
                reporte.fecha = hoy
                reporte.numero_sesion = numero_sesion_sugerido
                reporte.hora_inicio = hora_inicio_sugerida
                if cita_sugerida:
                    reporte.cita = cita_sugerida
                reporte.save()
                messages.success(request, f'Reporte de sesión #{reporte.numero_sesion} guardado correctamente.')
                return redirect('expediente_terapeuta_detalle', paciente_id=paciente.id)
            else:
                messages.error(request, 'Revisa los campos del reporte.')

        elif accion == 'subir_documento':
            form_apertura = AperturaExpedienteForm(instance=apertura)
            form_reporte = ReporteSesionForm()
            form_documento = DocumentoPacienteForm(request.POST, request.FILES)
            form = NotaTerapeutaPacienteForm()
            if form_documento.is_valid():
                archivo = request.FILES['archivo']
                documento = form_documento.save(commit=False)
                documento.paciente = paciente
                documento.terapeuta = terapeuta
                documento.subido_por = request.user
                documento.nombre_archivo = archivo.name
                documento.tipo_mime = archivo.content_type
                documento.contenido = archivo.read()
                documento.save()
                messages.success(request, 'Documento agregado correctamente.')
                return redirect('expediente_terapeuta_detalle', paciente_id=paciente.id)

        else:
            form_apertura = AperturaExpedienteForm(instance=apertura)
            form_reporte = ReporteSesionForm()
            form = NotaTerapeutaPacienteForm(request.POST)
            form_documento = DocumentoPacienteForm()
            if form.is_valid():
                nota = form.save(commit=False)
                nota.terapeuta = terapeuta
                nota.paciente = paciente
                nota.save()
                messages.success(request, 'Nota agregada correctamente.')
                return redirect('expediente_terapeuta_detalle', paciente_id=paciente.id)
    else:
        form = NotaTerapeutaPacienteForm()
        form_documento = DocumentoPacienteForm()
        form_reporte = ReporteSesionForm()
        form_apertura = AperturaExpedienteForm(instance=apertura)

    return render(request, 'clinica/expediente_terapeuta_detalle.html', {
        'terapeuta': terapeuta,
        'paciente': paciente,
        'historial': historial,
        'form_notas': form,
        'notas_historial': notas_historial,
        'form_documento': form_documento,
        'documentos_historial': documentos_historial,
        'form_reporte': form_reporte,
        'reportes_historial': reportes_historial,
        'numero_sesion_sugerido': numero_sesion_sugerido,
        'hora_inicio_sugerida': hora_inicio_sugerida,
        'fecha_hoy': hoy,
        'apertura': apertura,
        'form_apertura': form_apertura,
    })

@login_required
def descargar_documento(request, doc_id):
    documento = get_object_or_404(DocumentoPaciente, id=doc_id)
    response = HttpResponse(bytes(documento.contenido), content_type=documento.tipo_mime or 'application/octet-stream')
    response['Content-Disposition'] = f'inline; filename="{documento.nombre_archivo}"'
    return response

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
            paciente_param = request.GET.get('paciente')
            if str(paciente_param).isdigit():
                datos_iniciales['paciente'] = paciente_param
            else:
                paciente_match = resolver_paciente_por_nombre(paciente_param)
                if paciente_match:
                    datos_iniciales['paciente'] = paciente_match.id
            
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

                if solicitud.consultorio:
                    datos_iniciales['consultorio'] = solicitud.consultorio.id

                paciente_match = resolver_paciente_por_nombre(solicitud.paciente_nombre)
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
    fecha_str = request.GET.get('fecha')
    hora_str = request.GET.get('hora')
    consultorio_id = request.GET.get('consultorio')
    terapeuta_id = request.GET.get('terapeuta')

    if not (fecha_str and hora_str and consultorio_id and terapeuta_id):
        return JsonResponse({'available': True, 'msg': ''})

    _DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

    try:
        if len(hora_str) > 5:
            hora_str = hora_str[:5]

        fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        hora_obj = datetime.strptime(hora_str, '%H:%M').time()

        # 1. Validar bloqueos del terapeuta
        bloqueo = obtener_bloqueo_terapeuta_en_fecha(terapeuta_id, fecha_obj, hora_obj)
        if bloqueo:
            return JsonResponse({'available': False, 'msg': bloqueo.mensaje_bloqueo()})

        # 2. Validar horario solo si el terapeuta tiene alguno configurado
        dia_semana = fecha_obj.weekday()
        tiene_horarios = Horario.objects.filter(terapeuta_id=terapeuta_id).exists()
        if not tiene_horarios:
            return JsonResponse({'available': True, 'msg': 'Disponible para agendar'})

        horarios_dia = list(Horario.objects.filter(terapeuta_id=terapeuta_id, dia=dia_semana))
        if not horarios_dia:
            return JsonResponse({
                'available': False,
                'msg': f'El terapeuta no tiene horario configurado los {_DIAS[dia_semana]}.',
            })
        horario_activo = next(
            (h for h in horarios_dia if h.hora_inicio <= hora_obj <= h.hora_fin), None
        )
        if not horario_activo:
            return JsonResponse({
                'available': False,
                'msg': f'Las {hora_str} está fuera del horario del terapeuta los {_DIAS[dia_semana]}.',
            })

        # 3. Validar que el consultorio pertenezca a la sede del horario activo
        if horario_activo.sede and consultorio_id:
            from .models import Consultorio as ConsultorioModel
            _SEDES = dict(Horario.SEDE_CHOICES)
            try:
                cons = ConsultorioModel.objects.get(id=consultorio_id)
                if cons.sede and cons.sede != horario_activo.sede:
                    sede_t = _SEDES.get(horario_activo.sede, horario_activo.sede)
                    sede_c = _SEDES.get(cons.sede, cons.sede)
                    return JsonResponse({
                        'available': False,
                        'msg': f'El consultorio "{cons}" es de {sede_c}, pero el terapeuta trabaja en {sede_t} a esa hora.',
                    })
            except ConsultorioModel.DoesNotExist:
                pass

        return JsonResponse({'available': True, 'msg': 'Disponible para agendar'})

    except ValueError as e:
        print(f"Error de formato en verificar_disponibilidad: {e}")
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
        datos_iniciales = {}
        if 'fecha' in request.GET:
            datos_iniciales['fecha'] = request.GET.get('fecha')
        if 'hora' in request.GET:
            datos_iniciales['hora'] = request.GET.get('hora')
        if 'paciente' in request.GET:
            paciente_param = request.GET.get('paciente')
            if str(paciente_param).isdigit():
                datos_iniciales['paciente'] = paciente_param
            else:
                paciente_match = resolver_paciente_por_nombre(paciente_param)
                if paciente_match:
                    datos_iniciales['paciente'] = paciente_match.id
        if 'terapeuta' in request.GET:
            try:
                datos_iniciales['terapeuta'] = int(request.GET.get('terapeuta'))
            except (TypeError, ValueError):
                pass
        form = CitaForm(instance=cita, initial=datos_iniciales)

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


@login_required
def eliminar_paciente(request, paciente_id):
    if request.method != 'POST':
        return redirect('detalle_paciente', paciente_id=paciente_id)

    paciente = get_object_or_404(Paciente, id=paciente_id)
    nombre = paciente.nombre
    paciente.delete()
    messages.success(request, f'Expediente de {nombre} eliminado correctamente.')
    return redirect('lista_pacientes')


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
    ).order_by('hora')

    citas_proximas = Cita.objects.filter(
        terapeuta=mi_perfil,
        fecha__gt=hoy,
    ).order_by('fecha', 'hora')[:10] 

    try:
        semana_offset = int(request.GET.get('semana_offset', 0))
    except (TypeError, ValueError):
        semana_offset = 0

    inicio_semana = hoy - timedelta(days=hoy.weekday()) + timedelta(weeks=semana_offset)
    fin_semana = inicio_semana + timedelta(days=6)
    citas_semana = list(
        Cita.objects.filter(
            terapeuta=mi_perfil,
            fecha__gte=inicio_semana,
            fecha__lte=fin_semana,
        )
        .select_related('consultorio', 'servicio', 'paciente')
        .prefetch_related('pacientes_adicionales')
        .order_by('fecha', 'hora')
    )
    citas_por_fecha = defaultdict(list)
    for cita in citas_semana:
        citas_por_fecha[cita.fecha].append(cita)

    dias_semana_cortos = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
    meses_cortos = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
    agenda_semanal = []
    for offset in range(7):
        fecha_item = inicio_semana + timedelta(days=offset)
        agenda_semanal.append({
            'fecha': fecha_item,
            'nombre_corto': dias_semana_cortos[fecha_item.weekday()],
            'mes_corto': meses_cortos[fecha_item.month - 1],
            'es_hoy': fecha_item == hoy,
            'citas': citas_por_fecha.get(fecha_item, []),
        })
    
    mis_solicitudes = SolicitudCita.objects.filter(
        terapeuta=mi_perfil
    ).order_by('-fecha_creacion')[:5]
    bloqueos_futuros = mi_perfil.bloqueos_agenda.filter(
        activo=True,
    ).filter(
        Q(tipo_bloqueo=BloqueoAgendaTerapeuta.TIPO_PERMANENTE) |
        Q(fecha_fin__gte=hoy) |
        Q(fecha_fin__isnull=True, fecha_inicio__gte=hoy)
    ).order_by('alcance', 'dia_semana', 'fecha_inicio', 'hora_inicio')
    context = {
        'terapeuta': mi_perfil,
        'citas_hoy': citas_hoy,
        'citas_proximas': citas_proximas,
        'agenda_semanal': agenda_semanal,
        'agenda_inicio_semana': inicio_semana,
        'agenda_fin_semana': fin_semana,
        'agenda_semana_offset': semana_offset,
        'mostrar_agenda_semanal': request.GET.get('ver_agenda') == '1',
        'fecha_bonita': fecha_bonita, # <--- Pasamos la fecha arreglada
        'mis_solicitudes': mis_solicitudes,
        'bloqueos_agenda': bloqueos_futuros,
        'bloqueo_form': BloqueoAgendaTerapeutaForm(),
    }
    
    return render(request, 'clinica/portal_terapeuta.html', context)


@login_required
def crear_bloqueo_terapeuta(request):
    if not hasattr(request.user, 'perfil_terapeuta'):
        return redirect('home')

    if request.method != 'POST':
        return redirect('portal_terapeuta')

    mi_perfil = request.user.perfil_terapeuta
    form = BloqueoAgendaTerapeutaForm(request.POST)
    if form.is_valid():
        bloqueo = form.save(commit=False)
        bloqueo.terapeuta = mi_perfil
        bloqueo.creado_por = request.user
        bloqueo.save()
        messages.success(request, 'Bloqueo de agenda guardado correctamente.')
    else:
        for _, errors in form.errors.items():
            for error in errors:
                messages.error(request, error)

    return redirect('portal_terapeuta')


@login_required
def eliminar_bloqueo_terapeuta(request, bloqueo_id):
    if not hasattr(request.user, 'perfil_terapeuta'):
        return redirect('home')

    bloqueo = get_object_or_404(
        BloqueoAgendaTerapeuta,
        id=bloqueo_id,
        terapeuta=request.user.perfil_terapeuta,
    )
    bloqueo.delete()
    messages.success(request, 'Bloqueo eliminado correctamente.')
    return redirect('portal_terapeuta')

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
        
        consultorio_id = request.POST.get('consultorio')

        # Creamos el ticket en nuestra "Sala de Espera" (SolicitudCita)
        SolicitudCita.objects.create(
            paciente_nombre=mi_perfil.nombre,
            telefono=mi_perfil.telefono, # Asumiendo que tu modelo Paciente tiene campo telefono
            fecha_deseada=fecha,
            hora_deseada=hora if hora else None,
            terapeuta_id=terapeuta_id if terapeuta_id else None,
            consultorio_id=consultorio_id if consultorio_id else None,
            notas_paciente=notas,
            estado='pendiente'
        )
        
        # Le avisamos que todo salio bien y lo regresamos a su portal
        messages.success(request, '¡Tu solicitud ha sido enviada! Recepción la revisará y te confirmará pronto.')
        return redirect('portal_paciente')
        
    # Si apenas va a abrir la pagina (GET), le mandamos la lista de terapeutas y consultorios
    terapeutas = Terapeuta.objects.filter(activo=True)
    from .models import Consultorio
    consultorios = Consultorio.objects.all()
    return render(request, 'clinica/solicitar_cita.html', {'terapeutas': terapeutas, 'consultorios': consultorios})

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
        consultorio_id = request.POST.get('consultorio')

        SolicitudCita.objects.create(
            paciente_nombre=paciente,
            telefono=telefono,
            fecha_deseada=fecha,
            hora_deseada=hora if hora else None,
            terapeuta=mi_perfil,
            consultorio_id=consultorio_id if consultorio_id else None,
            notas_paciente=f"SOLICITADO POR TERAPEUTA: {notas}",
            estado='pendiente'
        )
        
        messages.success(request, 'Solicitud enviada a Recepción. Espera su confirmación.')
        return redirect('portal_terapeuta')
        
    # --- NUEVO: Traemos la lista de pacientes ordenados alfabeticamente ---
    pacientes = Paciente.objects.all().order_by('nombre')
    from .models import Consultorio
    consultorios = Consultorio.objects.all()

    return render(request, 'clinica/solicitar_cita_terapeuta.html', {
        'pacientes': pacientes,
        'consultorios': consultorios,
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
        bloqueos = list(
            BloqueoAgendaTerapeuta.objects.filter(
                terapeuta_id=terapeuta_id,
                activo=True,
                fecha_inicio__lte=fecha_obj,
            ).filter(
                Q(tipo_bloqueo=BloqueoAgendaTerapeuta.TIPO_PERMANENTE) |
                Q(fecha_fin__gte=fecha_obj)
            ).order_by('hora_inicio', 'fecha_inicio')
        )

        bloqueo_total = next(
            (bloqueo for bloqueo in bloqueos if bloqueo.bloquea_fecha_hora(fecha_obj)),
            None,
        )

        if bloqueo_total and not bloqueo_total.es_bloqueo_parcial():
            return JsonResponse({
                'bloqueado': True,
                'mensaje': bloqueo_total.mensaje_bloqueo(),
                'horarios': [],
            })

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
            
            while hora_actual <= hora_fin:
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
            if slot in citas_ocupadas:
                continue
            bloqueo_slot = obtener_bloqueo_terapeuta_en_fecha(terapeuta_id, fecha_obj, slot)
            if bloqueo_slot:
                continue
            if slot not in citas_ocupadas:
                horarios_libres.append(slot.strftime('%H:%M'))

        mensaje = ''
        if any(b.es_bloqueo_parcial() and b.aplica_en_fecha(fecha_obj) for b in bloqueos):
            mensaje = 'Hay horas bloqueadas por el terapeuta en esta fecha.'

        # Devolver la lista ordenada y sin duplicados
        return JsonResponse({'horarios': sorted(list(set(horarios_libres))), 'mensaje': mensaje})

    except Exception as e:
        print(f"Error en radar: {e}")
        return JsonResponse({'horarios': [], 'error': 'Error procesando datos'})


@login_required
def checkout_cita(request, cita_id):
    """
    Procesa el cierre de sesión de una cita desde el portal del terapeuta.
    Solo acepta POST (el formulario se envía desde el modal en portal_terapeuta.html).
    Opcionalmente crea una SolicitudCita de seguimiento si el terapeuta lo indicó.
    """
    if not hasattr(request.user, 'perfil_terapeuta'):
        return redirect('home')

    mi_perfil = request.user.perfil_terapeuta
    cita = get_object_or_404(Cita, id=cita_id, terapeuta=mi_perfil)

    if not cita.es_finalizable:
        messages.warning(request, f'La cita de {cita.paciente.nombre} ya fue finalizada anteriormente.')
        return redirect('portal_terapeuta')

    if request.method != 'POST':
        return redirect('portal_terapeuta')

    form = CheckoutCitaForm(request.POST)
    if form.is_valid():
        # Actualizar cita
        cita.estatus = form.cleaned_data['estatus']
        metodo = form.cleaned_data.get('metodo_pago')
        costo = form.cleaned_data.get('costo')
        if metodo:
            cita.metodo_pago = metodo
        if costo is not None:
            cita.costo = costo
        cita.save()

        # Crear solicitud de seguimiento si fue solicitada
        if form.cleaned_data.get('solicitar_siguiente') and form.cleaned_data.get('siguiente_fecha'):
            SolicitudCita.objects.create(
                paciente_nombre=cita.paciente.nombre,
                telefono=cita.paciente.telefono or '',
                fecha_deseada=form.cleaned_data['siguiente_fecha'],
                hora_deseada=form.cleaned_data.get('siguiente_hora'),
                terapeuta=mi_perfil,
                notas_paciente=form.cleaned_data.get('notas_recepcion') or '',
                estado='pendiente',
            )
            messages.success(request, f'Sesión de {cita.paciente.nombre} cerrada. Solicitud de siguiente cita enviada a Recepción.')
        else:
            messages.success(request, f'Sesión de {cita.paciente.nombre} registrada correctamente.')
    else:
        messages.error(request, 'Hubo un error al procesar el cierre de sesión. Intenta de nuevo.')

    return redirect('portal_terapeuta')


# =============================================================================
# SPRINT 3 — VISTAS DE RECEPCIÓN
# =============================================================================

@login_required
def bitacora_diaria(request):
    """
    Bitácora de citas de un día concreto para el staff.
    GET ?fecha=YYYY-MM-DD  → muestra ese día (default: hoy).
    Acceso exclusivo a is_superuser.
    """
    if not request.user.is_superuser:
        return redirect('home')

    from datetime import date as date_type
    fecha_str = request.GET.get('fecha', '')
    try:
        fecha = date_type.fromisoformat(fecha_str) if fecha_str else date_type.today()
    except ValueError:
        fecha = date_type.today()

    citas_qs = (
        Cita.objects
        .filter(fecha=fecha)
        .select_related('paciente', 'terapeuta', 'servicio', 'consultorio', 'division')
        .prefetch_related('pacientes_adicionales')
        .order_by('hora', 'terapeuta__nombre')
    )

    # Evaluar queryset una sola vez para cómputos Python eficientes
    citas = list(citas_qs)

    # Indicador "Solicitó Seguimiento": SolicitudCita creada ese día para ese par (terapeuta, paciente)
    sol_set = set(
        SolicitudCita.objects
        .filter(fecha_creacion__date=fecha)
        .values_list('terapeuta_id', 'paciente_nombre')
    )
    for cita in citas:
        key = (cita.terapeuta_id, cita.paciente.nombre if cita.paciente else '')
        cita.solicito_seguimiento = key in sol_set

    # Stats del día
    total         = len(citas)
    asistieron    = sum(1 for c in citas if c.estatus == Cita.ESTATUS_SI_ASISTIO)
    no_asistieron = sum(1 for c in citas if c.estatus in (Cita.ESTATUS_NO_ASISTIO, Cita.ESTATUS_CANCELO))
    por_cerrar    = sum(1 for c in citas if c.es_finalizable)
    monto_dia     = sum(
        (c.costo or Decimal('0')) for c in citas if c.estatus == Cita.ESTATUS_SI_ASISTIO
    )

    solicitudes_pendientes_count = SolicitudCita.objects.filter(estado='pendiente').count()

    # ── Exportar Excel ────────────────────────────────────────────────────────
    if request.GET.get('export') == 'xlsx':
        bita_headers = [
            'Hora', 'Consultorio', 'Paciente', 'Terapeuta',
            'Servicio', 'Estatus', 'Método de Pago', 'Costo ($)', 'Solicitó Seguimiento',
        ]
        bita_rows = [
            [
                c.hora.strftime('%H:%M'),
                str(c.consultorio) if c.consultorio else '—',
                c.paciente.nombre if c.paciente else '—',
                str(c.terapeuta) if c.terapeuta else '—',
                str(c.servicio) if c.servicio else '—',
                c.get_estatus_display(),
                c.metodo_pago or '—',
                float(c.costo) if c.costo is not None else 0,
                'Sí' if c.solicito_seguimiento else 'No',
            ]
            for c in citas
        ]
        return _build_excel_response(
            filename=f"bitacora_{fecha.isoformat()}.xlsx",
            sheet_title=f"Bitácora {fecha.isoformat()}",
            headers=bita_headers,
            rows=bita_rows,
            col_widths=[8, 18, 24, 22, 22, 14, 16, 10, 18],
        )
    # ─────────────────────────────────────────────────────────────────────────

    meses = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
             'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
    fecha_bonita = f"{fecha.day} de {meses[fecha.month - 1]} de {fecha.year}"

    return render(request, 'clinica/bitacora_diaria.html', {
        'citas':                        citas,
        'fecha':                        fecha,
        'fecha_iso':                    fecha.isoformat(),
        'fecha_bonita':                 fecha_bonita,
        'total':                        total,
        'asistieron':                   asistieron,
        'no_asistieron':                no_asistieron,
        'por_cerrar':                   por_cerrar,
        'monto_dia':                    monto_dia,
        'solicitudes_pendientes_count': solicitudes_pendientes_count,
    })


@login_required
def reporte_general(request):
    """
    Reporte histórico de citas con filtros por rango de fechas y terapeuta.
    GET ?fecha_inicio=&fecha_fin=&terapeuta_id=&export=csv
    Acceso exclusivo a is_superuser.
    """
    if not request.user.is_superuser:
        return redirect('home')

    from datetime import date as date_type
    hoy = date_type.today()

    # Leer filtros (default: mes actual)
    fecha_inicio_str = request.GET.get('fecha_inicio', '')
    fecha_fin_str    = request.GET.get('fecha_fin', '')
    terapeuta_id     = request.GET.get('terapeuta_id', '')

    try:
        fecha_inicio = date_type.fromisoformat(fecha_inicio_str) if fecha_inicio_str else hoy.replace(day=1)
    except ValueError:
        fecha_inicio = hoy.replace(day=1)

    try:
        fecha_fin = date_type.fromisoformat(fecha_fin_str) if fecha_fin_str else hoy
    except ValueError:
        fecha_fin = hoy

    citas = (
        Cita.objects
        .filter(fecha__range=(fecha_inicio, fecha_fin))
        .select_related('paciente', 'terapeuta', 'servicio', 'consultorio', 'division')
        .order_by('-fecha', 'hora')
    )
    if terapeuta_id:
        citas = citas.filter(terapeuta_id=terapeuta_id)

    # ── Exportar Excel / CSV ──────────────────────────────────────────────────
    export = request.GET.get('export', '')
    if export in ('xlsx', 'csv'):
        headers = [
            'Fecha', 'Hora', 'Tipo', 'Paciente', 'Terapeuta',
            'Servicio', 'División', 'Consultorio',
            'Estatus', 'Método de Pago', 'Costo ($)',
        ]
        rows = [
            [
                c.fecha.strftime('%d/%m/%Y'),
                c.hora.strftime('%H:%M'),
                c.get_tipo_paciente_display(),
                c.paciente.nombre if c.paciente else '—',
                str(c.terapeuta) if c.terapeuta else '—',
                str(c.servicio)  if c.servicio  else '—',
                str(c.division)  if c.division  else '—',
                str(c.consultorio) if c.consultorio else '—',
                c.get_estatus_display(),
                c.metodo_pago or '—',
                float(c.costo) if c.costo is not None else 0,
            ]
            for c in citas
        ]
        if export == 'xlsx':
            return _build_excel_response(
                filename=f"reporte_intra_{fecha_inicio}_{fecha_fin}.xlsx",
                sheet_title="Reporte General",
                headers=headers,
                rows=rows,
                col_widths=[14, 8, 8, 24, 22, 22, 14, 18, 16, 16, 10],
            )
        # CSV fallback
        nombre = f"reporte_intra_{fecha_inicio}_{fecha_fin}.csv"
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = f'attachment; filename="{nombre}"'
        writer = csv.writer(response)
        writer.writerow(headers)
        writer.writerows(rows)
        return response

    # ── Stats del rango ───────────────────────────────────────────────────────
    total      = citas.count()
    asistieron = citas.filter(estatus=Cita.ESTATUS_SI_ASISTIO).count()
    monto_total = (
        citas.filter(estatus=Cita.ESTATUS_SI_ASISTIO)
             .aggregate(t=Sum('costo'))['t'] or Decimal('0')
    )

    terapeutas = Terapeuta.objects.filter(activo=True).order_by('nombre')

    return render(request, 'clinica/reporte_general.html', {
        'citas':            citas,
        'fecha_inicio':     fecha_inicio,
        'fecha_fin':        fecha_fin,
        'fecha_inicio_iso': fecha_inicio.isoformat(),
        'fecha_fin_iso':    fecha_fin.isoformat(),
        'terapeuta_id_sel': terapeuta_id,
        'terapeutas':       terapeutas,
        'total':            total,
        'asistieron':       asistieron,
        'monto_total':      monto_total,
    })


# =============================================================================
# SPRINT 4 — NÓMINA SEMANAL
# =============================================================================

def _semana_actual():
    """Devuelve (lunes, domingo) de la semana en curso."""
    hoy = date.today()
    lunes = hoy - timedelta(days=hoy.weekday())
    return lunes, lunes + timedelta(days=6)


def _parse_fechas_semana(request):
    """Extrae fecha_inicio y fecha_fin de los GET params, con fallback a semana actual."""
    lunes, domingo = _semana_actual()
    try:
        fi = date.fromisoformat(request.GET.get('fecha_inicio', ''))
    except ValueError:
        fi = lunes
    try:
        ff = date.fromisoformat(request.GET.get('fecha_fin', ''))
    except ValueError:
        ff = domingo
    return fi, ff


@login_required
def nomina_lista(request):
    """
    Panel de nómina semanal: muestra todos los terapeutas activos con
    sus sesiones, ingreso clínica, pago calculado y estado del corte.
    """
    if not request.user.is_superuser:
        return redirect('home')

    fecha_inicio, fecha_fin = _parse_fechas_semana(request)
    prev_inicio = fecha_inicio - timedelta(days=7)
    next_inicio = fecha_inicio + timedelta(days=7)

    terapeutas = Terapeuta.objects.filter(activo=True).order_by('nombre')

    # Cortes existentes para esta semana (una sola consulta)
    cortes_map = {
        c.terapeuta_id: c
        for c in CorteSemanal.objects.filter(
            fecha_inicio=fecha_inicio,
            terapeuta__in=terapeutas,
        )
    }

    # Stats de citas por terapeuta (una sola consulta agregada)
    stats_map = {
        row['terapeuta_id']: row
        for row in Cita.objects.filter(
            fecha__range=(fecha_inicio, fecha_fin),
            estatus=Cita.ESTATUS_SI_ASISTIO,
            terapeuta__in=terapeutas,
        ).values('terapeuta_id').annotate(
            total_citas=Count('id'),
            ingreso_clinica=Sum('costo'),
        )
    }

    filas = []
    total_clinica_global = Decimal('0')
    total_terapeutas_global = Decimal('0')
    total_citas_global = 0

    for t in terapeutas:
        corte = cortes_map.get(t.id)
        stats = stats_map.get(t.id, {})
        citas_count   = stats.get('total_citas', 0)
        ingreso       = stats.get('ingreso_clinica') or Decimal('0')
        total_pago    = corte.total_pago if corte else None

        # Solo incluir terapeutas con actividad o con corte generado
        if not citas_count and not corte:
            continue

        total_clinica_global    += ingreso
        total_terapeutas_global += total_pago or Decimal('0')
        total_citas_global      += citas_count

        filas.append({
            'terapeuta':      t,
            'citas_count':    citas_count,
            'ingreso_clinica': ingreso,
            'total_pago':     total_pago,
            'corte':          corte,
        })

    meses = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
             'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
    semana_label = (
        f"{fecha_inicio.day} de {meses[fecha_inicio.month-1]}"
        f" al {fecha_fin.day} de {meses[fecha_fin.month-1]} de {fecha_fin.year}"
    )

    return render(request, 'clinica/nomina_lista.html', {
        'filas':                    filas,
        'fecha_inicio':             fecha_inicio,
        'fecha_fin':                fecha_fin,
        'fecha_inicio_iso':         fecha_inicio.isoformat(),
        'fecha_fin_iso':            fecha_fin.isoformat(),
        'prev_inicio_iso':          prev_inicio.isoformat(),
        'prev_fin_iso':             (prev_inicio + timedelta(days=6)).isoformat(),
        'next_inicio_iso':          next_inicio.isoformat(),
        'next_fin_iso':             (next_inicio + timedelta(days=6)).isoformat(),
        'semana_label':             semana_label,
        'total_clinica_global':     total_clinica_global,
        'total_terapeutas_global':  total_terapeutas_global,
        'total_citas_global':       total_citas_global,
        'aprobados':  sum(1 for f in filas if f['corte'] and f['corte'].estatus == CorteSemanal.ESTATUS_APROBADO),
        'borradores': sum(1 for f in filas if f['corte'] and f['corte'].estatus == CorteSemanal.ESTATUS_BORRADOR),
    })


@login_required
def nomina_detalle(request, terapeuta_id):
    """
    Desglose de nómina de un terapeuta para una semana.
    Si el CorteSemanal aún no existe, muestra un preview sin persistir.
    Si existe en borrador, permite agregar BonoExtra y aprobarlo.
    """
    if not request.user.is_superuser:
        return redirect('home')

    terapeuta    = get_object_or_404(Terapeuta, id=terapeuta_id)
    fecha_inicio, fecha_fin = _parse_fechas_semana(request)

    try:
        corte = CorteSemanal.objects.get(terapeuta=terapeuta, fecha_inicio=fecha_inicio)
    except CorteSemanal.DoesNotExist:
        corte = None

    error_preview = None

    if corte:
        lineas_sesion = list(
            corte.lineas.filter(tipo=LineaNomina.TIPO_SESION)
                        .select_related('cita__paciente', 'cita__servicio')
                        .order_by('cita__fecha', 'cita__hora')
        )
        lineas_bono = list(
            corte.lineas.exclude(tipo=LineaNomina.TIPO_SESION)
        )
        bonos_extra = list(corte.bonos_extra.select_related('registrado_por').order_by('creado_en'))
        subtotal    = corte.subtotal_sesiones
        total_bonos = corte.total_bonos
        total_pago  = corte.total_pago
    else:
        preview = preview_nomina_semanal(terapeuta, fecha_inicio, fecha_fin)
        if 'error' in preview:
            error_preview = preview['error']
            lineas_sesion = lineas_bono = bonos_extra = []
            subtotal = total_bonos = total_pago = Decimal('0')
        else:
            lineas_sesion = [l for l in preview['lineas'] if l['tipo'] == LineaNomina.TIPO_SESION]
            lineas_bono   = [l for l in preview['lineas'] if l['tipo'] != LineaNomina.TIPO_SESION]
            bonos_extra   = []
            subtotal      = preview['subtotal_sesiones']
            total_bonos   = preview['total_bonos']
            total_pago    = preview['total_pago']

    puede_editar  = corte and corte.estatus == CorteSemanal.ESTATUS_BORRADOR
    puede_aprobar = puede_editar

    meses = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
             'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
    semana_label = (
        f"{fecha_inicio.day} de {meses[fecha_inicio.month-1]}"
        f" al {fecha_fin.day} de {meses[fecha_fin.month-1]} de {fecha_fin.year}"
    )

    # ── Exportar nómina Excel ─────────────────────────────────────────────────
    if request.GET.get('export') == 'xlsx' and not error_preview:
        nom_headers = ['Tipo', 'Concepto', 'Fecha', 'Hora', 'Paciente', 'Monto ($)']
        nom_rows = []
        for l in lineas_sesion:
            if isinstance(l, dict):
                fecha_c = l['cita'].fecha.strftime('%d/%m/%Y') if l.get('cita') and l['cita'].fecha else '—'
                hora_c  = l['cita'].hora.strftime('%H:%M') if l.get('cita') and l['cita'].hora else '—'
                pac     = l['cita'].paciente.nombre if l.get('cita') and l['cita'].paciente else '—'
            else:
                fecha_c = l.cita.fecha.strftime('%d/%m/%Y') if l.cita and l.cita.fecha else '—'
                hora_c  = l.cita.hora.strftime('%H:%M') if l.cita and l.cita.hora else '—'
                pac     = l.cita.paciente.nombre if l.cita and l.cita.paciente else '—'
            monto = float(l['monto'] if isinstance(l, dict) else l.monto)
            nom_rows.append(['Sesión', l['concepto'] if isinstance(l, dict) else l.concepto, fecha_c, hora_c, pac, monto])
        for l in lineas_bono:
            monto = float(l['monto'] if isinstance(l, dict) else l.monto)
            nom_rows.append(['Bono automático', l['concepto'] if isinstance(l, dict) else l.concepto, '—', '—', '—', monto])
        for b in bonos_extra:
            nom_rows.append(['Bono extra', b.concepto, '—', '—', '—', float(b.monto)])
        return _build_excel_response(
            filename=f"nomina_{terapeuta.nombre.replace(' ', '_')}_{fecha_inicio.isoformat()}.xlsx",
            sheet_title="Nómina Detalle",
            headers=nom_headers,
            rows=nom_rows,
            col_widths=[16, 35, 12, 8, 24, 12],
        )
    # ─────────────────────────────────────────────────────────────────────────

    return render(request, 'clinica/nomina_detalle.html', {
        'terapeuta':      terapeuta,
        'corte':          corte,
        'lineas_sesion':  lineas_sesion,
        'lineas_bono':    lineas_bono,
        'bonos_extra':    bonos_extra,
        'subtotal':       subtotal,
        'total_bonos':    total_bonos,
        'total_pago':     total_pago,
        'fecha_inicio':   fecha_inicio,
        'fecha_fin':      fecha_fin,
        'fecha_inicio_iso': fecha_inicio.isoformat(),
        'fecha_fin_iso':    fecha_fin.isoformat(),
        'semana_label':   semana_label,
        'puede_editar':   puede_editar,
        'puede_aprobar':  puede_aprobar,
        'error_preview':  error_preview,
    })


@login_required
def nomina_calcular(request, terapeuta_id):
    """POST: genera o recalcula el CorteSemanal en borrador."""
    if not request.user.is_superuser or request.method != 'POST':
        return redirect('nomina_lista')

    terapeuta = get_object_or_404(Terapeuta, id=terapeuta_id)
    fi_str = request.POST.get('fecha_inicio', '')
    ff_str = request.POST.get('fecha_fin', '')

    try:
        fi = date.fromisoformat(fi_str)
        ff = date.fromisoformat(ff_str)
    except ValueError:
        messages.error(request, 'Fechas inválidas.')
        return redirect('nomina_lista')

    try:
        corte = calcular_nomina_semanal(terapeuta, fi, ff)
        messages.success(
            request,
            f'Corte de {terapeuta.nombre} generado. '
            f'Sesiones: {corte.total_sesiones} | Total: ${corte.total_pago:,.2f}'
        )
    except ValueError as e:
        messages.error(request, str(e))

    url = reverse('nomina_detalle', args=[terapeuta_id])
    return redirect(f'{url}?fecha_inicio={fi_str}&fecha_fin={ff_str}')


@login_required
def nomina_aprobar(request, corte_id):
    """POST: aprueba y sella un CorteSemanal."""
    if not request.user.is_superuser or request.method != 'POST':
        return redirect('nomina_lista')

    corte = get_object_or_404(CorteSemanal, id=corte_id)
    fi_str = corte.fecha_inicio.isoformat()
    ff_str = corte.fecha_fin.isoformat()

    try:
        aprobar_corte_semanal(corte, request.user)
        messages.success(
            request,
            f'Nómina de {corte.terapeuta.nombre} aprobada y sellada. '
            f'Total: ${corte.total_pago:,.2f}'
        )
    except ValueError as e:
        messages.error(request, str(e))

    url = reverse('nomina_detalle', args=[corte.terapeuta_id])
    return redirect(f'{url}?fecha_inicio={fi_str}&fecha_fin={ff_str}')


@login_required
def nomina_agregar_bono(request, corte_id):
    """POST: agrega un BonoExtra a un CorteSemanal en borrador y recalcula totales."""
    if not request.user.is_superuser or request.method != 'POST':
        return redirect('nomina_lista')

    corte = get_object_or_404(CorteSemanal, id=corte_id)
    fi_str = corte.fecha_inicio.isoformat()
    ff_str = corte.fecha_fin.isoformat()

    if corte.estatus != CorteSemanal.ESTATUS_BORRADOR:
        messages.error(request, 'Solo se pueden agregar bonos a cortes en borrador.')
        url = reverse('nomina_detalle', args=[corte.terapeuta_id])
        return redirect(f'{url}?fecha_inicio={fi_str}&fecha_fin={ff_str}')

    concepto = request.POST.get('concepto', '').strip()
    monto_str = request.POST.get('monto', '').strip()

    try:
        monto = Decimal(monto_str)
        if monto <= 0:
            raise ValueError('El monto debe ser mayor a cero.')
        if not concepto:
            raise ValueError('El concepto es obligatorio.')
    except Exception as e:
        messages.error(request, f'Error al agregar bono: {e}')
    else:
        BonoExtra.objects.create(
            corte=corte,
            concepto=concepto,
            monto=monto,
            registrado_por=request.user,
        )
        # Recalcular para que los totales del corte reflejen el nuevo BonoExtra
        try:
            calcular_nomina_semanal(corte.terapeuta, corte.fecha_inicio, corte.fecha_fin)
            messages.success(request, f'Bono "{concepto}" de ${monto:,.2f} agregado correctamente.')
        except ValueError as e:
            messages.warning(request, f'Bono guardado pero no se pudo recalcular el total: {e}')

    url = reverse('nomina_detalle', args=[corte.terapeuta_id])
    return redirect(f'{url}?fecha_inicio={fi_str}&fecha_fin={ff_str}')


# =============================================================================
# MÓDULO DE TABULADORES — Misión 2
# =============================================================================

@login_required
def tabuladores_config(request):
    """
    Vista principal de configuración de tabuladores.
    Muestra dos pestañas: Tabulador General (categorías) y Reglas Individuales.
    Acceso exclusivo a is_staff.
    """
    if not request.user.is_staff:
        return redirect('home')

    from .models import TabuladorGeneral, ReglaTerapeuta

    categorias = TabuladorGeneral.objects.order_by('numero')
    reglas = (
        ReglaTerapeuta.objects
        .select_related('terapeuta', 'tabulador_base')
        .order_by('terapeuta__nombre')
    )
    return render(request, 'clinica/tabuladores_config.html', {
        'categorias': categorias,
        'reglas': reglas,
    })


@login_required
def tabuladores_editar_categoria(request, categoria_id):
    """POST: actualiza un TabuladorGeneral desde el modal de edición."""
    if not request.user.is_staff or request.method != 'POST':
        return redirect('tabuladores_config')

    from .models import TabuladorGeneral
    from .forms import TabuladorGeneralForm

    categoria = get_object_or_404(TabuladorGeneral, id=categoria_id)
    form = TabuladorGeneralForm(request.POST, instance=categoria)
    if form.is_valid():
        form.save()
        messages.success(request, f'Categoría {categoria.numero} actualizada correctamente.')
    else:
        errores = '; '.join(
            f'{field}: {", ".join(errs)}'
            for field, errs in form.errors.items()
        )
        messages.error(request, f'Error al guardar: {errores}')
    return redirect('tabuladores_config')


@login_required
def tabuladores_editar_regla(request, regla_id):
    """POST: actualiza una ReglaTerapeuta desde el modal de edición."""
    if not request.user.is_staff or request.method != 'POST':
        return redirect('tabuladores_config')

    from .models import ReglaTerapeuta
    from .forms import ReglaTerapeutaForm

    regla = get_object_or_404(ReglaTerapeuta, id=regla_id)
    form = ReglaTerapeutaForm(request.POST, instance=regla)
    if form.is_valid():
        form.save()
        messages.success(request, f'Regla de {regla.terapeuta.nombre} actualizada correctamente.')
    else:
        errores = '; '.join(
            f'{field}: {", ".join(errs)}'
            for field, errs in form.errors.items()
        )
        messages.error(request, f'Error al guardar: {errores}')
    return redirect('tabuladores_config')


# ─────────────────────────────────────────────────────────────
# DISPONIBILIDAD SEMANAL
# ─────────────────────────────────────────────────────────────

DIAS_SEMANA = [
    (0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'),
    (3, 'Jueves'), (4, 'Viernes'), (5, 'Sábado'), (6, 'Domingo'),
]

@login_required
def disponibilidad_semanal(request):
    terapeutas = Terapeuta.objects.filter(activo=True).order_by('nombre')
    terapeutas_data = []
    for t in terapeutas:
        horarios_qs = list(Horario.objects.filter(terapeuta=t).order_by('dia', 'hora_inicio'))
        dias_data = []
        for dia_num, dia_nombre in DIAS_SEMANA:
            slots = [h for h in horarios_qs if h.dia == dia_num]
            dias_data.append({'num': dia_num, 'nombre': dia_nombre, 'slots': slots})
        terapeutas_data.append({
            'terapeuta': t,
            'dias': dias_data,
            'total': len(horarios_qs),
        })
    return render(request, 'clinica/disponibilidad_semanal.html', {
        'terapeutas_data': terapeutas_data,
    })


@login_required
def agregar_disponibilidad(request):
    if request.method != 'POST':
        return redirect('disponibilidad_semanal')
    terapeuta = get_object_or_404(Terapeuta, id=request.POST.get('terapeuta'))
    dia = request.POST.get('dia')
    hora_inicio = request.POST.get('hora_inicio')
    hora_fin = request.POST.get('hora_fin')
    sede = request.POST.get('sede') or None
    if not (dia and hora_inicio and hora_fin and sede):
        messages.error(request, 'Completa todos los campos del horario, incluyendo la sede.')
        return redirect('disponibilidad_semanal')
    if hora_fin <= hora_inicio:
        messages.error(request, 'La hora de fin debe ser mayor que la de inicio.')
        return redirect('disponibilidad_semanal')
    Horario.objects.create(terapeuta=terapeuta, dia=int(dia), hora_inicio=hora_inicio, hora_fin=hora_fin, sede=sede)
    messages.success(request, f'Horario agregado para {terapeuta.nombre}.')
    return redirect('disponibilidad_semanal')


@login_required
def eliminar_disponibilidad(request, horario_id):
    if request.method != 'POST':
        return redirect('disponibilidad_semanal')
    horario = get_object_or_404(Horario, id=horario_id)
    nombre = horario.terapeuta.nombre
    horario.delete()
    messages.success(request, f'Horario eliminado para {nombre}.')
    return redirect('disponibilidad_semanal')


def api_consultorios_por_horario(request):
    """Devuelve los consultorios válidos para un terapeuta en una fecha y hora dadas."""
    from .models import Consultorio as ConsultorioModel
    terapeuta_id = request.GET.get('terapeuta')
    fecha_str    = request.GET.get('fecha')
    hora_str     = request.GET.get('hora')

    if not (terapeuta_id and fecha_str and hora_str):
        todos = list(ConsultorioModel.objects.values('id', 'nombre'))
        return JsonResponse({'consultorios': todos, 'filtrado': False})

    try:
        if len(hora_str) > 5:
            hora_str = hora_str[:5]
        fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        hora_obj  = datetime.strptime(hora_str, '%H:%M').time()
        dia_semana = fecha_obj.weekday()

        horarios_dia = list(Horario.objects.filter(terapeuta_id=terapeuta_id, dia=dia_semana))
        horario_activo = next(
            (h for h in horarios_dia if h.hora_inicio <= hora_obj <= h.hora_fin), None
        )

        if horario_activo and horario_activo.sede:
            qs = ConsultorioModel.objects.filter(sede=horario_activo.sede)
            consultorios = list(qs.values('id', 'nombre'))
            return JsonResponse({'consultorios': consultorios, 'filtrado': True, 'sede': horario_activo.sede})

        todos = list(ConsultorioModel.objects.values('id', 'nombre'))
        return JsonResponse({'consultorios': todos, 'filtrado': False})

    except Exception as e:
        print(f'Error en api_consultorios_por_horario: {e}')
        todos = list(ConsultorioModel.objects.values('id', 'nombre'))
        return JsonResponse({'consultorios': todos, 'filtrado': False})


# =============================================================================
# PORTAL EMPRESA
# =============================================================================

@login_required
def portal_empresa(request):
    if not hasattr(request.user, 'perfil_empresa'):
        return redirect('home')

    mi_empresa = request.user.perfil_empresa
    hoy = date.today()

    # Solo nombre y teléfono — no expediente
    pacientes = mi_empresa.pacientes.only('id', 'nombre', 'telefono').order_by('nombre')

    proximas_citas_qs = Cita.objects.filter(
        paciente__empresa=mi_empresa,
        fecha__gte=hoy,
        estatus__in=Cita.ESTATUS_ACTIVOS,
    ).select_related('paciente', 'terapeuta').order_by('fecha', 'hora')

    return render(request, 'clinica/portal_empresa.html', {
        'empresa': mi_empresa,
        'pacientes': pacientes,
        'total_pacientes': pacientes.count(),
        'proximas_citas': proximas_citas_qs[:10],
        'total_proximas_citas': proximas_citas_qs.count(),
        'hoy': hoy,
    })


@login_required
def registrar_paciente_empresa(request):
    if not hasattr(request.user, 'perfil_empresa'):
        return redirect('home')

    mi_empresa = request.user.perfil_empresa

    if request.method == 'POST':
        form = PacienteEmpresaForm(request.POST)
        if form.is_valid():
            paciente = form.save(commit=False)
            paciente.empresa = mi_empresa
            paciente.save()
            messages.success(request, f'Paciente {paciente.nombre} registrado correctamente.')
            return redirect('portal_empresa')
    else:
        form = PacienteEmpresaForm()

    return render(request, 'clinica/registrar_paciente_empresa.html', {
        'form': form,
        'empresa': mi_empresa,
    })


@login_required
def agendar_cita_empresa(request):
    if not hasattr(request.user, 'perfil_empresa'):
        return redirect('home')

    mi_empresa = request.user.perfil_empresa
    terapeutas = Terapeuta.objects.filter(activo=True)

    if request.method == 'POST':
        form = CitaEmpresaForm(request.POST, empresa=mi_empresa)
        if form.is_valid():
            cita = form.save(commit=False)
            cita.estatus = Cita.ESTATUS_SIN_CONFIRMAR

            # Verificar que el slot esté disponible
            conflicto = Cita.objects.filter(
                terapeuta_id=cita.terapeuta_id,
                fecha=cita.fecha,
                hora=cita.hora,
                estatus__in=Cita.ESTATUS_ACTIVOS,
            ).exists()

            if conflicto:
                messages.error(request, 'Este horario ya está ocupado. Por favor elige otro.')
            else:
                bloqueo = obtener_bloqueo_terapeuta_en_fecha(cita.terapeuta_id, cita.fecha, cita.hora)
                if bloqueo:
                    messages.error(request, f'El terapeuta tiene este horario bloqueado: {bloqueo.motivo or "sin motivo especificado"}.')
                else:
                    cita.save()
                    messages.success(request, f'Cita agendada para {cita.paciente.nombre} el {cita.fecha} a las {cita.hora:%H:%M}.')
                    return redirect('portal_empresa')
    else:
        form = CitaEmpresaForm(empresa=mi_empresa)

    return render(request, 'clinica/agendar_cita_empresa.html', {
        'form': form,
        'empresa': mi_empresa,
        'terapeutas': terapeutas,
    })
