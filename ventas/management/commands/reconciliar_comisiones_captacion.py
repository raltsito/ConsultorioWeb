from django.core.management.base import BaseCommand, CommandError

from ventas.models import Captacion
from ventas.services import reconciliar_comisiones_pendientes


class Command(BaseCommand):
    help = "Evalúa y genera comisiones de captación elegibles."

    ESTADOS_RESUMEN = (
        ("generada", "Generadas"),
        ("ya_existia", "Ya existentes"),
        ("sin_cita_asistida", "Sin primera asistencia"),
        ("cita_sin_pago", "Sin pago"),
        ("sin_cuenta", "Sin cuenta"),
        ("sin_importe_servicio", "Sin importe servicio"),
        ("importe_servicio_invalido", "Importe servicio inválido"),
        ("datos_inconsistentes", "Datos inconsistentes"),
        ("error", "Errores"),
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--captacion-id",
            type=int,
            help="Evalúa únicamente la captación indicada.",
        )

    def handle(self, *args, **options):
        captacion_id = options.get("captacion_id")
        if captacion_id is not None and not Captacion.objects.filter(
            pk=captacion_id
        ).exists():
            raise CommandError(f"No existe la captación {captacion_id}.")

        resumen = reconciliar_comisiones_pendientes(
            captacion_id=captacion_id,
        )
        self.stdout.write(f"Evaluadas: {resumen.evaluadas}")
        estados_mostrados = set()
        for estado, etiqueta in self.ESTADOS_RESUMEN:
            cantidad = resumen.conteos.get(estado, 0)
            self.stdout.write(f"{etiqueta}: {cantidad}")
            estados_mostrados.add(estado)

        estados_adicionales = set(resumen.conteos) - estados_mostrados
        for estado in sorted(estados_adicionales):
            self.stdout.write(f"{estado}: {resumen.conteos[estado]}")
