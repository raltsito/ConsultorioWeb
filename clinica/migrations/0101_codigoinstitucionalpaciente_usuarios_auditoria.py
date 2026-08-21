import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('clinica', '0100_cita_descuento_captacion_porcentaje_snapshot_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='codigoinstitucionalpaciente',
            name='asignado_por_usuario',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='codigos_institucionales_asignados',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='codigoinstitucionalpaciente',
            name='retirado_por_usuario',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='codigos_institucionales_retirados',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
