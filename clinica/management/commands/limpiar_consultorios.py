"""
Limpia registros duplicados y mal escritos de Consultorio.
Reasigna las citas que apuntan a registros viejos a los correctos,
corrige el campo sede de los registros buenos y elimina los viejos.
"""
from django.core.management.base import BaseCommand
from clinica.models import Consultorio, Cita, SolicitudCita


class Command(BaseCommand):
    help = 'Limpia consultorios duplicados y mal escritos en la BD'

    # (id_viejo, id_nuevo, sede_correcta)
    MIGRACIONES = [
        (8,  17, 'republica'),   # "Repblica - Sala 1" -> "República - Sala 1"
        (9,  18, 'republica'),   # "Repblica - Sala 2" -> "República - Sala 2"
        (10, 19, 'republica'),   # "Repblica - Sala 3" -> "República - Sala 3"
        (5,  16, 'zoom'),        # "Zoom"              -> "Zoom / Online"
        (13, 20, 'colinas'),     # "Colinas - nica"    -> "Colinas - Única"
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué haría sin hacer cambios reales',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('--- MODO DRY-RUN: no se guardan cambios ---'))

        for id_viejo, id_nuevo, sede in self.MIGRACIONES:
            try:
                viejo = Consultorio.objects.get(pk=id_viejo)
            except Consultorio.DoesNotExist:
                self.stdout.write(f'  [skip] ID {id_viejo} no existe (ya fue eliminado)')
                continue

            try:
                nuevo = Consultorio.objects.get(pk=id_nuevo)
            except Consultorio.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'  [ERROR] ID destino {id_nuevo} no existe, saltando'))
                continue

            citas      = Cita.objects.filter(consultorio_id=id_viejo)
            solicitudes = SolicitudCita.objects.filter(consultorio_id=id_viejo)

            self.stdout.write(
                f'  "{viejo.nombre}" (id={id_viejo}) -> "{nuevo.nombre}" (id={id_nuevo}): '
                f'{citas.count()} cita(s), {solicitudes.count()} solicitud(es)'
            )

            if not dry_run:
                citas.update(consultorio_id=id_nuevo)
                solicitudes.update(consultorio_id=id_nuevo)
                viejo.delete()
                self.stdout.write(self.style.SUCCESS(f'    Reasignado y eliminado ID {id_viejo}'))

            # Corregir sede del registro destino si está vacía
            if not nuevo.sede:
                self.stdout.write(f'    Actualizando sede de "{nuevo.nombre}" -> "{sede}"')
                if not dry_run:
                    nuevo.sede = sede
                    nuevo.save(update_fields=['sede'])

        if not dry_run:
            self.stdout.write(self.style.SUCCESS('\nLimpieza completada.'))
        else:
            self.stdout.write(self.style.WARNING('\nDry-run terminado. Ejecuta sin --dry-run para aplicar cambios.'))
