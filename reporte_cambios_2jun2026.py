from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

OUTPUT = r"C:\Users\carlo\Documents\Freelancer\ConsultorioWeb\Reporte_Cambios_2Jun2026.pdf"

doc = SimpleDocTemplate(
    OUTPUT,
    pagesize=A4,
    rightMargin=2.5*cm,
    leftMargin=2.5*cm,
    topMargin=2.5*cm,
    bottomMargin=2.5*cm,
)

AZUL      = colors.HexColor("#1E3A5F")
AZUL_LIGHT= colors.HexColor("#2563EB")
GRIS_LINE = colors.HexColor("#CBD5E1")
GRIS_BG   = colors.HexColor("#F1F5F9")
NEGRO     = colors.HexColor("#1E293B")
GRIS_SUB  = colors.HexColor("#64748B")

styles = getSampleStyleSheet()

titulo_style = ParagraphStyle(
    "Titulo",
    fontSize=22,
    textColor=AZUL,
    fontName="Helvetica-Bold",
    spaceAfter=4,
    alignment=TA_LEFT,
)
fecha_style = ParagraphStyle(
    "Fecha",
    fontSize=10,
    textColor=GRIS_SUB,
    fontName="Helvetica",
    spaceAfter=2,
)
item_num_style = ParagraphStyle(
    "ItemNum",
    fontSize=12,
    textColor=AZUL_LIGHT,
    fontName="Helvetica-Bold",
    spaceBefore=14,
    spaceAfter=2,
)
item_title_style = ParagraphStyle(
    "ItemTitle",
    fontSize=13,
    textColor=NEGRO,
    fontName="Helvetica-Bold",
    spaceAfter=4,
)
body_style = ParagraphStyle(
    "Body",
    fontSize=10,
    textColor=NEGRO,
    fontName="Helvetica",
    leading=15,
    spaceAfter=4,
)
footer_style = ParagraphStyle(
    "Footer",
    fontSize=9,
    textColor=GRIS_SUB,
    fontName="Helvetica-Oblique",
    alignment=TA_CENTER,
)

cambios = [
    (
        "1. Restablecimiento de contraseñas — Jorge y Misty",
        "Se restableció el acceso al sistema para ambos usuarios. Ya pueden ingresar con su nueva contraseña sin ningún inconveniente."
    ),
    (
        "2. Historial de cambios",
        "Se implementó un registro de trazabilidad en el sistema. A partir de ahora queda documentado quién realizó cambios importantes (edición de citas, modificación de datos, etc.), con fecha y hora. Esto permite auditar cualquier modificación en caso de duda."
    ),
    (
        "3. Limpieza de catálogo de terapeutas",
        "Se corrigió la lista de terapeutas que aparece en todos los formularios de agendado, edición y solicitud de citas. Ahora únicamente aparecen los terapeutas que tienen disponibilidad configurada en el sistema. Los terapeutas sin horario registrado ya no aparecen como opciones seleccionables, evitando errores al agendar."
    ),
    (
        "4. Nuevo tipo de paciente: Crisis",
        "Se agregó la opción \"Crisis\" a la clasificación de tipo de paciente, que ya contaba con Nuevo, Seguimiento y Referido. Esto permite identificar y registrar correctamente las atenciones de urgencia o situaciones de crisis dentro del expediente y los reportes."
    ),
    (
        "5. Seguimiento sin reagendar — Vista \"Todo el tiempo\"",
        "El widget del dashboard que muestra pacientes sin reagendar (con las vistas de Ayer, Semana y Mes) ahora incluye una cuarta opción: \"Todo\". Esta vista muestra el acumulado histórico completo de pacientes que tuvieron sesión y aún no tienen una próxima cita agendada, sin límite de fecha."
    ),
    (
        "6. Corrección de validación al reagendar / cancelar",
        "Se corrigió un error en el que el sistema bloqueaba un espacio en el calendario cuando la cita tenía estatus \"Reagendo\", impidiendo agendar a otro paciente en ese mismo horario y con ese terapeuta. Dado que una cita reagendada ya no ocupa el espacio, el sistema ahora lo libera correctamente y permite agendarlo sin restricciones. Lo mismo aplica para citas con estatus \"Canceló\"."
    ),
]

story = []

story.append(Paragraph("Reporte de Cambios", titulo_style))
story.append(Paragraph("2 de junio de 2026", fecha_style))
story.append(Spacer(1, 6))
story.append(HRFlowable(width="100%", thickness=2, color=AZUL, spaceAfter=16))

for title, body in cambios:
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRIS_LINE, spaceBefore=6, spaceAfter=8))
    story.append(Paragraph(title, item_title_style))
    story.append(Paragraph(body, body_style))

story.append(Spacer(1, 20))
story.append(HRFlowable(width="100%", thickness=1, color=GRIS_LINE))
story.append(Spacer(1, 6))
story.append(Paragraph("Todos los cambios fueron aplicados y están activos en el sistema.", footer_style))

doc.build(story)
print(f"PDF generado: {OUTPUT}")
