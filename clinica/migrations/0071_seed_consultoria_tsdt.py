from django.conf import settings
from django.db import migrations


USERNAME = 'ConsultoriaTsDt'
PASSWORD_HASH = 'pbkdf2_sha256$1200000$wnVM5DtPwNdSbiqdlmOkiy$01qy/hSbk214y6hpI0kIYFkPT9vORS9VdvQ+qTBy+A8='
DIVISION_NAMES = ['DOROTHEA', 'Trabajo Social']


def crear_consultoria_tsdt(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Consultoria = apps.get_model('clinica', 'Consultoria')
    Division = apps.get_model('clinica', 'Division')

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

    consultoria, _ = Consultoria.objects.get_or_create(
        usuario=user,
        defaults={'nombre': USERNAME, 'activo': True},
    )
    consultoria.nombre = USERNAME
    consultoria.activo = True
    consultoria.save(update_fields=['nombre', 'activo'])

    divisiones = [
        Division.objects.get_or_create(nombre=nombre)[0]
        for nombre in DIVISION_NAMES
    ]
    consultoria.divisiones.set(divisiones)


def revertir_consultoria_tsdt(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    User.objects.filter(username=USERNAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('clinica', '0070_consultoria_divisiones'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(crear_consultoria_tsdt, revertir_consultoria_tsdt),
    ]
