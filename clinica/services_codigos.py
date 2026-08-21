from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    CODIGOS_INSTITUCIONALES,
    CodigoInstitucionalPaciente,
    Paciente,
)


def actualizar_codigos_institucionales(
    *,
    paciente,
    codigos,
    usuario,
    terapeuta=None,
):
    seleccionados = set(codigos)
    invalidos = seleccionados - set(CODIGOS_INSTITUCIONALES)
    if invalidos:
        raise ValidationError('Se enviaron códigos institucionales inválidos.')

    if len(seleccionados) > 1:
        raise ValidationError(
            'Cada paciente puede tener como máximo un código institucional activo.'
        )

    ahora = timezone.now()
    with transaction.atomic():
        Paciente.objects.select_for_update().get(pk=paciente.pk)
        activos = list(
            CodigoInstitucionalPaciente.objects
            .select_for_update()
            .filter(paciente=paciente, activo=True)
        )
        codigos_activos = {item.codigo for item in activos}

        for item in activos:
            if item.codigo not in seleccionados:
                item.activo = False
                item.fecha_retiro = ahora
                item.retirado_por = terapeuta
                item.retirado_por_usuario = usuario
                item.save(
                    update_fields=[
                        'activo',
                        'fecha_retiro',
                        'retirado_por',
                        'retirado_por_usuario',
                    ]
                )

        for codigo in seleccionados - codigos_activos:
            CodigoInstitucionalPaciente.objects.create(
                paciente=paciente,
                codigo=codigo,
                asignado_por=terapeuta,
                asignado_por_usuario=usuario,
            )
