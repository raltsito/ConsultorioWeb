from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ObjectDoesNotExist


PORCENTAJE_DESCUENTO_CAPTACION = Decimal("25.00")
CIEN = Decimal("100.00")
CENTAVO = Decimal("0.01")


@dataclass(frozen=True)
class CalculoImporteServicio:
    aplica_descuento: bool
    precio_general: Decimal | None
    porcentaje_descuento: Decimal | None
    importe_final: Decimal | None
    requiere_importe_manual: bool


def paciente_tiene_descuento_captacion(paciente):
    """Consulta la fuente de verdad sin duplicar el beneficio en Paciente."""
    if paciente is None or paciente.pk is None:
        return False

    from ventas.models import Captacion

    try:
        captacion = paciente.captacion_ventas
    except ObjectDoesNotExist:
        return False
    return captacion.estado == Captacion.ESTADO_APROBADA


def calcular_importe_servicio_con_captacion(*, paciente, servicio):
    """Calcula siempre desde el precio público vigente, nunca desde Cita.costo."""
    precio_general = None if servicio is None else servicio.precio
    aplica_descuento = paciente_tiene_descuento_captacion(paciente)
    if precio_general is None:
        return CalculoImporteServicio(
            aplica_descuento=aplica_descuento,
            precio_general=None,
            porcentaje_descuento=None,
            importe_final=None,
            requiere_importe_manual=True,
        )

    precio_general = Decimal(precio_general).quantize(CENTAVO, ROUND_HALF_UP)
    porcentaje = (
        PORCENTAJE_DESCUENTO_CAPTACION
        if aplica_descuento
        else Decimal("0.00")
    )
    factor_pago = (CIEN - porcentaje) / CIEN
    importe_final = (precio_general * factor_pago).quantize(
        CENTAVO,
        ROUND_HALF_UP,
    )
    return CalculoImporteServicio(
        aplica_descuento=aplica_descuento,
        precio_general=precio_general,
        porcentaje_descuento=porcentaje,
        importe_final=importe_final,
        requiere_importe_manual=False,
    )


def aplicar_costo_captacion_a_cita(cita):
    """Establece el costo esperado sin tocar cuentas ni descuentos legacy."""
    if (
        cita.estatus == cita.ESTATUS_NO_ASISTIO
        or cita.tiene_descuento
        or cita.importe_servicio_snapshot is not None
    ):
        return cita
    calculo = calcular_importe_servicio_con_captacion(
        paciente=cita.paciente,
        servicio=cita.servicio,
    )
    if calculo.aplica_descuento and calculo.importe_final is not None:
        cita.costo = calculo.importe_final
    return cita
