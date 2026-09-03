from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    NotificacionTarifa,
    PropuestaTarifaDetalle,
    PropuestaTarifas,
    Servicio,
    TarifaServicio,
)
from .services_tarifas import (
    obtener_tarifa_vigente,
    publicar_tarifa_servicio,
    validar_publicacion_tarifa,
)


PERMISO_PROPONER = 'clinica.propose_service_tariff'
PERMISO_ENVIAR = 'clinica.submit_service_tariff_proposal'
PERMISO_REVISAR = 'clinica.review_service_tariff_proposal'
PERMISO_PUBLICAR = 'clinica.publish_service_tariff'


def enviar_propuesta_tarifas(*, propuesta, actor):
    _exigir_permiso(actor, PERMISO_ENVIAR)
    with transaction.atomic():
        bloqueada = PropuestaTarifas.objects.select_for_update().get(pk=propuesta.pk)
        if bloqueada.estado != PropuestaTarifas.ESTADO_BORRADOR:
            raise ValidationError('Sólo puede enviarse una propuesta en borrador.')
        if bloqueada.vigencia_propuesta < timezone.localdate():
            raise ValidationError('La vigencia propuesta no puede estar en el pasado.')

        detalles = list(
            PropuestaTarifaDetalle.objects.select_for_update()
            .select_related('servicio')
            .filter(propuesta=bloqueada)
            .order_by('servicio_id')
        )
        if not detalles:
            raise ValidationError('La propuesta debe contener al menos un servicio.')

        ahora = timezone.now()
        for detalle in detalles:
            _validar_detalle_enviable(detalle)
            tarifa_actual = obtener_tarifa_vigente(
                detalle.servicio,
                timezone.localdate(),
            )
            detalle.tarifa_actual = tarifa_actual
            detalle.precio_actual_snapshot = (
                tarifa_actual.precio_final if tarifa_actual else None
            )
            detalle.gratuita_actual_snapshot = (
                tarifa_actual.gratuita if tarifa_actual else None
            )
            detalle.save(
                update_fields=[
                    'tarifa_actual',
                    'precio_actual_snapshot',
                    'gratuita_actual_snapshot',
                ]
            )

        bloqueada.estado = PropuestaTarifas.ESTADO_PENDIENTE
        bloqueada.enviada_por = actor
        bloqueada.enviada_en = ahora
        bloqueada.save(update_fields=['estado', 'enviada_por', 'enviada_en', 'actualizada_en'])
        transaction.on_commit(
            lambda propuesta_id=bloqueada.pk: _notificar_revision(propuesta_id)
        )
        return bloqueada


def aprobar_propuesta_tarifas(*, propuesta, actor):
    _exigir_permiso(actor, PERMISO_REVISAR)
    _exigir_permiso(actor, PERMISO_PUBLICAR)
    with transaction.atomic():
        bloqueada = PropuestaTarifas.objects.select_for_update().get(pk=propuesta.pk)
        if bloqueada.estado != PropuestaTarifas.ESTADO_PENDIENTE:
            raise ValidationError('La propuesta ya no está pendiente de aprobación.')

        detalles = list(
            PropuestaTarifaDetalle.objects.select_for_update()
            .select_related('servicio', 'tarifa_actual')
            .filter(propuesta=bloqueada)
            .order_by('servicio_id')
        )
        servicios_ids = [detalle.servicio_id for detalle in detalles]
        servicios = {
            servicio.pk: servicio
            for servicio in Servicio.objects.select_for_update()
            .filter(pk__in=servicios_ids)
            .order_by('pk')
        }

        for detalle in detalles:
            detalle.servicio = servicios[detalle.servicio_id]
            _validar_snapshot_vigente(detalle)
            validar_publicacion_tarifa(
                servicio=detalle.servicio,
                precio_final=detalle.precio_propuesto,
                gratuita=detalle.gratuita_propuesta,
                vigente_desde=bloqueada.vigencia_propuesta,
                actor=actor,
                origen=TarifaServicio.ORIGEN_PROPUESTA,
            )

        for detalle in detalles:
            tarifa = publicar_tarifa_servicio(
                servicio=detalle.servicio,
                precio_final=detalle.precio_propuesto,
                gratuita=detalle.gratuita_propuesta,
                vigente_desde=bloqueada.vigencia_propuesta,
                actor=actor,
                origen=TarifaServicio.ORIGEN_PROPUESTA,
                motivo=f'Propuesta #{bloqueada.pk}',
            )
            detalle.tarifa_publicada = tarifa
            detalle.save(update_fields=['tarifa_publicada'])

        bloqueada.estado = PropuestaTarifas.ESTADO_APROBADA
        bloqueada.aprobada_por = actor
        bloqueada.aprobada_en = timezone.now()
        bloqueada.save(update_fields=['estado', 'aprobada_por', 'aprobada_en', 'actualizada_en'])
        transaction.on_commit(
            lambda propuesta_id=bloqueada.pk: _notificar_creador(
                propuesta_id,
                NotificacionTarifa.TIPO_PROPUESTA_APROBADA,
            )
        )
        return bloqueada


def rechazar_propuesta_tarifas(*, propuesta, actor, motivo):
    _exigir_permiso(actor, PERMISO_REVISAR)
    motivo_limpio = (motivo or '').strip()
    if not motivo_limpio:
        raise ValidationError('El rechazo requiere un motivo.')

    with transaction.atomic():
        bloqueada = PropuestaTarifas.objects.select_for_update().get(pk=propuesta.pk)
        if bloqueada.estado != PropuestaTarifas.ESTADO_PENDIENTE:
            raise ValidationError('Sólo puede rechazarse una propuesta pendiente.')
        bloqueada.estado = PropuestaTarifas.ESTADO_RECHAZADA
        bloqueada.rechazada_por = actor
        bloqueada.rechazada_en = timezone.now()
        bloqueada.motivo_rechazo = motivo_limpio
        bloqueada.save(
            update_fields=[
                'estado', 'rechazada_por', 'rechazada_en',
                'motivo_rechazo', 'actualizada_en',
            ]
        )
        transaction.on_commit(
            lambda propuesta_id=bloqueada.pk: _notificar_creador(
                propuesta_id,
                NotificacionTarifa.TIPO_PROPUESTA_RECHAZADA,
            )
        )
        return bloqueada


def duplicar_propuesta_rechazada(*, propuesta, actor):
    _exigir_permiso(actor, PERMISO_PROPONER)
    if propuesta.estado != PropuestaTarifas.ESTADO_RECHAZADA:
        raise ValidationError('Sólo pueden duplicarse propuestas rechazadas.')
    with transaction.atomic():
        nueva = PropuestaTarifas.objects.create(
            vigencia_propuesta=propuesta.vigencia_propuesta,
            observaciones=propuesta.observaciones,
            creada_por=actor,
        )
        PropuestaTarifaDetalle.objects.bulk_create(
            [
                PropuestaTarifaDetalle(
                    propuesta=nueva,
                    servicio=detalle.servicio,
                    precio_propuesto=detalle.precio_propuesto,
                    gratuita_propuesta=detalle.gratuita_propuesta,
                )
                for detalle in propuesta.detalles.select_related('servicio')
            ]
        )
        return nueva


def _validar_detalle_enviable(detalle):
    servicio = detalle.servicio
    if not servicio.activo or servicio.reemplazado_por_id is not None:
        raise ValidationError(f'{servicio}: no admite nuevas tarifas.')
    if servicio.tratamiento_iva is None:
        raise ValidationError(f'{servicio}: tratamiento fiscal pendiente.')
    if detalle.precio_propuesto is None:
        raise ValidationError(f'{servicio}: falta el precio propuesto.')
    precio = Decimal(detalle.precio_propuesto)
    if detalle.gratuita_propuesta and precio != Decimal('0.00'):
        raise ValidationError(f'{servicio}: una tarifa gratuita debe ser cero.')
    if not detalle.gratuita_propuesta and precio <= Decimal('0.00'):
        raise ValidationError(f'{servicio}: el precio debe ser mayor que cero.')


def _validar_snapshot_vigente(detalle):
    actual = obtener_tarifa_vigente(detalle.servicio, timezone.localdate())
    actual_id = actual.pk if actual else None
    if actual_id != detalle.tarifa_actual_id:
        raise ValidationError(
            f'{detalle.servicio}: la tarifa vigente cambió desde el envío.'
        )
    if actual:
        if (
            actual.precio_final != detalle.precio_actual_snapshot
            or actual.gratuita != detalle.gratuita_actual_snapshot
        ):
            raise ValidationError(
                f'{detalle.servicio}: la tarifa vigente cambió desde el envío.'
            )
    elif (
        detalle.precio_actual_snapshot is not None
        or detalle.gratuita_actual_snapshot is not None
    ):
        raise ValidationError(
            f'{detalle.servicio}: la tarifa vigente cambió desde el envío.'
        )


def _notificar_revision(propuesta_id):
    destinatarios = _usuarios_con_permiso(PERMISO_REVISAR)
    NotificacionTarifa.objects.bulk_create(
        [
            NotificacionTarifa(
                destinatario=usuario,
                tipo=NotificacionTarifa.TIPO_PROPUESTA_ENVIADA,
                propuesta_id=propuesta_id,
            )
            for usuario in destinatarios
        ],
        ignore_conflicts=True,
    )


def _notificar_creador(propuesta_id, tipo):
    propuesta = PropuestaTarifas.objects.get(pk=propuesta_id)
    destinatarios = {propuesta.creada_por_id, propuesta.enviada_por_id} - {None}
    NotificacionTarifa.objects.bulk_create(
        [
            NotificacionTarifa(
                destinatario_id=usuario_id,
                tipo=tipo,
                propuesta=propuesta,
            )
            for usuario_id in destinatarios
        ],
        ignore_conflicts=True,
    )


def _usuarios_con_permiso(permiso_completo):
    app_label, codename = permiso_completo.split('.', 1)
    User = get_user_model()
    return list(
        User.objects.filter(is_active=True)
        .filter(
            Q(is_superuser=True)
            | Q(user_permissions__content_type__app_label=app_label,
                user_permissions__codename=codename)
            | Q(groups__permissions__content_type__app_label=app_label,
                groups__permissions__codename=codename)
        )
        .distinct()
    )


def _exigir_permiso(actor, permiso):
    if actor is None or not actor.has_perm(permiso):
        raise PermissionDenied
