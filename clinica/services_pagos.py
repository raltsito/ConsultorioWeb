"""Servicios de dominio para pagos de citas.

Los importes de pago siempre son argumentos explicitos: este modulo no los
infiere desde tarifas, beneficios ni ``Cita.costo``. Cuando un cobro queda
completamente cubierto, delega al dominio de Captacion la evaluacion de una
posible comision, sin modificar los importes del cobro ni del pago.
"""

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Cita, CobroCita, Pago


def _generar_comision_captacion(cita, usuario):
    from ventas.services import generar_comision_captacion_si_corresponde

    return generar_comision_captacion_si_corresponde(
        cita=cita,
        usuario=usuario,
    )


def _importe_no_negativo(valor, nombre_campo):
    if isinstance(valor, bool):
        raise ValidationError({nombre_campo: "Proporciona un importe decimal válido."})
    try:
        importe = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(
            {nombre_campo: "Proporciona un importe decimal válido."}
        )
    if not importe.is_finite() or importe < Decimal("0.00"):
        raise ValidationError({nombre_campo: "El importe no puede ser negativo."})
    return importe


def _validar_actor(actor, nombre_campo):
    if actor is None or getattr(actor, "pk", None) is None:
        raise ValidationError({nombre_campo: "El usuario es obligatorio."})


def _obtener_cita_bloqueada(cita):
    if cita is None or getattr(cita, "pk", None) is None:
        raise ValidationError({"cita": "La cita debe existir antes de registrar el pago."})
    try:
        return Cita.objects.select_for_update().get(pk=cita.pk)
    except Cita.DoesNotExist:
        raise ValidationError({"cita": "La cita indicada no existe."})


def _obtener_pago_bloqueado(pago):
    if pago is None or getattr(pago, "pk", None) is None:
        raise ValidationError({"pago": "El pago debe existir."})
    try:
        return Pago.objects.select_for_update().get(pk=pago.pk)
    except Pago.DoesNotExist:
        raise ValidationError({"pago": "El pago indicado no existe."})


def _validar_metodo(metodo_pago):
    metodos_validos = {valor for valor, _ in Cita.PAGO_CHOICES}
    if metodo_pago not in metodos_validos:
        raise ValidationError({"metodo_pago": "Selecciona un método de pago válido."})
    if metodo_pago == "Pase":
        raise ValidationError(
            {"metodo_pago": "Pase no representa una entrada de dinero."}
        )


def _validar_origen(origen_registro):
    origenes_validos = {valor for valor, _ in Pago.ORIGEN_CHOICES}
    if origen_registro not in origenes_validos:
        raise ValidationError({"origen_registro": "Selecciona un origen válido."})


@transaction.atomic
def registrar_pago(
    *,
    cita,
    importe_esperado,
    importe_reportado,
    metodo_pago,
    origen_registro,
    registrado_por,
):
    """Registra una entrada individual de dinero para el cobro de una cita.

    El origen determina el estado inicial de forma explícita y acotada:

    * terapeuta: pendiente de verificación;
    * Recepción: confirmado por el mismo usuario que lo registra.

    El checkout del terapeuta sólo puede originar una entrada activa. Los pagos
    posteriores de Recepción permanecen como entradas independientes.
    """

    cita_bloqueada = _obtener_cita_bloqueada(cita)
    reportado = _importe_no_negativo(importe_reportado, "importe_reportado")
    _validar_metodo(metodo_pago)
    _validar_origen(origen_registro)
    _validar_actor(registrado_por, "registrado_por")

    cobro = (
        CobroCita.objects.select_for_update()
        .filter(cita=cita_bloqueada)
        .first()
    )
    if cobro is None:
        esperado = _importe_no_negativo(importe_esperado, "importe_esperado")
        cobro = CobroCita(
            cita=cita_bloqueada,
            importe_esperado=esperado,
        )
        cobro.full_clean()
        cobro.save()

    estado_inicial = (
        Pago.ESTADO_PENDIENTE_VERIFICACION
        if origen_registro == Pago.ORIGEN_TERAPEUTA
        else Pago.ESTADO_CONFIRMADO
    )
    existente_checkout = None
    if origen_registro == Pago.ORIGEN_TERAPEUTA:
        existente_checkout = (
            Pago.objects.filter(
                cobro=cobro,
                origen_registro=Pago.ORIGEN_TERAPEUTA,
            )
            .exclude(estado=Pago.ESTADO_ANULADO)
            .first()
        )
    if existente_checkout is not None:
        es_misma_operacion = all((
            existente_checkout.importe_reportado == reportado,
            existente_checkout.metodo_pago == metodo_pago,
            existente_checkout.registrado_por_id == registrado_por.pk,
        ))
        if es_misma_operacion:
            return existente_checkout, False
        raise ValidationError(
            {"cita": "El checkout del terapeuta ya registró un pago activo."}
        )

    ahora = timezone.now()
    pago = Pago(
        cobro=cobro,
        importe_reportado=reportado,
        metodo_pago=metodo_pago,
        origen_registro=origen_registro,
        estado=estado_inicial,
        registrado_por=registrado_por,
        registrado_en=ahora,
    )
    if estado_inicial == Pago.ESTADO_CONFIRMADO:
        pago.importe_verificado = reportado
        pago.verificado_por = registrado_por
        pago.verificado_en = ahora

    pago.full_clean()
    pago.save()
    if estado_inicial == Pago.ESTADO_CONFIRMADO:
        _generar_comision_captacion(cita_bloqueada, registrado_por)
    return pago, True


@transaction.atomic
def confirmar_pago(*, pago, importe_verificado, verificado_por):
    """Confirma un pago pendiente sin reemplazar el importe reportado."""

    pago_bloqueado = _obtener_pago_bloqueado(pago)
    verificado = _importe_no_negativo(importe_verificado, "importe_verificado")
    _validar_actor(verificado_por, "verificado_por")

    if pago_bloqueado.estado == Pago.ESTADO_ANULADO:
        raise ValidationError({"pago": "Un pago anulado no puede confirmarse."})
    if pago_bloqueado.estado == Pago.ESTADO_CON_DIFERENCIA:
        raise ValidationError(
            {"pago": "El pago ya tiene una diferencia registrada."}
        )
    if pago_bloqueado.estado == Pago.ESTADO_CONFIRMADO:
        if pago_bloqueado.importe_verificado == verificado:
            return pago_bloqueado, False
        raise ValidationError(
            {"importe_verificado": "El pago ya fue confirmado con otro importe."}
        )
    if verificado != pago_bloqueado.importe_reportado:
        raise ValidationError(
            {
                "importe_verificado": (
                    "El importe difiere del reportado; registra la diferencia."
                )
            }
        )

    pago_bloqueado.importe_verificado = verificado
    pago_bloqueado.verificado_por = verificado_por
    pago_bloqueado.verificado_en = timezone.now()
    pago_bloqueado.estado = Pago.ESTADO_CONFIRMADO
    pago_bloqueado.full_clean()
    pago_bloqueado.save(
        update_fields=(
            "importe_verificado",
            "verificado_por",
            "verificado_en",
            "estado",
        )
    )
    _generar_comision_captacion(
        pago_bloqueado.cobro.cita,
        verificado_por,
    )
    return pago_bloqueado, True


@transaction.atomic
def registrar_diferencia_pago(
    *,
    pago,
    importe_verificado,
    observacion,
    verificado_por,
):
    """Conserva el importe reportado y registra la discrepancia verificada."""

    pago_bloqueado = _obtener_pago_bloqueado(pago)
    verificado = _importe_no_negativo(importe_verificado, "importe_verificado")
    _validar_actor(verificado_por, "verificado_por")
    observacion_limpia = (observacion or "").strip()
    if not observacion_limpia:
        raise ValidationError(
            {"observacion_diferencia": "Describe la diferencia encontrada."}
        )
    if verificado == pago_bloqueado.importe_reportado:
        raise ValidationError(
            {"importe_verificado": "No existe diferencia con el importe reportado."}
        )

    if pago_bloqueado.estado == Pago.ESTADO_ANULADO:
        raise ValidationError({"pago": "Un pago anulado no puede verificarse."})
    if pago_bloqueado.estado == Pago.ESTADO_CONFIRMADO:
        raise ValidationError({"pago": "El pago ya fue confirmado."})
    if pago_bloqueado.estado == Pago.ESTADO_CON_DIFERENCIA:
        es_misma_operacion = all((
            pago_bloqueado.importe_verificado == verificado,
            pago_bloqueado.observacion_diferencia == observacion_limpia,
        ))
        if es_misma_operacion:
            return pago_bloqueado, False
        raise ValidationError({"pago": "El pago ya tiene otra diferencia registrada."})

    pago_bloqueado.importe_verificado = verificado
    pago_bloqueado.verificado_por = verificado_por
    pago_bloqueado.verificado_en = timezone.now()
    pago_bloqueado.observacion_diferencia = observacion_limpia
    pago_bloqueado.estado = Pago.ESTADO_CON_DIFERENCIA
    pago_bloqueado.full_clean()
    pago_bloqueado.save(
        update_fields=(
            "importe_verificado",
            "verificado_por",
            "verificado_en",
            "observacion_diferencia",
            "estado",
        )
    )
    _generar_comision_captacion(
        pago_bloqueado.cobro.cita,
        verificado_por,
    )
    return pago_bloqueado, True


@transaction.atomic
def anular_pago(*, pago, anulado_por, motivo):
    """Invalida un pago sin borrarlo y conserva toda su historia previa."""

    pago_bloqueado = _obtener_pago_bloqueado(pago)
    _validar_actor(anulado_por, "anulado_por")
    motivo_limpio = (motivo or "").strip()
    if not motivo_limpio:
        raise ValidationError({"motivo_anulacion": "El motivo es obligatorio."})

    if pago_bloqueado.estado == Pago.ESTADO_ANULADO:
        return pago_bloqueado, False

    pago_bloqueado.estado = Pago.ESTADO_ANULADO
    pago_bloqueado.anulado_por = anulado_por
    pago_bloqueado.anulado_en = timezone.now()
    pago_bloqueado.motivo_anulacion = motivo_limpio
    pago_bloqueado.full_clean()
    pago_bloqueado.save(
        update_fields=(
            "estado",
            "anulado_por",
            "anulado_en",
            "motivo_anulacion",
        )
    )
    return pago_bloqueado, True
