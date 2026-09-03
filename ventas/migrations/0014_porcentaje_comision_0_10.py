import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventas", "0013_alter_codigocaptacion_options"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="codigocaptacion",
            name="ventas_codigo_captacion_porcentaje_1_10",
        ),
        migrations.AlterField(
            model_name="codigocaptacion",
            name="porcentaje_comision",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(10),
                ],
            ),
        ),
        migrations.AddConstraint(
            model_name="codigocaptacion",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(porcentaje_comision__isnull=True)
                    | models.Q(
                        porcentaje_comision__gte=0,
                        porcentaje_comision__lte=10,
                    )
                ),
                name="ventas_codigo_captacion_porcentaje_0_10",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="captacion",
            name="ventas_captacion_porcentaje_1_10",
        ),
        migrations.AlterField(
            model_name="captacion",
            name="porcentaje_comision",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(10),
                ],
            ),
        ),
        migrations.AddConstraint(
            model_name="captacion",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(porcentaje_comision__isnull=True)
                    | models.Q(
                        porcentaje_comision__gte=0,
                        porcentaje_comision__lte=10,
                    )
                ),
                name="ventas_captacion_porcentaje_0_10",
            ),
        ),
    ]
