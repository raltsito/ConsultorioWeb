from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Servicio, TarifaServicio


class IntegridadTarifasError(Exception):
    """La historia tarifaria contiene más de una respuesta válida."""


def obtener_tarifa_vigente(servicio, fecha):
    coincidencias = list(
        TarifaServicio.objects.filter(
            servicio=servicio,
            estado=TarifaServicio.ESTADO_PUBLICADA,
            vigente_desde__lte=fecha,
        )
        .filter(Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gte=fecha))
        .order_by('vigente_desde', 'id')[:2]
    )
    if len(coincidencias) > 1:
        raise IntegridadTarifasError(
            f'El servicio {servicio.pk} tiene tarifas superpuestas para {fecha}.'
        )
    return coincidencias[0] if coincidencias else None


def obtener_proxima_tarifa(servicio, desde=None):
    fecha_referencia = desde or timezone.localdate()
    return (
        TarifaServicio.objects.filter(
            servicio=servicio,
            estado=TarifaServicio.ESTADO_PUBLICADA,
            vigente_desde__gt=fecha_referencia,
        )
        .order_by('vigente_desde', 'id')
        .first()
    )


def publicar_tarifa_servicio(
    *,
    servicio,
    precio_final,
    gratuita,
    vigente_desde,
    actor,
    origen,
    motivo='',
):
    precio = _normalizar_precio(precio_final)
    _validar_datos_publicacion(
        servicio=servicio,
        precio_final=precio,
        gratuita=gratuita,
        vigente_desde=vigente_desde,
        actor=actor,
        origen=origen,
    )

    with transaction.atomic():
        servicio_bloqueado = Servicio.objects.select_for_update().get(
            pk=servicio.pk
        )
        _validar_servicio_publicable(servicio_bloqueado)

        publicadas = list(
            TarifaServicio.objects.select_for_update()
            .filter(
                servicio=servicio_bloqueado,
                estado=TarifaServicio.ESTADO_PUBLICADA,
            )
            .order_by('vigente_desde', 'id')
        )
        _validar_cronologia_publicacion(publicadas, vigente_desde)

        anterior = publicadas[-1] if publicadas else None
        if anterior and (
            anterior.vigente_hasta is None
            or anterior.vigente_hasta >= vigente_desde
        ):
            anterior.vigente_hasta = vigente_desde - timedelta(days=1)
            anterior.full_clean()
            anterior.save(update_fields=['vigente_hasta'])

        tasa_iva = _tasa_para_tratamiento(
            servicio_bloqueado.tratamiento_iva
        )
        ahora = timezone.now()
        tarifa = TarifaServicio(
            servicio=servicio_bloqueado,
            precio_final=precio,
            gratuita=gratuita,
            vigente_desde=vigente_desde,
            vigente_hasta=None,
            estado=TarifaServicio.ESTADO_PUBLICADA,
            origen=origen,
            motivo_publicacion=motivo.strip(),
            tratamiento_iva_snapshot=servicio_bloqueado.tratamiento_iva,
            tasa_iva_snapshot=tasa_iva,
            creada_por=actor,
            publicada_por=actor,
            publicada_en=ahora,
        )
        tarifa.full_clean()
        tarifa.save()

        if obtener_tarifa_vigente(servicio_bloqueado, vigente_desde) != tarifa:
            raise IntegridadTarifasError(
                'La verificación final no encontró la tarifa recién publicada.'
            )
        return tarifa


def validar_publicacion_tarifa(
    *,
    servicio,
    precio_final,
    gratuita,
    vigente_desde,
    actor,
    origen,
):
    precio = _normalizar_precio(precio_final)
    _validar_datos_publicacion(
        servicio=servicio,
        precio_final=precio,
        gratuita=gratuita,
        vigente_desde=vigente_desde,
        actor=actor,
        origen=origen,
    )
    _validar_servicio_publicable(servicio)
    publicadas = list(
        TarifaServicio.objects.filter(
            servicio=servicio,
            estado=TarifaServicio.ESTADO_PUBLICADA,
        ).order_by('vigente_desde', 'id')
    )
    _validar_cronologia_publicacion(publicadas, vigente_desde)
    return precio


def cancelar_tarifa_futura(
    *,
    tarifa,
    actor,
    motivo,
    fecha_operativa=None,
):
    motivo_limpio = (motivo or '').strip()
    if not motivo_limpio:
        raise ValidationError('La cancelación requiere un motivo.')
    if actor is None or actor.pk is None:
        raise ValidationError('La cancelación requiere un actor persistido.')

    fecha_referencia = fecha_operativa or timezone.localdate()
    if not isinstance(fecha_referencia, date):
        raise ValidationError('La fecha operativa debe ser una fecha válida.')

    with transaction.atomic():
        Servicio.objects.select_for_update().get(pk=tarifa.servicio_id)
        tarifa_bloqueada = (
            TarifaServicio.objects.select_for_update()
            .select_related('servicio')
            .get(pk=tarifa.pk)
        )
        if tarifa_bloqueada.estado != TarifaServicio.ESTADO_PUBLICADA:
            raise ValidationError('Sólo puede cancelarse una tarifa publicada.')
        if tarifa_bloqueada.vigente_desde <= fecha_referencia:
            raise ValidationError(
                'Este método sólo permite cancelar tarifas futuras.'
            )

        tarifa_bloqueada.estado = TarifaServicio.ESTADO_CANCELADA
        tarifa_bloqueada.cancelada_por = actor
        tarifa_bloqueada.cancelada_en = timezone.now()
        tarifa_bloqueada.motivo_cancelacion = motivo_limpio
        tarifa_bloqueada.full_clean()
        tarifa_bloqueada.save(
            update_fields=[
                'estado',
                'cancelada_por',
                'cancelada_en',
                'motivo_cancelacion',
            ]
        )

        anterior = (
            TarifaServicio.objects.select_for_update()
            .filter(
                servicio_id=tarifa_bloqueada.servicio_id,
                estado=TarifaServicio.ESTADO_PUBLICADA,
                vigente_desde__lt=tarifa_bloqueada.vigente_desde,
            )
            .order_by('-vigente_desde', '-id')
            .first()
        )
        limite_creado_por_futura = tarifa_bloqueada.vigente_desde - timedelta(
            days=1
        )
        if anterior and anterior.vigente_hasta == limite_creado_por_futura:
            siguiente = (
                TarifaServicio.objects.filter(
                    servicio_id=tarifa_bloqueada.servicio_id,
                    estado=TarifaServicio.ESTADO_PUBLICADA,
                    vigente_desde__gt=tarifa_bloqueada.vigente_desde,
                )
                .order_by('vigente_desde', 'id')
                .first()
            )
            anterior.vigente_hasta = (
                siguiente.vigente_desde - timedelta(days=1)
                if siguiente
                else None
            )
            anterior.full_clean()
            anterior.save(update_fields=['vigente_hasta'])

        return tarifa_bloqueada


def _normalizar_precio(valor):
    if isinstance(valor, float):
        raise ValidationError('El precio debe proporcionarse como Decimal, no float.')
    try:
        return Decimal(valor).quantize(
            Decimal('0.01'),
            rounding=ROUND_HALF_UP,
        )
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValidationError('El precio final no es válido.') from error


def _validar_datos_publicacion(
    *,
    servicio,
    precio_final,
    gratuita,
    vigente_desde,
    actor,
    origen,
):
    if servicio is None or servicio.pk is None:
        raise ValidationError('La publicación requiere un servicio persistido.')
    if actor is None or actor.pk is None:
        raise ValidationError('La publicación requiere un actor persistido.')
    if not isinstance(vigente_desde, date):
        raise ValidationError('La vigencia inicial debe ser una fecha válida.')
    if origen not in dict(TarifaServicio.ORIGEN_CHOICES):
        raise ValidationError('El origen de la tarifa no es válido.')
    if gratuita and precio_final != Decimal('0.00'):
        raise ValidationError('Una tarifa gratuita debe tener precio final cero.')
    if not gratuita and precio_final <= Decimal('0.00'):
        raise ValidationError(
            'Una tarifa no gratuita debe tener precio final mayor que cero.'
        )


def _validar_servicio_publicable(servicio):
    if not servicio.activo:
        raise ValidationError('No se puede publicar una tarifa para un servicio inactivo.')
    if servicio.reemplazado_por_id is not None:
        raise ValidationError(
            'No se puede publicar una tarifa para una variante histórica.'
        )
    if servicio.tratamiento_iva is None:
        raise ValidationError('El servicio no tiene tratamiento fiscal definido.')
    _tasa_para_tratamiento(servicio.tratamiento_iva)


def _tasa_para_tratamiento(tratamiento):
    tasas = {
        Servicio.IVA_INCLUIDO_16: Decimal('16.00'),
        Servicio.IVA_EXENTO: Decimal('0.00'),
    }
    try:
        return tasas[tratamiento]
    except KeyError as error:
        raise ValidationError('El tratamiento fiscal del servicio no es válido.') from error


def _validar_cronologia_publicacion(publicadas, vigente_desde):
    hoy = timezone.localdate()
    if vigente_desde > hoy and any(
        tarifa.vigente_desde > hoy for tarifa in publicadas
    ):
        raise ValidationError(
            'Ya existe una tarifa futura publicada para este servicio. '
            'Debe cancelarse antes de programar otra.'
        )
    if any(tarifa.vigente_desde >= vigente_desde for tarifa in publicadas):
        raise ValidationError(
            'Ya existe una tarifa publicada desde esa fecha o una fecha posterior. '
            'Cancela primero la tarifa futura correspondiente.'
        )
