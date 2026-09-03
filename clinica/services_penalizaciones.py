from decimal import Decimal, ROUND_HALF_UP

from .services_tarifas import obtener_tarifa_vigente


PORCENTAJE_PENALIZACION_INASISTENCIA = Decimal('0.50')
CENTAVOS = Decimal('0.01')


def calcular_monto_penalizacion(base):
    """Calcula el 50% de una base monetaria usando únicamente Decimal."""
    if base is None:
        return None
    return (
        Decimal(base) * PORCENTAJE_PENALIZACION_INASISTENCIA
    ).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def obtener_base_penalizacion_cita(cita):
    """Resuelve la base histórica aplicable a una inasistencia.

    La tarifa oficial correspondiente a ``Cita.fecha`` es prioritaria. Durante
    la transición, las citas sin historia oficial conservan el comportamiento
    anterior mediante ``Servicio.precio``. No se usa ni modifica ``Cita.costo``.
    """
    if cita.servicio_id is None or cita.fecha is None:
        return None

    tarifa = obtener_tarifa_vigente(cita.servicio, cita.fecha)
    if tarifa is not None:
        return tarifa.total

    return cita.servicio.precio


def calcular_penalizacion_inasistencia(cita):
    return calcular_monto_penalizacion(obtener_base_penalizacion_cita(cita))
