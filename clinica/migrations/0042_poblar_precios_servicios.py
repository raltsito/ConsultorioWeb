from django.db import migrations
from decimal import Decimal


PRECIOS = [
    ("psicoterapia individual",          Decimal("600.00")),
    ("psicoterapia de pareja",           Decimal("700.00")),
    ("psicoterapia familiar",            Decimal("750.00")),
    ("psicoterapia infantil",            Decimal("650.00")),
    ("hipnosis clinica",                 Decimal("800.00")),
    ("hipnosis clínica",                 Decimal("800.00")),
    ("evaluacion psicologica",           Decimal("600.00")),
    ("evaluación psicológica",           Decimal("600.00")),
    ("evaluacion neuropsicologica",      Decimal("650.00")),
    ("evaluación neuropsicológica",      Decimal("650.00")),
    ("consulta medica general",          Decimal("700.00")),
    ("consulta médica general",          Decimal("700.00")),
    ("consulta medica en salud mental",  Decimal("1000.00")),
    ("consulta médica en salud mental",  Decimal("1000.00")),
    ("consulta nutricional",             Decimal("850.00")),
    ("psicotanatologia",                 Decimal("600.00")),
    ("psicotanatología",                 Decimal("600.00")),
    ("certificado de mascotas",          Decimal("2200.00")),
    ("evaluacion psicologica infantil",  Decimal("650.00")),
    ("evaluación psicológica infantil",  Decimal("650.00")),
]


def poblar_precios(apps, schema_editor):
    Servicio = apps.get_model('clinica', 'Servicio')
    for servicio in Servicio.objects.all():
        nombre_lower = servicio.nombre.lower().strip()
        for fragmento, precio in PRECIOS:
            if fragmento in nombre_lower:
                servicio.precio = precio
                servicio.save(update_fields=['precio'])
                break


def revertir_precios(apps, schema_editor):
    Servicio = apps.get_model('clinica', 'Servicio')
    Servicio.objects.all().update(precio=None)


class Migration(migrations.Migration):

    dependencies = [
        ('clinica', '0041_servicio_precio_penalizacion_paciente'),
    ]

    operations = [
        migrations.RunPython(poblar_precios, revertir_precios),
    ]
