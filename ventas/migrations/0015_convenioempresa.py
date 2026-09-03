import decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ("ventas", "0014_porcentaje_comision_0_10"),
    ("clinica", "0034_empresa_paciente_empresa"),
    migrations.swappable_dependency(settings.AUTH_USER_MODEL),
]

    operations = [
        migrations.CreateModel(
            name="ConvenioEmpresa",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("activo", models.BooleanField(default=True)),
                ("vigencia_desde", models.DateField(blank=True, null=True)),
                ("vigencia_hasta", models.DateField(blank=True, null=True)),
                (
                    "modalidad",
                    models.CharField(
                        choices=[
                            ("TARIFA_ESPECIAL", "Tarifa especial"),
                            ("DESCUENTO_PORCENTAJE", "Descuento porcentual"),
                            ("PAQUETE_MENSUAL", "Paquete mensual"),
                            ("PASE", "Pase / autorización"),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    "quien_paga",
                    models.CharField(
                        choices=[
                            ("PACIENTE", "Paciente"),
                            ("EMPRESA", "Empresa"),
                            ("ASOCIACION", "Asociación"),
                            ("COMPARTIDO", "Compartido"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "limite_consultas_mensual",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                (
                    "monto_mensual",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=12,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(
                                decimal.Decimal("0.00")
                            )
                        ],
                    ),
                ),
                (
                    "pase_requiere_identificador",
                    models.BooleanField(
                        default=False,
                        verbose_name="¿Los pases utilizan folio o identificador?",
                    ),
                ),
                (
                    "consultas_por_pase",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                ("observaciones", models.TextField(blank=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                (
                    "actualizado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="convenios_empresa_actualizados",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "creado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="convenios_empresa_creados",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "empresa",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="convenios_ventas",
                        to="clinica.empresa",
                    ),
                ),
            ],
            options={
                "verbose_name": "Convenio empresarial",
                "verbose_name_plural": "Convenios empresariales",
                "ordering": ["-activo", "-vigencia_desde", "-id"],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("activo", True)),
                        fields=("empresa",),
                        name="ventas_un_convenio_activo_por_empresa",
                    )
                ],
            },
        ),
    ]
