from django.core.management.base import BaseCommand, CommandError

from clinica.services_catalogo_backfill import (
    InventarioCatalogoIncompatible,
    SERVICIOS_ESPERADOS,
    aplicar_backfill_catalogo,
    construir_plan_backfill,
)


class Command(BaseCommand):
    help = 'Valida o aplica la matriz curada del Catálogo de Servicios.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Aplica el backfill de forma atómica después del preflight.',
        )

    def handle(self, *args, **options):
        aplicar = options['apply']
        self.stdout.write(
            self.style.WARNING(
                'BACKFILL CATÁLOGO — APPLY'
                if aplicar
                else 'BACKFILL CATÁLOGO — DRY RUN'
            )
        )

        plan = construir_plan_backfill()
        self._mostrar_plan(plan)
        if plan.conflictos:
            if not aplicar:
                self.stdout.write(self.style.WARNING('NO SE MODIFICÓ NINGÚN DATO'))
            raise CommandError(
                'INVENTARIO CAMBIÓ — REQUIERE REVISIÓN DE MATRIZ'
            )

        if aplicar:
            try:
                aplicar_backfill_catalogo()
            except InventarioCatalogoIncompatible as error:
                raise CommandError(str(error)) from error
            self.stdout.write(self.style.SUCCESS('BACKFILL APLICADO CORRECTAMENTE'))
        else:
            self.stdout.write(self.style.WARNING('NO SE MODIFICÓ NINGÚN DATO'))

    def _mostrar_plan(self, plan):
        self.stdout.write(
            f'Inventario: esperados={len(SERVICIOS_ESPERADOS)}, '
            f'encontrados={len(plan.servicios)}'
        )
        self.stdout.write(
            'Categorías que se crearían: '
            + (', '.join(item.codigo for item in plan.categorias_a_crear) or 'ninguna')
        )
        self.stdout.write(
            'Categorías ya existentes: '
            + (', '.join(item.codigo for item in plan.categorias_existentes) or 'ninguna')
        )
        self.stdout.write('Servicios canónicos: 13')
        self.stdout.write('Variantes históricas: 6')
        self.stdout.write('Inventario encontrado (precio sólo contextual):')
        for servicio in plan.servicios:
            self.stdout.write(
                f'  ID {servicio.id}: {servicio.nombre} | precio={servicio.precio!r}'
            )

        for cambio in plan.cambios:
            self.stdout.write(
                f'ID {cambio.servicio_id} {cambio.servicio_nombre}: '
                f'{cambio.campo}: {cambio.valor_actual!r} '
                f'→ {cambio.valor_esperado!r}'
            )

        for conflicto in plan.conflictos:
            self.stdout.write(self.style.ERROR(f'CONFLICTO: {conflicto}'))
