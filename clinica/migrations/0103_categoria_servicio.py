from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('clinica', '0102_un_codigo_institucional_activo_por_paciente'),
    ]

    operations = [
        migrations.CreateModel(
            name='CategoriaServicio',
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
                ('codigo', models.CharField(max_length=30, unique=True)),
                ('nombre', models.CharField(max_length=100, unique=True)),
                ('activo', models.BooleanField(default=True)),
                ('orden', models.PositiveIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'Categoría de servicio',
                'verbose_name_plural': 'Categorías de servicio',
                'ordering': ('orden', 'nombre'),
            },
        ),
    ]
