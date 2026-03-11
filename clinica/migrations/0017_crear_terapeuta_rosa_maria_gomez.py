from django.db import migrations


def crear_terapeuta_rosa_maria_gomez(apps, schema_editor):
    Terapeuta = apps.get_model("clinica", "Terapeuta")
    Terapeuta.objects.get_or_create(
        nombre="Rosa María Gómez",
        defaults={"activo": True},
    )


def eliminar_terapeuta_rosa_maria_gomez(apps, schema_editor):
    Terapeuta = apps.get_model("clinica", "Terapeuta")
    Terapeuta.objects.filter(nombre="Rosa María Gómez").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("clinica", "0016_cita_tipo_paciente"),
    ]

    operations = [
        migrations.RunPython(
            crear_terapeuta_rosa_maria_gomez,
            eliminar_terapeuta_rosa_maria_gomez,
        ),
    ]
