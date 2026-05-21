from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('clinica', '0064_cita_sin_bono'),
    ]

    operations = [
        migrations.AddField(
            model_name='lineanomina',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('sesion', 'Sesión'),
                    ('bono_umbral', 'Bono por volumen'),
                    ('bono_por_paciente', 'Bono por paciente'),
                    ('penalizacion', 'Penalización inasistencia'),
                    ('expositor', 'Horas Expositor'),
                ],
                default='sesion',
                max_length=30,
            ),
            preserve_default=False,
        ) if False else migrations.AlterField(
            model_name='lineanomina',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('sesion', 'Sesión'),
                    ('bono_umbral', 'Bono por volumen'),
                    ('bono_por_paciente', 'Bono por paciente'),
                    ('penalizacion', 'Penalización inasistencia'),
                    ('expositor', 'Horas Expositor'),
                ],
                default='sesion',
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name='notificacionterapeuta',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('cita_aceptada', 'Cita aceptada'),
                    ('cita_rechazada', 'Cita rechazada'),
                    ('cita_modificada', 'Cita modificada'),
                    ('reagendo_aprobado', 'Reagendo aprobado'),
                    ('reagendo_rechazado', 'Reagendo rechazado'),
                    ('respuesta_incidente', 'Respuesta a reporte'),
                    ('expositor_aceptado', 'Horas expositor aceptadas'),
                    ('expositor_rechazado', 'Horas expositor rechazadas'),
                ],
                max_length=30,
            ),
        ),
        migrations.CreateModel(
            name='SolicitudHorasExpositor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('horas', models.PositiveIntegerField(verbose_name='Número de horas')),
                ('lugar', models.CharField(max_length=200, verbose_name='Lugar / Evento')),
                ('notas', models.TextField(verbose_name='Descripción de la actividad')),
                ('estado', models.CharField(
                    choices=[('pendiente', 'Pendiente'), ('aceptada', 'Aceptada'), ('rechazada', 'Rechazada')],
                    default='pendiente', max_length=20,
                )),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('terapeuta', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='solicitudes_expositor',
                    to='clinica.terapeuta',
                )),
            ],
            options={
                'verbose_name': 'Solicitud de Horas Expositor',
                'verbose_name_plural': 'Solicitudes de Horas Expositor',
                'ordering': ['-creado_en'],
            },
        ),
    ]
