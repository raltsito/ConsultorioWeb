from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from clinica.models import Paciente


class Command(BaseCommand):
    help = 'Borra TODOS los pacientes del sistema para iniciar de cero'

    def add_arguments(self, parser):
        parser.add_argument(
            '--borrar-usuarios',
            action='store_true',
            help='También borra los usuarios asociados a los pacientes',
        )

    def handle(self, *args, **options):
        cantidad_pacientes = Paciente.objects.count()
        
        if cantidad_pacientes == 0:
            self.stdout.write(self.style.SUCCESS('✓ No hay pacientes que borrar'))
            return

        # Confirmación
        self.stdout.write(self.style.WARNING(f'\n⚠️  ADVERTENCIA: Vas a borrar {cantidad_pacientes} paciente(s)'))
        confirmacion = input('¿Estás seguro? Escribe "SI" para confirmar: ')
        
        if confirmacion.upper() != 'SI':
            self.stdout.write(self.style.ERROR('✗ Operación cancelada'))
            return

        # Obtener usuarios asociados antes de borrar
        usuarios_ids = list(
            Paciente.objects.values_list('usuario_id', flat=True)
            .filter(usuario__isnull=False)
        )

        # Borrar pacientes
        Paciente.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'✓ {cantidad_pacientes} paciente(s) borrado(s)'))

        # Borrar usuarios si se solicita
        if options['borrar_usuarios'] and usuarios_ids:
            cantidad_usuarios = User.objects.filter(id__in=usuarios_ids).delete()[0]
            self.stdout.write(self.style.SUCCESS(f'✓ {cantidad_usuarios} usuario(s) borrado(s)'))

        self.stdout.write(self.style.SUCCESS('\n✓ Expedientes listos para llenar desde cero'))
