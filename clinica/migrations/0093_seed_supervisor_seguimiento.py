from django.conf import settings
from django.db import migrations


USERNAME = 'supervisor_seguimiento'
PASSWORD_HASH = 'pbkdf2_sha256$1200000$nHDZZlzBNeZpLMriYRCwAk$XV9neUInTqPIIILTh4sMHyMHBkN47AXFuC9kBlqFcYQ='


def crear_supervisor_seguimiento(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    SupervisorSeguimiento = apps.get_model('clinica', 'SupervisorSeguimiento')

    user, _ = User.objects.get_or_create(
        username=USERNAME,
        defaults={
            'password': PASSWORD_HASH,
            'is_active': True,
            'is_staff': False,
            'is_superuser': False,
        },
    )
    user.password = PASSWORD_HASH
    user.is_active = True
    user.is_staff = False
    user.is_superuser = False
    user.save(update_fields=['password', 'is_active', 'is_staff', 'is_superuser'])

    perfil, _ = SupervisorSeguimiento.objects.get_or_create(
        usuario=user,
        defaults={'nombre': 'Supervisor de Seguimiento', 'activo': True},
    )
    perfil.nombre = 'Supervisor de Seguimiento'
    perfil.activo = True
    perfil.save(update_fields=['nombre', 'activo'])


def revertir_supervisor_seguimiento(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    User.objects.filter(username=USERNAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('clinica', '0092_grupo_supervisor_seguimiento'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(crear_supervisor_seguimiento, revertir_supervisor_seguimiento),
    ]
