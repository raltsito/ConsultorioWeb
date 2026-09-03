import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('clinica', '0104_servicio_catalogo_estructura'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TarifaServicio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('precio_final', models.DecimalField(decimal_places=2, max_digits=12)),
                ('gratuita', models.BooleanField(default=False)),
                ('vigente_desde', models.DateField()),
                ('vigente_hasta', models.DateField(blank=True, null=True)),
                ('estado', models.CharField(choices=[('publicada', 'Publicada'), ('cancelada', 'Cancelada')], max_length=20)),
                ('origen', models.CharField(choices=[('migracion', 'Migración'), ('direccion', 'Dirección'), ('propuesta', 'Propuesta')], max_length=20)),
                ('motivo_publicacion', models.TextField(blank=True)),
                ('tratamiento_iva_snapshot', models.CharField(choices=[('iva_incluido_16', 'IVA incluido 16%'), ('exento', 'Exento')], max_length=20)),
                ('tasa_iva_snapshot', models.DecimalField(decimal_places=2, max_digits=5)),
                ('creada_en', models.DateTimeField(auto_now_add=True)),
                ('publicada_en', models.DateTimeField()),
                ('cancelada_en', models.DateTimeField(blank=True, null=True)),
                ('motivo_cancelacion', models.TextField(blank=True)),
                ('cancelada_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='tarifas_servicio_canceladas', to=settings.AUTH_USER_MODEL)),
                ('creada_por', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='tarifas_servicio_creadas', to=settings.AUTH_USER_MODEL)),
                ('publicada_por', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='tarifas_servicio_publicadas', to=settings.AUTH_USER_MODEL)),
                ('servicio', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='tarifas', to='clinica.servicio')),
            ],
            options={
                'verbose_name': 'Tarifa de servicio',
                'verbose_name_plural': 'Tarifas de servicio',
                'ordering': ('servicio_id', 'vigente_desde', 'id'),
                'indexes': [models.Index(fields=['servicio', 'estado', 'vigente_desde'], name='tarifa_serv_est_inicio_idx')],
                'constraints': [
                    models.CheckConstraint(condition=models.Q(models.Q(('gratuita', True), ('precio_final', Decimal('0.00'))), models.Q(('gratuita', False), ('precio_final__gt', Decimal('0.00'))), _connector='OR'), name='tarifa_gratuidad_precio_consistente'),
                    models.CheckConstraint(condition=models.Q(('vigente_hasta__isnull', True), ('vigente_hasta__gte', models.F('vigente_desde')), _connector='OR'), name='tarifa_rango_vigencia_valido'),
                    models.CheckConstraint(condition=models.Q(models.Q(('cancelada_en__isnull', True), ('cancelada_por__isnull', True), ('estado', 'publicada'), ('motivo_cancelacion', '')), models.Q(('cancelada_en__isnull', False), ('cancelada_por__isnull', False), ('estado', 'cancelada')), _connector='OR'), name='tarifa_cancelacion_consistente'),
                ],
            },
        ),
    ]
