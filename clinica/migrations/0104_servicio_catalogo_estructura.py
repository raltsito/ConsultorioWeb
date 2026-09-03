import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('clinica', '0103_categoria_servicio'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicio',
            name='activo',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='servicio',
            name='categoria',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='servicios',
                to='clinica.categoriaservicio',
            ),
        ),
        migrations.AddField(
            model_name='servicio',
            name='codigo',
            field=models.CharField(
                blank=True,
                max_length=30,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name='servicio',
            name='duracion_minutos',
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                validators=[django.core.validators.MinValueValidator(1)],
            ),
        ),
        migrations.AddField(
            model_name='servicio',
            name='modalidad',
            field=models.CharField(
                blank=True,
                choices=[
                    ('individual', 'Individual'),
                    ('pareja', 'Pareja'),
                    ('familiar', 'Familiar'),
                    ('grupal', 'Grupal'),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='servicio',
            name='orden',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='servicio',
            name='reemplazado_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='variantes_historicas',
                to='clinica.servicio',
            ),
        ),
        migrations.AddField(
            model_name='servicio',
            name='tratamiento_iva',
            field=models.CharField(
                blank=True,
                choices=[
                    ('iva_incluido_16', 'IVA incluido 16%'),
                    ('exento', 'Exento'),
                ],
                max_length=20,
                null=True,
            ),
        ),
    ]
