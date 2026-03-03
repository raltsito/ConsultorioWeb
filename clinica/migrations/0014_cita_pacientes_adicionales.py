from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("clinica", "0013_crear_terapeuta_prueba"),
    ]

    operations = [
        migrations.AddField(
            model_name="cita",
            name="pacientes_adicionales",
            field=models.ManyToManyField(
                blank=True,
                related_name="citas_como_adicional",
                to="clinica.paciente",
            ),
        ),
    ]
