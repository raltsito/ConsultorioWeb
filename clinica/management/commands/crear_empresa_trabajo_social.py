from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from clinica.models import Empresa, Division


class Command(BaseCommand):
    help = 'Crea el usuario y empresa de Trabajo Social'

    def handle(self, *args, **options):
        username = 'trabajo_social'
        password = 'ts2026'

        division, div_created = Division.objects.get_or_create(nombre='Trabajo Social')
        if div_created:
            self.stdout.write(f'  División creada: {division.nombre}')
        else:
            self.stdout.write(f'  División existente: {division.nombre}')

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'  El usuario "{username}" ya existe, no se modifica.'))
            user = User.objects.get(username=username)
        else:
            user = User.objects.create_user(username=username, password=password)
            self.stdout.write(self.style.SUCCESS(f'  Usuario creado: {username} / {password}'))

        empresa, emp_created = Empresa.objects.get_or_create(
            nombre='Trabajo Social',
            defaults={'usuario': user, 'division': division, 'activo': True},
        )

        if emp_created:
            self.stdout.write(self.style.SUCCESS(f'  Empresa creada: {empresa.nombre}'))
        else:
            self.stdout.write(self.style.WARNING(f'  Empresa ya existía: {empresa.nombre}'))
            if not empresa.usuario:
                empresa.usuario = user
            if not empresa.division:
                empresa.division = division
            empresa.save()

        self.stdout.write(self.style.SUCCESS('\nListo. Credenciales: trabajo_social / ts2026'))
