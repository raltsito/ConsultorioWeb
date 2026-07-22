from django.db import migrations


GROUP_NAME = 'Lider de operaciones clinicas'


def crear_grupo(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name=GROUP_NAME)


def eliminar_grupo(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name=GROUP_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('clinica', '0087_direccioncomercial'),
    ]

    operations = [
        migrations.RunPython(crear_grupo, eliminar_grupo),
    ]
