from django.db import migrations


def crear_servicio(apps, schema_editor):
    Servicio = apps.get_model("clinica", "Servicio")
    Servicio.objects.get_or_create(nombre="Evaluación psicológica")


def eliminar_servicio(apps, schema_editor):
    Servicio = apps.get_model("clinica", "Servicio")
    Servicio.objects.filter(nombre="Evaluación psicológica").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("clinica", "0030_aperturaexpediente"),
    ]

    operations = [
        migrations.RunPython(crear_servicio, eliminar_servicio),
    ]
