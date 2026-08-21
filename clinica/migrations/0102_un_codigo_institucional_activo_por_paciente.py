from django.db import migrations, models
from django.db.models import Count


def validar_un_codigo_activo(apps, schema_editor):
    CodigoInstitucionalPaciente = apps.get_model(
        'clinica',
        'CodigoInstitucionalPaciente',
    )
    duplicados = list(
        CodigoInstitucionalPaciente.objects
        .filter(activo=True)
        .values('paciente_id')
        .annotate(total=Count('id'))
        .filter(total__gt=1)
        .values_list('paciente_id', flat=True)
    )
    if duplicados:
        raise RuntimeError(
            'No se puede aplicar la restricción de código único. '
            'Hay pacientes con varios códigos activos: '
            f'{duplicados}. Revisa estos casos manualmente; no se descartó ningún dato.'
        )


class Migration(migrations.Migration):
    dependencies = [
        (
            'clinica',
            '0101_codigoinstitucionalpaciente_usuarios_auditoria',
        ),
    ]

    operations = [
        migrations.RunPython(
            validar_un_codigo_activo,
            migrations.RunPython.noop,
        ),
        migrations.RemoveConstraint(
            model_name='codigoinstitucionalpaciente',
            name='codigo_activo_unico_paciente',
        ),
        migrations.AddConstraint(
            model_name='codigoinstitucionalpaciente',
            constraint=models.UniqueConstraint(
                condition=models.Q(('activo', True)),
                fields=('paciente',),
                name='un_codigo_institucional_activo_por_paciente',
            ),
        ),
    ]
