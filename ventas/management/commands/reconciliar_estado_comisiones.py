from django.core.management.base import BaseCommand, CommandError

from ventas.models import ComisionCaptacion
from ventas.services import reconciliar_comisiones_generadas


class Command(BaseCommand):
    help = "Reconcilia el estado financiero de comisiones ya generadas."

    ESTADOS_RESUMEN = (
        ("sin_cambios", "Sin cambios"),
        ("suspendida", "Suspendidas"),
        ("reactivada", "Reactivadas"),
        ("estado_no_reconciliable", "Estados no reconciliables"),
        ("datos_inconsistentes", "Datos inconsistentes"),
        ("error", "Errores"),
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--comision-id",
            type=int,
            help="Reconcilia únicamente la comisión indicada.",
        )

    def handle(self, *args, **options):
        comision_id = options.get("comision_id")
        if comision_id is not None and not ComisionCaptacion.objects.filter(
            pk=comision_id
        ).exists():
            raise CommandError(f"No existe la comisión {comision_id}.")

        resumen = reconciliar_comisiones_generadas(
            comision_id=comision_id,
        )
        self.stdout.write(f"Evaluadas: {resumen.evaluadas}")
        for estado, etiqueta in self.ESTADOS_RESUMEN:
            cantidad = resumen.conteos.get(estado, 0)
            self.stdout.write(f"{etiqueta}: {cantidad}")
