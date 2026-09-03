from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import CategoriaServicio, ReglaBeneficioReferido
from .services_tarifas import obtener_tarifa_vigente

if TYPE_CHECKING:
    from ventas.models import Captacion

    from .models import Paciente, Servicio, TarifaServicio


CENTAVO = Decimal('0.01')
CIEN = Decimal('100.00')


@dataclass(frozen=True)
class ResultadoBeneficioReferido:
    aplica: bool
    motivo: str
    captacion: Captacion | None
    servicio: Servicio | None
    categoria: CategoriaServicio | None
    tarifa: TarifaServicio | None
    regla: ReglaBeneficioReferido | None
    tarifa_oficial: Decimal | None
    porcentaje_beneficio: Decimal | None
    importe_descuento: Decimal | None
    total_despues_beneficio: Decimal | None


class IntegridadReglasBeneficioError(RuntimeError):
    """Indica que existen reglas activas incompatibles para una misma fecha."""


def _validar_categoria(categoria):
    if not isinstance(categoria, CategoriaServicio) or categoria.pk is None:
        raise ValidationError(
            {'categoria_servicio': 'Selecciona una categoría registrada.'}
        )


def _validar_actor(actor):
    if actor is None or actor.pk is None:
        raise ValidationError(
            {'creado_por': 'Se requiere un usuario registrado como responsable.'}
        )


def _validar_fecha(fecha):
    if not isinstance(fecha, date):
        raise ValidationError({'vigente_desde': 'Indica una fecha válida.'})


def obtener_regla_beneficio_vigente(*, categoria, fecha):
    """Devuelve la única regla activa de la categoría en la fecha, o None."""
    _validar_categoria(categoria)
    _validar_fecha(fecha)

    reglas = list(
        ReglaBeneficioReferido.objects.filter(
            categoria_servicio=categoria,
            activo=True,
            vigente_desde__lte=fecha,
        )
        .filter(Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gte=fecha))
        .order_by('-vigente_desde', '-pk')[:2]
    )
    if len(reglas) > 1:
        raise IntegridadReglasBeneficioError(
            'Existe más de una regla vigente para la categoría y fecha indicadas.'
        )
    return reglas[0] if reglas else None


def obtener_captacion_registrada(paciente):
    """Obtiene el origen persistente sin interpretar el estado de la comisión."""
    if paciente is None or paciente.pk is None:
        return None

    paciente_actual = (
        paciente.__class__.objects.select_related('captacion_ventas')
        .filter(pk=paciente.pk)
        .first()
    )
    if paciente_actual is None:
        return None
    try:
        return paciente_actual.captacion_ventas
    except ObjectDoesNotExist:
        return None


def paciente_tiene_captacion_registrada(paciente):
    """Una captación registrada acredita el origen, no la comisión posterior."""
    return obtener_captacion_registrada(paciente) is not None


def _resultado_sin_beneficio(
    *,
    motivo,
    captacion,
    servicio,
    categoria=None,
    tarifa=None,
    regla=None,
):
    return ResultadoBeneficioReferido(
        aplica=False,
        motivo=motivo,
        captacion=captacion,
        servicio=servicio,
        categoria=categoria,
        tarifa=tarifa,
        regla=regla,
        tarifa_oficial=None,
        porcentaje_beneficio=None,
        importe_descuento=None,
        total_despues_beneficio=None,
    )


def resolver_beneficio_referido(*, paciente, servicio, fecha):
    """Calcula el beneficio por categoría y fecha sin persistir el resultado."""
    _validar_fecha(fecha)

    captacion = obtener_captacion_registrada(paciente)
    if captacion is None:
        return _resultado_sin_beneficio(
            motivo='paciente_no_referido',
            captacion=None,
            servicio=servicio,
        )

    categoria = servicio.categoria if servicio is not None else None
    if categoria is None:
        return _resultado_sin_beneficio(
            motivo='categoria_no_determinada',
            captacion=captacion,
            servicio=servicio,
        )

    tarifa = obtener_tarifa_vigente(servicio, fecha)
    if tarifa is None:
        return _resultado_sin_beneficio(
            motivo='tarifa_oficial_no_disponible',
            captacion=captacion,
            servicio=servicio,
            categoria=categoria,
        )

    regla = obtener_regla_beneficio_vigente(
        categoria=categoria,
        fecha=fecha,
    )
    if regla is None:
        return _resultado_sin_beneficio(
            motivo='regla_no_disponible',
            captacion=captacion,
            servicio=servicio,
            categoria=categoria,
            tarifa=tarifa,
        )

    tarifa_oficial = Decimal(tarifa.total).quantize(
        CENTAVO,
        rounding=ROUND_HALF_UP,
    )
    porcentaje_beneficio = Decimal(regla.porcentaje_descuento).quantize(
        CENTAVO,
        rounding=ROUND_HALF_UP,
    )
    importe_descuento = (
        tarifa_oficial * porcentaje_beneficio / CIEN
    ).quantize(
        CENTAVO,
        rounding=ROUND_HALF_UP,
    )
    total_despues_beneficio = (
        tarifa_oficial - importe_descuento
    ).quantize(
        CENTAVO,
        rounding=ROUND_HALF_UP,
    )
    return ResultadoBeneficioReferido(
        aplica=True,
        motivo='beneficio_aplicable',
        captacion=captacion,
        servicio=servicio,
        categoria=categoria,
        tarifa=tarifa,
        regla=regla,
        tarifa_oficial=tarifa_oficial,
        porcentaje_beneficio=porcentaje_beneficio,
        importe_descuento=importe_descuento,
        total_despues_beneficio=total_despues_beneficio,
    )


def _guardar_regla(
    *,
    categoria,
    porcentaje_descuento,
    vigente_desde,
    vigente_hasta,
    activo,
    actor,
):
    momento = timezone.now()
    regla = ReglaBeneficioReferido(
        categoria_servicio=categoria,
        porcentaje_descuento=Decimal(str(porcentaje_descuento)),
        activo=activo,
        vigente_desde=vigente_desde,
        vigente_hasta=vigente_hasta,
        creado_por=actor,
        aprobado_por=actor,
        aprobado_en=momento,
    )
    regla.full_clean()
    regla.save()
    return regla


@transaction.atomic
def crear_regla_beneficio(
    *,
    categoria,
    porcentaje_descuento,
    vigente_desde,
    actor,
    vigente_hasta=None,
    activo=True,
):
    """Registra una regla sin consultar pacientes, citas, servicios o captaciones."""
    _validar_categoria(categoria)
    _validar_actor(actor)
    _validar_fecha(vigente_desde)

    categoria_bloqueada = CategoriaServicio.objects.select_for_update().get(
        pk=categoria.pk
    )
    list(
        ReglaBeneficioReferido.objects.select_for_update().filter(
            categoria_servicio=categoria_bloqueada
        )
    )
    return _guardar_regla(
        categoria=categoria_bloqueada,
        porcentaje_descuento=porcentaje_descuento,
        vigente_desde=vigente_desde,
        vigente_hasta=vigente_hasta,
        activo=activo,
        actor=actor,
    )


@transaction.atomic
def programar_regla_beneficio(
    *,
    categoria,
    porcentaje_descuento,
    vigente_desde,
    actor,
    vigente_hasta=None,
):
    """Programa una regla futura y conserva como histórico la regla anterior."""
    _validar_categoria(categoria)
    _validar_actor(actor)
    _validar_fecha(vigente_desde)
    if vigente_desde <= timezone.localdate():
        raise ValidationError(
            {'vigente_desde': 'Un cambio programado debe iniciar en una fecha futura.'}
        )

    categoria_bloqueada = CategoriaServicio.objects.select_for_update().get(
        pk=categoria.pk
    )
    reglas_activas = ReglaBeneficioReferido.objects.select_for_update().filter(
        categoria_servicio=categoria_bloqueada,
        activo=True,
    )
    reglas_anteriores_superpuestas = reglas_activas.filter(
        vigente_desde__lt=vigente_desde,
    ).filter(
        Q(vigente_hasta__isnull=True)
        | Q(vigente_hasta__gte=vigente_desde)
    )
    reglas_anteriores = list(reglas_anteriores_superpuestas)
    if len(reglas_anteriores) > 1:
        raise IntegridadReglasBeneficioError(
            'Existen varias reglas anteriores superpuestas para esta categoría.'
        )
    if reglas_anteriores:
        regla_anterior = reglas_anteriores[0]
        regla_anterior.vigente_hasta = vigente_desde - timedelta(days=1)
        regla_anterior.full_clean()
        regla_anterior.save(update_fields=['vigente_hasta'])

    return _guardar_regla(
        categoria=categoria_bloqueada,
        porcentaje_descuento=porcentaje_descuento,
        vigente_desde=vigente_desde,
        vigente_hasta=vigente_hasta,
        activo=True,
        actor=actor,
    )
