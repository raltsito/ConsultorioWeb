from django.conf import settings
from django.db import migrations


USERNAME = 'benja_administrativo'
PASSWORD_HASH = 'pbkdf2_sha256$1200000$feU3MF42oPKLKLky1awG5t$ttSTQzZx++7g+f485Kp9jdu6wi1FvPkm8MLinXbXdRo='


def crear_benja_administrativo(apps, schema_editor):
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
        defaults={'nombre': 'Benja Administrativo', 'activo': True},
    )
    perfil.nombre = 'Benja Administrativo'
    perfil.activo = True
    perfil.save(update_fields=['nombre', 'activo'])


def revertir_benja_administrativo(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    User.objects.filter(username=USERNAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('clinica', '0093_seed_supervisor_seguimiento'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(crear_benja_administrativo, revertir_benja_administrativo),
    ]
