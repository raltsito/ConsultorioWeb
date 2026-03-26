from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('clinica', '0029_reportesesion'),
    ]

    operations = [
        migrations.CreateModel(
            name='AperturaExpediente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('expediente_no', models.CharField(blank=True, max_length=50, verbose_name='Expediente No.')),
                ('apellido_paterno', models.CharField(max_length=100, verbose_name='Apellido Paterno')),
                ('apellido_materno', models.CharField(blank=True, max_length=100, verbose_name='Apellido Materno')),
                ('ocupacion', models.CharField(blank=True, max_length=150, verbose_name='Ocupación')),
                ('lugar_de_trabajo', models.CharField(blank=True, max_length=200, verbose_name='Lugar de Trabajo')),
                ('cargo', models.CharField(blank=True, max_length=150, verbose_name='Cargo que desempeña')),
                ('estado_civil', models.CharField(
                    blank=True, max_length=20,
                    choices=[
                        ('', '---------'),
                        ('soltero', 'Soltero(a)'),
                        ('casado', 'Casado(a)'),
                        ('divorciado', 'Divorciado(a)'),
                        ('viudo', 'Viudo(a)'),
                        ('union_libre', 'Unión libre'),
                        ('otro', 'Otro'),
                    ],
                    verbose_name='Estado Civil',
                )),
                ('calle', models.CharField(blank=True, max_length=200, verbose_name='Calle')),
                ('num_exterior', models.CharField(blank=True, max_length=20, verbose_name='Núm.')),
                ('colonia', models.CharField(blank=True, max_length=150, verbose_name='Col.')),
                ('vive_con', models.CharField(blank=True, max_length=200, verbose_name='Vive con')),
                ('tiene_hijos', models.BooleanField(default=False, verbose_name='Tiene hijos')),
                ('num_hijos', models.PositiveIntegerField(blank=True, null=True, verbose_name='No. de Hijos')),
                ('hijo_1', models.CharField(blank=True, max_length=200, verbose_name='Hijo 1')),
                ('hijo_2', models.CharField(blank=True, max_length=200, verbose_name='Hijo 2')),
                ('hijo_3', models.CharField(blank=True, max_length=200, verbose_name='Hijo 3')),
                ('hijo_4', models.CharField(blank=True, max_length=200, verbose_name='Hijo 4')),
                ('religion', models.CharField(blank=True, max_length=100, verbose_name='Religión')),
                ('motivo_consulta', models.TextField(blank=True, verbose_name='Motivo de consulta')),
                ('emergencia_contacto', models.CharField(blank=True, max_length=200, verbose_name='En caso de emergencia llamar a')),
                ('emergencia_telefono', models.CharField(blank=True, max_length=30, verbose_name='Teléfono de contacto de emergencia')),
                ('como_se_entero', models.CharField(blank=True, max_length=200, verbose_name='¿Cómo se enteró de nosotros?')),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('paciente', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='apertura_expediente_obj',
                    to='clinica.paciente',
                )),
                ('documento', models.OneToOneField(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='apertura_origen',
                    to='clinica.documentopaciente',
                )),
                ('division', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='clinica.division',
                    verbose_name='División',
                )),
            ],
            options={
                'verbose_name': 'Apertura de Expediente',
                'verbose_name_plural': 'Aperturas de Expediente',
            },
        ),
    ]
