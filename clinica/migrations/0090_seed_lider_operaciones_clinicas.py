from django.conf import settings
from django.db import migrations


USERNAME = 'lider_operaciones'
PASSWORD_HASH = 'pbkdf2_sha256$1200000$j0bgPIS89ClTeiOGFCfEA6$qdIyJ7nI8i1BkOF0SfyyVHM889Mtf8f0wL/DL8aE14o='


def crear_lider_operaciones(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    LiderOperacionesClinicas = apps.get_model('clinica', 'LiderOperacionesClinicas')

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

    perfil, _ = LiderOperacionesClinicas.objects.get_or_create(
        usuario=user,
        defaults={'nombre': 'Lider de Operaciones Clinicas', 'activo': True},
    )
    perfil.nombre = 'Lider de Operaciones Clinicas'
    perfil.activo = True
    perfil.save(update_fields=['nombre', 'activo'])


def revertir_lider_operaciones(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    User.objects.filter(username=USERNAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('clinica', '0089_lideroperacionesclinicas'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(crear_lider_operaciones, revertir_lider_operaciones),
    ]
