from django.db import migrations


def crear_terapeuta_prueba(apps, schema_editor):
    Terapeuta = apps.get_model("clinica", "Terapeuta")
    Terapeuta.objects.get_or_create(
        nombre="terapeuta prueba",
        defaults={"activo": True},
    )


def eliminar_terapeuta_prueba(apps, schema_editor):
    Terapeuta = apps.get_model("clinica", "Terapeuta")
    Terapeuta.objects.filter(nombre="terapeuta prueba").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("clinica", "0012_reparar_columna_paciente_en_cita"),
    ]

    operations = [
        migrations.RunPython(crear_terapeuta_prueba, eliminar_terapeuta_prueba),
    ]
