from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('clinica', '0065_horas_expositor'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RegistroActividad',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('accion', models.CharField(
                    choices=[
                        ('cita_creada', 'Cita agendada'),
                        ('cita_editada', 'Cita editada'),
                        ('cita_eliminada', 'Cita eliminada'),
                        ('cita_checkout', 'Sesión cerrada'),
                        ('disponib_agregada', 'Disponibilidad agregada'),
                        ('disponib_eliminada', 'Disponibilidad eliminada'),
                        ('bloqueo_creado', 'Bloqueo de agenda creado'),
                        ('bloqueo_eliminado', 'Bloqueo de agenda eliminado'),
                        ('solicitud_aceptada', 'Solicitud aceptada'),
                        ('solicitud_rechazada', 'Solicitud rechazada'),
                        ('reagendo_solicitado', 'Reagendo solicitado'),
                        ('reagendo_aprobado', 'Reagendo aprobado'),
                        ('reagendo_rechazado', 'Reagendo rechazado'),
                        ('paciente_registrado', 'Paciente registrado'),
                        ('paciente_editado', 'Paciente editado'),
                        ('paciente_eliminado', 'Paciente eliminado'),
                        ('nomina_aprobada', 'Nómina aprobada'),
                        ('expositor_respondido', 'Horas expositor respondidas'),
                        ('incidente_reportado', 'Incidente reportado'),
                        ('incidente_respondido', 'Incidente respondido'),
                    ],
                    db_index=True,
                    max_length=40,
                )),
                ('categoria', models.CharField(
                    choices=[
                        ('cita', 'Cita'),
                        ('disponibilidad', 'Disponibilidad'),
                        ('reagendo', 'Reagendo'),
                        ('paciente', 'Paciente'),
                        ('nomina', 'Nómina'),
                        ('solicitud', 'Solicitud'),
                        ('incidente', 'Incidente'),
                    ],
                    db_index=True,
                    max_length=20,
                )),
                ('descripcion', models.TextField()),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('es_retroactivo', models.BooleanField(default=False)),
                ('paciente_afectado', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='registros_actividad',
                    to='clinica.paciente',
                )),
                ('terapeuta_afectado', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='registros_actividad',
                    to='clinica.terapeuta',
                )),
                ('usuario', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='registros_actividad',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Registro de Actividad',
                'verbose_name_plural': 'Registro de Actividades',
                'ordering': ['-timestamp'],
            },
        ),
    ]
