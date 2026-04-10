from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clinica', '0038_pacienteterapeutaacceso'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccesoDirectoPortal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('clave', models.CharField(choices=[('manual_portal_medico', 'Manual del sistema para portal medico')], max_length=50, unique=True)),
                ('titulo', models.CharField(default='Manual del sistema', max_length=120)),
                ('nombre_archivo', models.CharField(blank=True, max_length=255)),
                ('tipo_mime', models.CharField(blank=True, max_length=100)),
                ('contenido', models.BinaryField(blank=True)),
                ('activo', models.BooleanField(default=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Acceso directo',
                'verbose_name_plural': 'Accesos directos',
            },
        ),
    ]
