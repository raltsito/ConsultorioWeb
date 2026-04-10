from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('clinica', '0037_solicitud_reagendo'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PacienteTerapeutaAcceso',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('creado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='vinculos_terapeuta_paciente_creados', to=settings.AUTH_USER_MODEL)),
                ('paciente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='terapeutas_vinculados', to='clinica.paciente')),
                ('terapeuta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pacientes_vinculados', to='clinica.terapeuta')),
            ],
            options={
                'verbose_name': 'Vinculo Terapeuta Paciente',
                'verbose_name_plural': 'Vinculos Terapeuta Paciente',
                'ordering': ['-creado_en'],
                'unique_together': {('terapeuta', 'paciente')},
            },
        ),
    ]
