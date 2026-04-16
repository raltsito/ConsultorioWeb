from django.db import migrations
from decimal import Decimal


# Mapeo nombre (lowercase) -> precio
# Cubre los nombres reales encontrados en la BD
PRECIOS = [
    ("terapia individual",                   Decimal("600.00")),
    ("psicoterapia individual",               Decimal("600.00")),
    ("terapia de parejas",                    Decimal("700.00")),
    ("psicoterapia de pareja",                Decimal("700.00")),
    ("terapia familiar",                      Decimal("750.00")),
    ("psicoterapia familiar",                 Decimal("750.00")),
    ("terapia infantil",                      Decimal("650.00")),
    ("psicoterapia infantil",                 Decimal("650.00")),
    ("hipnosis",                              Decimal("800.00")),
    ("evaluacion psicologica infantil",       Decimal("650.00")),
    ("evaluación psicológica infantil",       Decimal("650.00")),
    ("evaluacion psicologica",                Decimal("600.00")),
    ("evaluación psicológica",                Decimal("600.00")),
    ("evaluacion neuropsicologica",           Decimal("650.00")),
    ("evaluación neuropsicológica",           Decimal("650.00")),
    ("consulta medica general",               Decimal("700.00")),
    ("consulta médica general",               Decimal("700.00")),
    ("consulta medica",                       Decimal("700.00")),
    ("consulta médica",                       Decimal("700.00")),
    ("consulta en salud mental",              Decimal("1000.00")),
    ("consulta medica en salud mental",       Decimal("1000.00")),
    ("consulta médica en salud mental",       Decimal("1000.00")),
    ("consulta nutricional",                  Decimal("850.00")),
    ("psicotanatologia",                      Decimal("600.00")),
    ("psicotanatología",                      Decimal("600.00")),
    ("certificado de mascotas",               Decimal("2200.00")),
]


def corregir_precios(apps, schema_editor):
    Servicio = apps.get_model('clinica', 'Servicio')
    for servicio in Servicio.objects.filter(precio__isnull=True):
        nombre_lower = servicio.nombre.lower().strip()
        for fragmento, precio in PRECIOS:
            if fragmento in nombre_lower:
                servicio.precio = precio
                servicio.save(update_fields=['precio'])
                break


def revertir(apps, schema_editor):
    pass  # No revertimos precios parciales


class Migration(migrations.Migration):

    dependencies = [
        ('clinica', '0042_poblar_precios_servicios'),
    ]

    operations = [
        migrations.RunPython(corregir_precios, revertir),
    ]
