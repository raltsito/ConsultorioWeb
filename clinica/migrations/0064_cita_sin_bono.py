from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clinica', '0063_consultorio_activo'),
    ]

    operations = [
        migrations.AddField(
            model_name='cita',
            name='sin_bono',
            field=models.BooleanField(
                default=False,
                help_text='Si True, la cita se paga al terapeuta pero no suma para el cálculo de bonos adicionales.',
            ),
        ),
    ]
