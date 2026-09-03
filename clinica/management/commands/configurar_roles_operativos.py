from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


PERMISOS_POR_GRUPO = {
    'Dirección General': (
        ('ventas', 'authorize_captacion_commission'),
    ),
    'Recepción': (
        ('clinica', 'view_reception_ledger'),
        ('clinica', 'register_reception_payment'),
        ('clinica', 'confirm_reception_payment'),
    ),
    'Finanzas': (
        ('ventas', 'view_liquidaciones'),
        ('ventas', 'create_liquidacion'),
        ('ventas', 'change_draft_liquidacion'),
        ('ventas', 'cancel_draft_liquidacion'),
        ('ventas', 'pay_liquidacion'),
    ),
    'Sistemas': (),
}


class Command(BaseCommand):
    help = 'Crea y configura los grupos operativos sin asignar usuarios.'

    def handle(self, *args, **options):
        permisos_resueltos = {}
        faltantes = []

        for grupo, referencias in PERMISOS_POR_GRUPO.items():
            permisos_grupo = []
            for app_label, codename in referencias:
                permiso = (
                    Permission.objects
                    .filter(
                        content_type__app_label=app_label,
                        codename=codename,
                    )
                    .first()
                )
                if permiso is None:
                    faltantes.append(f'{app_label}.{codename}')
                else:
                    permisos_grupo.append(permiso)
            permisos_resueltos[grupo] = permisos_grupo

        if faltantes:
            detalle = ', '.join(sorted(faltantes))
            raise CommandError(
                'No se modificaron grupos porque faltan permisos: '
                f'{detalle}. Aplica primero las migraciones correspondientes.'
            )

        resumen = []
        with transaction.atomic():
            for nombre, permisos in permisos_resueltos.items():
                grupo, creado = Group.objects.get_or_create(name=nombre)
                grupo.permissions.set(permisos)
                resumen.append((grupo, creado, permisos))

        self.stdout.write(self.style.SUCCESS('Roles operativos configurados.'))
        for grupo, creado, permisos in resumen:
            estado = 'creado' if creado else 'actualizado'
            nombres = ', '.join(
                f'{permiso.content_type.app_label}.{permiso.codename}'
                for permiso in permisos
            ) or 'sin permisos asignados'
            self.stdout.write(f'- {grupo.name}: {estado}; {nombres}')
        self.stdout.write('Usuarios asignados automáticamente: 0')
