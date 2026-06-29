from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER

OUTPUT = r"C:\Users\carlo\Documents\Freelancer\ConsultorioWeb\Solicitud_Boton_Alta_Paciente.pdf"

doc = SimpleDocTemplate(
    OUTPUT,
    pagesize=A4,
    rightMargin=2.5*cm,
    leftMargin=2.5*cm,
    topMargin=2.5*cm,
    bottomMargin=2.5*cm,
)

AZUL       = colors.HexColor("#1E3A5F")
AZUL_LIGHT = colors.HexColor("#2563EB")
GRIS_LINE  = colors.HexColor("#CBD5E1")
GRIS_BG    = colors.HexColor("#F1F5F9")
NEGRO      = colors.HexColor("#1E293B")
GRIS_SUB   = colors.HexColor("#64748B")
VERDE      = colors.HexColor("#16A34A")

styles = getSampleStyleSheet()

titulo_style = ParagraphStyle(
    "Titulo", fontSize=22, textColor=AZUL, fontName="Helvetica-Bold",
    spaceAfter=4, alignment=TA_LEFT,
)
meta_style = ParagraphStyle(
    "Meta", fontSize=10, textColor=GRIS_SUB, fontName="Helvetica",
    spaceAfter=2, leading=14,
)
section_style = ParagraphStyle(
    "Section", fontSize=13, textColor=AZUL_LIGHT, fontName="Helvetica-Bold",
    spaceBefore=16, spaceAfter=6,
)
subsection_style = ParagraphStyle(
    "Subsection", fontSize=11, textColor=NEGRO, fontName="Helvetica-Bold",
    spaceBefore=10, spaceAfter=3,
)
body_style = ParagraphStyle(
    "Body", fontSize=10, textColor=NEGRO, fontName="Helvetica",
    leading=15, spaceAfter=4,
)
bullet_style = ParagraphStyle(
    "Bullet", fontSize=10, textColor=NEGRO, fontName="Helvetica",
    leading=14, spaceAfter=3, leftIndent=14, bulletIndent=2,
)
check_style = ParagraphStyle(
    "Check", fontSize=10, textColor=NEGRO, fontName="Helvetica",
    leading=14, spaceAfter=4, leftIndent=14,
)
code_style = ParagraphStyle(
    "Code", fontSize=9, textColor=AZUL, fontName="Courier",
    leading=13, spaceAfter=2, leftIndent=8,
)
footer_style = ParagraphStyle(
    "Footer", fontSize=9, textColor=GRIS_SUB, fontName="Helvetica-Oblique",
    alignment=TA_CENTER,
)

def code_box(lines):
    cell = [Paragraph(line, code_style) for line in lines]
    t = Table([[cell]], colWidths=[16.4*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), GRIS_BG),
        ('BOX', (0, 0), (-1, -1), 0.5, GRIS_LINE),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    return t

story = []

# ── Encabezado ──────────────────────────────────────────────
story.append(Paragraph("Solicitud de Cambio", titulo_style))
story.append(Paragraph("Botón de “Alta” en el expediente del paciente", meta_style))
story.append(Spacer(1, 4))
story.append(Paragraph("Fecha: 23 de junio de 2026", meta_style))
story.append(Paragraph("Módulo: Expediente de paciente / Panel principal (Admin y Recepción)", meta_style))
story.append(Spacer(1, 6))
story.append(HRFlowable(width="100%", thickness=2, color=AZUL, spaceAfter=16))

# ── 1. Objetivo ──────────────────────────────────────────────
story.append(Paragraph("1. Objetivo", section_style))
story.append(Paragraph(
    "Agregar un botón en el expediente de cada paciente que permita marcarlo como "
    "“dado de alta”. A partir de ese momento, ese paciente debe dejar de contarse en el "
    "widget <b>“Sin Reagendar”</b> del panel principal de Admin y Recepción, ya que su "
    "proceso se considera cerrado y no se espera que reagende.",
    body_style
))

# ── 2. Contexto actual ───────────────────────────────────────
story.append(Paragraph("2. Contexto actual (cómo funciona hoy)", section_style))
story.append(Paragraph(
    "El widget “Sin Reagendar” cuenta a todo paciente que cumple <b>ambas</b> condiciones:",
    body_style
))
story.append(Paragraph("• Tuvo una cita con estatus “Asistió” o “No asistió” dentro del periodo "
                        "seleccionado (Ayer / Semana / Mes / Todo).", bullet_style))
story.append(Paragraph("• No tiene actualmente una cita futura activa ni una solicitud de cita pendiente.", bullet_style))
story.append(Paragraph(
    "Esta lógica está duplicada en dos lugares de <b>clinica/views.py</b> que deben mantenerse "
    "sincronizados:",
    body_style
))
story.append(Paragraph("• <b>_sin_reagendar_stats()</b> — alimenta las tarjetas del dashboard (home).", bullet_style))
story.append(Paragraph("• <b>api_sin_reagendar()</b> — endpoint <b>/api/sin-reagendar/</b> que alimenta el modal "
                        "con el detalle de pacientes del widget.", bullet_style))
story.append(Paragraph(
    "Hoy <b>no existe</b> ningún campo en el modelo <b>Paciente</b> para marcar alta o baja de "
    "seguimiento; hay que agregarlo.",
    body_style
))

# ── 3. Comportamiento esperado ───────────────────────────────
story.append(Paragraph("3. Comportamiento esperado", section_style))
story.append(Paragraph("• El botón aparece en el expediente del paciente "
                        "(<b>clinica/templates/clinica/detalle_paciente.html</b>), visible "
                        "<b>solo para administradores</b> (mismo criterio que ya se usa hoy para "
                        "subir documentos al expediente: <b>request.user.is_superuser</b>).", bullet_style))
story.append(Paragraph("• Texto dinámico: “Dar de alta” si el paciente sigue activo en "
                        "seguimiento, o “Reactivar seguimiento” si ya está dado de alta.", bullet_style))
story.append(Paragraph("• Antes de aplicar el cambio debe pedir confirmación (modal), explicando que el "
                        "paciente dejará de aparecer en el widget de seguimiento.", bullet_style))
story.append(Paragraph("• Es <b>reversible</b>: un administrador puede revertir el alta en cualquier "
                        "momento desde el mismo botón.", bullet_style))
story.append(Paragraph("• Mientras el paciente esté dado de alta, debe excluirse de <b>ambas</b> "
                        "funciones (_sin_reagendar_stats y api_sin_reagendar), en las 4 vistas de periodo "
                        "(día / semana / mes / todo).", bullet_style))
story.append(Paragraph("• El expediente debe mostrar una etiqueta visible (badge) cuando el paciente "
                        "esté dado de alta.", bullet_style))

# ── 4. Detalle técnico sugerido ──────────────────────────────
story.append(Paragraph("4. Detalle técnico sugerido", section_style))

story.append(Paragraph("4.1 Modelo — clinica/models.py (clase Paciente, línea ~381)", subsection_style))
story.append(Paragraph("Agregar dos campos nuevos:", body_style))
story.append(code_box([
    "dado_de_alta = models.BooleanField(default=False, verbose_name=\"Dado de alta\")",
    "fecha_alta = models.DateTimeField(null=True, blank=True)",
]))
story.append(Spacer(1, 4))
story.append(Paragraph("Generar y aplicar la migración correspondiente "
                        "(<b>python manage.py makemigrations clinica</b> y <b>migrate</b>).", body_style))

story.append(Paragraph("4.2 Vista nueva — clinica/views.py", subsection_style))
story.append(Paragraph(
    "Crear una vista <b>toggle_alta_paciente(request, paciente_id)</b> que:",
    body_style
))
story.append(Paragraph("• Requiere login y valida que <b>request.user.is_superuser</b> sea verdadero.", bullet_style))
story.append(Paragraph("• Solo acepta POST.", bullet_style))
story.append(Paragraph("• Invierte el valor de <b>paciente.dado_de_alta</b>. Si queda en True, guarda "
                        "<b>fecha_alta = timezone.now()</b>; si queda en False, limpia <b>fecha_alta</b>.", bullet_style))
story.append(Paragraph("• Muestra un mensaje de confirmación (messages.success) y redirige de vuelta a "
                        "<b>detalle_paciente</b>.", bullet_style))

story.append(Paragraph("4.3 Ruta nueva — core/urls.py", subsection_style))
story.append(code_box([
    "path('pacientes/&lt;int:paciente_id&gt;/toggle-alta/',",
    "     clinica_views.toggle_alta_paciente, name='toggle_alta_paciente'),",
]))

story.append(Paragraph("4.4 Template — clinica/templates/clinica/detalle_paciente.html", subsection_style))
story.append(Paragraph("• Agregar el botón junto a los datos generales del paciente, dentro de un "
                        "&lt;form method=\"post\"&gt; que apunte a la nueva ruta, envuelto en el mismo "
                        "condicional que ya oculta/muestra opciones solo para administradores.", bullet_style))
story.append(Paragraph("• Usar un modal de confirmación de Bootstrap (la plantilla ya usa "
                        "Bootstrap 5 + bootstrap-icons).", bullet_style))
story.append(Paragraph("• Mostrar una etiqueta/badge “Dado de alta” cuando "
                        "<b>paciente.dado_de_alta</b> sea verdadero.", bullet_style))
story.append(Paragraph("• Evitar el color coral (#EF5350) en cualquier elemento nuevo de UI; usar la "
                        "paleta azul ya establecida en el sistema.", bullet_style))

story.append(Paragraph("4.5 Excluir del widget — clinica/views.py", subsection_style))
story.append(Paragraph("• En <b>_sin_reagendar_stats()</b>: agregar el filtro "
                        "<b>paciente__dado_de_alta=False</b> a los querysets <b>citas</b> y "
                        "<b>citas_todo</b> (líneas ~327 y ~335).", bullet_style))
story.append(Paragraph("• En <b>api_sin_reagendar()</b>: agregar el mismo filtro "
                        "<b>paciente__dado_de_alta=False</b> al queryset <b>citas_qs</b> "
                        "(línea ~689).", bullet_style))

# ── 5. Criterios de aceptación ───────────────────────────────
story.append(Paragraph("5. Criterios de aceptación", section_style))
criterios = [
    "El botón aparece en el expediente y solo es visible para administradores.",
    "Al confirmar, el paciente deja de aparecer de inmediato en el widget del panel principal "
    "(las 4 vistas: día, semana, mes, todo) y en /api/sin-reagendar/.",
    "El botón cambia su texto y permite revertir el alta en cualquier momento.",
    "Al revertir el alta, el paciente vuelve a contarse normalmente si cumple las condiciones "
    "actuales del widget.",
    "El expediente muestra una etiqueta visible cuando el paciente está dado de alta.",
    "No se rompe el comportamiento actual del widget para pacientes sin esta marca.",
]
for c in criterios:
    story.append(Paragraph(f"☐  {c}", check_style))

# ── 6. Notas ──────────────────────────────────────────────────
story.append(Paragraph("6. Notas / puntos a confirmar con el equipo", section_style))
story.append(Paragraph(
    "• No es obligatorio para este alcance, pero se puede evaluar si al agendarle una nueva "
    "cita a un paciente dado de alta, el sistema le quita automáticamente la marca (queda abierto "
    "a decidir en una siguiente iteración).",
    bullet_style
))
story.append(Paragraph(
    "• Agregar los campos <b>dado_de_alta</b> y <b>fecha_alta</b> también al admin de Django, "
    "para poder revisarlos manualmente si hace falta auditarlos.",
    bullet_style
))
story.append(Paragraph(
    "• La lógica completa del widget actual está documentada en clinica/views.py, dentro de "
    "las funciones mencionadas en la sección 2.",
    bullet_style
))

story.append(Spacer(1, 20))
story.append(HRFlowable(width="100%", thickness=1, color=GRIS_LINE))
story.append(Spacer(1, 6))
story.append(Paragraph("Cualquier duda sobre el alcance, favor de confirmar antes de implementar.", footer_style))

doc.build(story)
print(f"PDF generado: {OUTPUT}")
