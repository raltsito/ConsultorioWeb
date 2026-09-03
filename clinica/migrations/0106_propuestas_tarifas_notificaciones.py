import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('clinica', '0105_tarifa_servicio'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PropuestaTarifas',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('vigencia_propuesta', models.DateField()),
                ('observaciones', models.TextField(blank=True)),
                ('estado', models.CharField(choices=[('borrador', 'Borrador'), ('pendiente', 'Pendiente'), ('aprobada', 'Aprobada'), ('rechazada', 'Rechazada')], default='borrador', max_length=20)),
                ('creada_en', models.DateTimeField(auto_now_add=True)),
                ('actualizada_en', models.DateTimeField(auto_now=True)),
                ('enviada_en', models.DateTimeField(blank=True, null=True)),
                ('aprobada_en', models.DateTimeField(blank=True, null=True)),
                ('rechazada_en', models.DateTimeField(blank=True, null=True)),
                ('motivo_rechazo', models.TextField(blank=True)),
                ('aprobada_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='propuestas_tarifas_aprobadas', to=settings.AUTH_USER_MODEL)),
                ('creada_por', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='propuestas_tarifas_creadas', to=settings.AUTH_USER_MODEL)),
                ('enviada_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='propuestas_tarifas_enviadas', to=settings.AUTH_USER_MODEL)),
                ('rechazada_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='propuestas_tarifas_rechazadas', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Propuesta de tarifas',
                'verbose_name_plural': 'Propuestas de tarifas',
                'ordering': ('-creada_en', '-id'),
                'permissions': [('view_service_catalog', 'Puede consultar el catálogo de servicios'), ('propose_service_tariff', 'Puede crear propuestas de tarifas'), ('submit_service_tariff_proposal', 'Puede enviar propuestas de tarifas'), ('review_service_tariff_proposal', 'Puede revisar propuestas de tarifas'), ('publish_service_tariff', 'Puede publicar tarifas de servicios'), ('cancel_future_service_tariff', 'Puede cancelar tarifas futuras')],
            },
        ),
        migrations.CreateModel(
            name='PropuestaTarifaDetalle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('precio_actual_snapshot', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('gratuita_actual_snapshot', models.BooleanField(blank=True, null=True)),
                ('precio_propuesto', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('gratuita_propuesta', models.BooleanField(default=False)),
                ('propuesta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detalles', to='clinica.propuestatarifas')),
                ('servicio', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='propuestas_tarifa', to='clinica.servicio')),
                ('tarifa_actual', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='detalles_snapshot', to='clinica.tarifaservicio')),
                ('tarifa_publicada', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='detalles_origen', to='clinica.tarifaservicio')),
            ],
            options={
                'verbose_name': 'Detalle de propuesta de tarifas',
                'verbose_name_plural': 'Detalles de propuesta de tarifas',
                'ordering': ('servicio__nombre', 'id'),
                'constraints': [models.UniqueConstraint(fields=('propuesta', 'servicio'), name='propuesta_tarifa_servicio_unico')],
            },
        ),
        migrations.CreateModel(
            name='NotificacionTarifa',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('propuesta_enviada', 'Propuesta enviada'), ('propuesta_aprobada', 'Propuesta aprobada'), ('propuesta_rechazada', 'Propuesta rechazada')], max_length=30)),
                ('creada_en', models.DateTimeField(auto_now_add=True)),
                ('leida_en', models.DateTimeField(blank=True, null=True)),
                ('destinatario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notificaciones_tarifas', to=settings.AUTH_USER_MODEL)),
                ('propuesta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notificaciones', to='clinica.propuestatarifas')),
            ],
            options={
                'verbose_name': 'Notificación de tarifas',
                'verbose_name_plural': 'Notificaciones de tarifas',
                'ordering': ('-creada_en', '-id'),
                'constraints': [models.UniqueConstraint(fields=('destinatario', 'tipo', 'propuesta'), name='notificacion_tarifa_unica')],
            },
        ),
    ]
