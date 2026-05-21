from django.db import migrations, models

NUEVOS_CONSULTORIOS = [
    ('Republica 1 - Médico',                'republica'),
    ('Republica 2 - t. Individual',         'republica'),
    ('Republica 3 - Infantil',              'republica'),
    ('Republica 4 - T Pareja, familiar, grupal', 'republica'),
    ('Republica 5 - Of. Lucía',             'republica'),
    ('Republica 6 - Of. Javier Mtz',        'republica'),
    ('Consultorio Externo',                 'externo'),
    ('Morelos Consultorio 1',               'morelos'),
    ('Morelos Consultorio 2',               'morelos'),
    ('Morelos Consultorio 3',               'morelos'),
    ('Trabajo Social',                      'trabajo_social'),
    ('Trabajo Social Poniente',             'trabajo_social'),
    ('Zoom / Online',                       'zoom'),
    ('Colinas Consultorio 1',               'colinas'),
]


def activar_consultorios(apps, schema_editor):
    Consultorio = apps.get_model('clinica', 'Consultorio')
    for nombre, sede in NUEVOS_CONSULTORIOS:
        obj, _ = Consultorio.objects.get_or_create(nombre=nombre)
        obj.sede = sede
        obj.activo = True
        obj.save()


def desactivar_consultorios(apps, schema_editor):
    Consultorio = apps.get_model('clinica', 'Consultorio')
    nombres = [n for n, _ in NUEVOS_CONSULTORIOS]
    Consultorio.objects.filter(nombre__in=nombres).update(activo=False)


class Migration(migrations.Migration):

    dependencies = [
        ('clinica', '0062_seed_catalogo'),
    ]

    operations = [
        migrations.AddField(
            model_name='consultorio',
            name='activo',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(activar_consultorios, desactivar_consultorios),
    ]
