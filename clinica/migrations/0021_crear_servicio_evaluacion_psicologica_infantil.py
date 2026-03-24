from django.db import migrations


def crear_servicio(apps, schema_editor):
    Servicio = apps.get_model("clinica", "Servicio")
    Servicio.objects.get_or_create(nombre="Evaluación psicológica infantil")


def eliminar_servicio(apps, schema_editor):
    Servicio = apps.get_model("clinica", "Servicio")
    Servicio.objects.filter(nombre="Evaluación psicológica infantil").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("clinica", "0020_tabuladorgeneral_cortesemanal_bonoextra_lineanomina_and_more"),
    ]

    operations = [
        migrations.RunPython(crear_servicio, eliminar_servicio),
    ]
