import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('clinica', '0097_mensajewhatsappentrante_media_id_and_more'),
    ]
    operations = [
        migrations.CreateModel(
            name='CodigoInstitucionalPaciente',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'codigo',
                    models.CharField(
                        choices=[
                            ('C100-B', 'Código 100 – Bajo'),
                            ('C100-M', 'Código 100 – Medio'),
                            ('C100-A', 'Código 100 – Alto'),
                            ('MOR', 'Código Morado'),
                            ('VIO', 'Código Violeta'),
                            ('VIH', 'Código VIH'),
                            ('GRI', 'Código Gris'),
                            ('AZI', 'Código Azul INTRA'),
                            ('ROS', 'Código Rosa'),
                        ],
                        max_length=10,
                    ),
                ),
                ('activo', models.BooleanField(default=True)),
                ('fecha_asignacion', models.DateTimeField(auto_now_add=True)),
                ('fecha_retiro', models.DateTimeField(blank=True, null=True)),
                ('observacion', models.CharField(blank=True, max_length=255)),
                (
                    'asignado_por',
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='codigos_asignados',
                        to='clinica.terapeuta',
                    ),
                ),
                (
                    'paciente',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='codigos_institucionales',
                        to='clinica.paciente',
                    ),
                ),
                (
                    'retirado_por',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='codigos_retirados',
                        to='clinica.terapeuta',
                    ),
                ),
            ],
            options={'ordering': ['codigo', '-fecha_asignacion']},
        ),
        migrations.AddConstraint(
            model_name='codigoinstitucionalpaciente',
            constraint=models.UniqueConstraint(
                condition=models.Q(('activo', True)),
                fields=('paciente', 'codigo'),
                name='codigo_activo_unico_paciente',
            ),
        ),
    ]
