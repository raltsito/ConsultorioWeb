from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Permission, User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    NotificacionTarifa,
    PropuestaTarifaDetalle,
    PropuestaTarifas,
    Servicio,
    TarifaServicio,
)
from .services_propuestas_tarifas import (
    aprobar_propuesta_tarifas,
    duplicar_propuesta_rechazada,
    enviar_propuesta_tarifas,
    rechazar_propuesta_tarifas,
)
from .services_tarifas import publicar_tarifa_servicio
from .tests_helpers import ClinicaTestDataMixin


PERMISOS_RECEPCION = (
    'view_service_catalog',
    'propose_service_tariff',
    'submit_service_tariff_proposal',
)
PERMISOS_DIRECCION = (
    'view_service_catalog',
    'review_service_tariff_proposal',
    'publish_service_tariff',
    'cancel_future_service_tariff',
)


class PropuestasTarifasBase(TestCase):
    def setUp(self):
        self.recepcion = User.objects.create_user(username='recepcion_tarifas')
        self.direccion = User.objects.create_user(username='direccion_tarifas')
        self.terapeuta = User.objects.create_user(username='terapeuta_tarifas')
        self._asignar(self.recepcion, PERMISOS_RECEPCION)
        self._asignar(self.direccion, PERMISOS_DIRECCION)
        self.servicio = Servicio.objects.create(
            nombre='Servicio propuesta',
            codigo='PROP-1',
            activo=True,
            tratamiento_iva=Servicio.IVA_INCLUIDO_16,
            precio=Decimal('600.00'),
        )
        self.otro_servicio = Servicio.objects.create(
            nombre='Otro servicio propuesta',
            codigo='PROP-2',
            activo=True,
            tratamiento_iva=Servicio.IVA_EXENTO,
            precio=Decimal('900.00'),
        )
        self.vigencia = timezone.localdate() + timedelta(days=10)

    def _asignar(self, usuario, codenames):
        usuario.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label='clinica',
                codename__in=codenames,
            )
        )

    def crear_propuesta(self, *, estado=PropuestaTarifas.ESTADO_BORRADOR):
        return PropuestaTarifas.objects.create(
            vigencia_propuesta=self.vigencia,
            observaciones='Revisión trimestral',
            estado=estado,
            creada_por=self.recepcion,
        )

    def agregar_detalle(self, propuesta, servicio=None, precio='650.00', gratuita=False):
        return PropuestaTarifaDetalle.objects.create(
            propuesta=propuesta,
            servicio=servicio or self.servicio,
            precio_propuesto=Decimal(precio),
            gratuita_propuesta=gratuita,
        )

    def enviar(self, propuesta):
        with self.captureOnCommitCallbacks(execute=True):
            return enviar_propuesta_tarifas(
                propuesta=propuesta,
                actor=self.recepcion,
            )


class ModelosPropuestaTests(PropuestasTarifasBase):
    def test_propuesta_inicia_borrador_con_auditoria(self):
        propuesta = self.crear_propuesta()
        self.assertEqual(propuesta.estado, PropuestaTarifas.ESTADO_BORRADOR)
        self.assertEqual(propuesta.creada_por, self.recepcion)
        self.assertIsNotNone(propuesta.creada_en)
        self.assertIsNotNone(propuesta.actualizada_en)

    def test_servicio_es_unico_por_propuesta(self):
        propuesta = self.crear_propuesta()
        self.agregar_detalle(propuesta)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.agregar_detalle(propuesta)


class EnvioPropuestaTests(PropuestasTarifasBase):
    def test_no_envia_sin_detalles(self):
        with self.assertRaises(ValidationError):
            self.enviar(self.crear_propuesta())

    def test_primera_tarifa_congela_snapshot_nulo_y_notifica_direccion(self):
        propuesta = self.crear_propuesta()
        detalle = self.agregar_detalle(propuesta)
        self.enviar(propuesta)
        propuesta.refresh_from_db()
        detalle.refresh_from_db()
        self.assertEqual(propuesta.estado, PropuestaTarifas.ESTADO_PENDIENTE)
        self.assertEqual(propuesta.enviada_por, self.recepcion)
        self.assertIsNone(detalle.tarifa_actual_id)
        self.assertIsNone(detalle.precio_actual_snapshot)
        self.assertIsNone(detalle.gratuita_actual_snapshot)
        self.assertTrue(NotificacionTarifa.objects.filter(
            destinatario=self.direccion,
            tipo=NotificacionTarifa.TIPO_PROPUESTA_ENVIADA,
        ).exists())

    def test_tarifa_existente_congela_snapshot(self):
        actual = publicar_tarifa_servicio(
            servicio=self.servicio,
            precio_final=Decimal('600.00'),
            gratuita=False,
            vigente_desde=timezone.localdate() - timedelta(days=30),
            actor=self.direccion,
            origen=TarifaServicio.ORIGEN_DIRECCION,
        )
        propuesta = self.crear_propuesta()
        detalle = self.agregar_detalle(propuesta)
        self.enviar(propuesta)
        detalle.refresh_from_db()
        self.assertEqual(detalle.tarifa_actual, actual)
        self.assertEqual(detalle.precio_actual_snapshot, Decimal('600.00'))
        self.assertFalse(detalle.gratuita_actual_snapshot)

    def test_rechaza_historico_e_iva_pendiente(self):
        historico = Servicio.objects.create(
            nombre='Histórico', activo=False, reemplazado_por=self.servicio,
            tratamiento_iva=Servicio.IVA_INCLUIDO_16,
        )
        propuesta = self.crear_propuesta()
        self.agregar_detalle(propuesta, historico)
        with self.assertRaises(ValidationError):
            self.enviar(propuesta)
        propuesta.detalles.all().delete()
        sin_iva = Servicio.objects.create(nombre='Sin IVA', activo=True)
        self.agregar_detalle(propuesta, sin_iva)
        with self.assertRaises(ValidationError):
            self.enviar(propuesta)

    def test_notificacion_no_se_crea_si_transaccion_externa_revierte(self):
        propuesta = self.crear_propuesta()
        self.agregar_detalle(propuesta)
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    enviar_propuesta_tarifas(propuesta=propuesta, actor=self.recepcion)
                    raise RuntimeError('rollback')
            except RuntimeError:
                pass
        self.assertFalse(NotificacionTarifa.objects.exists())


class AprobacionPropuestaTests(PropuestasTarifasBase):
    def test_aprueba_todas_lineas_y_enlaza_tarifas(self):
        propuesta = self.crear_propuesta()
        self.agregar_detalle(propuesta, self.servicio, '650.00')
        self.agregar_detalle(propuesta, self.otro_servicio, '950.00')
        self.enviar(propuesta)
        with self.captureOnCommitCallbacks(execute=True):
            aprobar_propuesta_tarifas(propuesta=propuesta, actor=self.direccion)
        propuesta.refresh_from_db()
        self.assertEqual(propuesta.estado, PropuestaTarifas.ESTADO_APROBADA)
        self.assertEqual(propuesta.aprobada_por, self.direccion)
        self.assertEqual(TarifaServicio.objects.count(), 2)
        self.assertFalse(propuesta.detalles.filter(tarifa_publicada__isnull=True).exists())
        self.assertFalse(TarifaServicio.objects.exclude(
            origen=TarifaServicio.ORIGEN_PROPUESTA
        ).exists())
        self.assertTrue(NotificacionTarifa.objects.filter(
            destinatario=self.recepcion,
            tipo=NotificacionTarifa.TIPO_PROPUESTA_APROBADA,
        ).exists())

    def test_stale_permanece_pendiente_y_no_publica(self):
        propuesta = self.crear_propuesta()
        self.agregar_detalle(propuesta)
        self.enviar(propuesta)
        publicar_tarifa_servicio(
            servicio=self.servicio,
            precio_final=Decimal('625.00'),
            gratuita=False,
            vigente_desde=timezone.localdate(),
            actor=self.direccion,
            origen=TarifaServicio.ORIGEN_DIRECCION,
        )
        with self.assertRaises(ValidationError):
            aprobar_propuesta_tarifas(propuesta=propuesta, actor=self.direccion)
        propuesta.refresh_from_db()
        self.assertEqual(propuesta.estado, PropuestaTarifas.ESTADO_PENDIENTE)
        self.assertEqual(TarifaServicio.objects.count(), 1)

    def test_error_en_segunda_linea_hace_rollback_total(self):
        propuesta = self.crear_propuesta()
        self.agregar_detalle(propuesta, self.servicio, '650.00')
        self.agregar_detalle(propuesta, self.otro_servicio, '950.00')
        self.enviar(propuesta)
        publicar_tarifa_servicio(
            servicio=self.otro_servicio,
            precio_final=Decimal('925.00'),
            gratuita=False,
            vigente_desde=self.vigencia,
            actor=self.direccion,
            origen=TarifaServicio.ORIGEN_DIRECCION,
        )
        with self.assertRaises(ValidationError):
            aprobar_propuesta_tarifas(propuesta=propuesta, actor=self.direccion)
        self.assertFalse(TarifaServicio.objects.filter(servicio=self.servicio).exists())
        propuesta.refresh_from_db()
        self.assertEqual(propuesta.estado, PropuestaTarifas.ESTADO_PENDIENTE)

    def test_doble_aprobacion_no_duplica(self):
        propuesta = self.crear_propuesta()
        self.agregar_detalle(propuesta)
        self.enviar(propuesta)
        aprobar_propuesta_tarifas(propuesta=propuesta, actor=self.direccion)
        with self.assertRaises(ValidationError):
            aprobar_propuesta_tarifas(propuesta=propuesta, actor=self.direccion)
        self.assertEqual(TarifaServicio.objects.count(), 1)


class RechazoPropuestaTests(PropuestasTarifasBase):
    def test_rechazo_exige_motivo_notifica_y_no_publica(self):
        propuesta = self.crear_propuesta()
        self.agregar_detalle(propuesta)
        self.enviar(propuesta)
        with self.assertRaises(ValidationError):
            rechazar_propuesta_tarifas(
                propuesta=propuesta, actor=self.direccion, motivo=' '
            )
        with self.captureOnCommitCallbacks(execute=True):
            rechazar_propuesta_tarifas(
                propuesta=propuesta,
                actor=self.direccion,
                motivo='Revisar tarifa médica',
            )
        propuesta.refresh_from_db()
        self.assertEqual(propuesta.estado, PropuestaTarifas.ESTADO_RECHAZADA)
        self.assertEqual(propuesta.motivo_rechazo, 'Revisar tarifa médica')
        self.assertFalse(TarifaServicio.objects.exists())
        self.assertTrue(NotificacionTarifa.objects.filter(
            destinatario=self.recepcion,
            tipo=NotificacionTarifa.TIPO_PROPUESTA_RECHAZADA,
        ).exists())

    def test_duplicar_rechazada_crea_borrador_independiente(self):
        propuesta = self.crear_propuesta()
        self.agregar_detalle(propuesta)
        self.enviar(propuesta)
        rechazar_propuesta_tarifas(
            propuesta=propuesta,
            actor=self.direccion,
            motivo='Corregir',
        )
        propuesta.refresh_from_db()
        nueva = duplicar_propuesta_rechazada(
            propuesta=propuesta,
            actor=self.recepcion,
        )
        self.assertNotEqual(nueva.pk, propuesta.pk)
        self.assertEqual(nueva.estado, PropuestaTarifas.ESTADO_BORRADOR)
        self.assertEqual(nueva.detalles.count(), 1)
        self.assertIsNone(nueva.enviada_en)


class PermisosYVistasTarifasTests(PropuestasTarifasBase):
    def test_catalogo_y_propuestas_respetan_permisos(self):
        self.client.force_login(self.recepcion)
        self.assertRedirects(
            self.client.get(reverse('catalogo_servicios_tarifas')),
            reverse('precios_servicios'),
        )
        self.assertEqual(self.client.get(reverse('propuesta_tarifas_nueva')).status_code, 200)
        self.assertEqual(self.client.get(reverse('propuestas_tarifas_pendientes')).status_code, 403)
        self.assertEqual(self.client.get(reverse('tarifa_servicio_directa')).status_code, 403)
        self.client.force_login(self.direccion)
        self.assertRedirects(
            self.client.get(reverse('catalogo_servicios_tarifas')),
            reverse('precios_servicios'),
        )
        self.assertEqual(self.client.get(reverse('propuestas_tarifas_pendientes')).status_code, 200)
        self.assertEqual(self.client.get(reverse('tarifa_servicio_directa')).status_code, 200)
        self.client.force_login(self.terapeuta)
        self.assertEqual(self.client.get(reverse('catalogo_servicios_tarifas')).status_code, 403)

    def test_direccion_publica_directo_y_recepcion_no(self):
        datos = {
            'servicio': self.servicio.pk,
            'precio_final': '700.00',
            'vigente_desde': timezone.localdate().isoformat(),
            'motivo': 'Ajuste Dirección',
        }
        self.client.force_login(self.recepcion)
        self.assertEqual(
            self.client.post(reverse('tarifa_servicio_directa'), datos).status_code,
            403,
        )
        self.client.force_login(self.direccion)
        response = self.client.post(reverse('tarifa_servicio_directa'), datos)
        self.assertRedirects(response, reverse('precios_servicios'))
        self.assertEqual(
            TarifaServicio.objects.get().origen,
            TarifaServicio.ORIGEN_DIRECCION,
        )

    def test_notificacion_se_marca_leida_y_contador_baja(self):
        propuesta = self.crear_propuesta()
        notificacion = NotificacionTarifa.objects.create(
            destinatario=self.direccion,
            tipo=NotificacionTarifa.TIPO_PROPUESTA_ENVIADA,
            propuesta=propuesta,
        )
        self.client.force_login(self.direccion)
        self.assertEqual(
            self.direccion.notificaciones_tarifas.filter(leida_en__isnull=True).count(),
            1,
        )
        self.client.post(reverse('notificacion_tarifa_marcar_leida', args=[notificacion.pk]))
        notificacion.refresh_from_db()
        self.assertIsNotNone(notificacion.leida_en)


class PantallaUnicaPropuestaTests(PropuestasTarifasBase):
    def datos_pantalla(self, lineas, *, accion='guardar', iniciales=0, observaciones='Ajuste mensual'):
        datos = {
            'vigencia_propuesta': self.vigencia.isoformat(),
            'observaciones': observaciones,
            'accion': accion,
            'detalles-TOTAL_FORMS': str(len(lineas)),
            'detalles-INITIAL_FORMS': str(iniciales),
            'detalles-MIN_NUM_FORMS': '0',
            'detalles-MAX_NUM_FORMS': '1000',
        }
        for indice, linea in enumerate(lineas):
            prefijo = f'detalles-{indice}'
            datos[f'{prefijo}-id'] = str(linea.get('id', ''))
            datos[f'{prefijo}-propuesta'] = str(linea.get('propuesta', ''))
            datos[f'{prefijo}-servicio'] = str(linea['servicio'])
            datos[f'{prefijo}-precio_propuesto'] = str(linea['precio'])
            datos[f'{prefijo}-gratuita_propuesta'] = (
                'True' if linea.get('gratuita', False) else 'False'
            )
            if linea.get('eliminar'):
                datos[f'{prefijo}-DELETE'] = 'on'
        return datos

    def test_nueva_pantalla_reune_datos_servicios_y_acciones(self):
        publicar_tarifa_servicio(
            servicio=self.servicio,
            precio_final=Decimal('650.00'),
            gratuita=False,
            vigente_desde=timezone.localdate(),
            actor=self.direccion,
            origen=TarifaServicio.ORIGEN_DIRECCION,
        )
        self.client.force_login(self.recepcion)

        response = self.client.get(reverse('propuesta_tarifas_nueva'))

        self.assertContains(response, 'Nueva propuesta de tarifas')
        self.assertContains(response, 'Vigente desde')
        self.assertContains(response, 'Tarifa actual')
        self.assertContains(response, 'Nueva tarifa')
        self.assertContains(response, 'Agregar servicio')
        self.assertContains(response, 'Enviar a Dirección')
        self.assertContains(response, 'Guardar borrador')
        self.assertEqual(
            response.context['tarifas_actuales'][str(self.servicio.pk)],
            '650.00',
        )
        self.assertIsNone(
            response.context['tarifas_actuales'][str(self.otro_servicio.pk)]
        )
        self.assertNotContains(response, 'legacy')

    def test_crea_un_servicio_y_guarda_borrador_desde_una_pantalla(self):
        self.client.force_login(self.recepcion)

        response = self.client.post(
            reverse('propuesta_tarifas_nueva'),
            self.datos_pantalla([
                {'servicio': self.servicio.pk, 'precio': '700.00'},
            ]),
        )

        propuesta = PropuestaTarifas.objects.get()
        self.assertRedirects(
            response,
            reverse('propuesta_tarifas_detalle', args=[propuesta.pk]),
        )
        self.assertEqual(propuesta.estado, PropuestaTarifas.ESTADO_BORRADOR)
        self.assertEqual(propuesta.detalles.count(), 1)
        self.assertEqual(
            propuesta.detalles.get().precio_propuesto,
            Decimal('700.00'),
        )

    def test_envio_directo_multiservicio_queda_read_only(self):
        self.client.force_login(self.recepcion)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('propuesta_tarifas_nueva'),
                self.datos_pantalla([
                    {'servicio': self.servicio.pk, 'precio': '700.00'},
                    {
                        'servicio': self.otro_servicio.pk,
                        'precio': '0.00',
                        'gratuita': True,
                    },
                ], accion='enviar'),
            )

        propuesta = PropuestaTarifas.objects.get()
        self.assertRedirects(
            response,
            reverse('propuesta_tarifas_detalle', args=[propuesta.pk]),
        )
        self.assertEqual(propuesta.estado, PropuestaTarifas.ESTADO_PENDIENTE)
        self.assertEqual(propuesta.detalles.count(), 2)
        consulta = self.client.get(
            reverse('propuesta_tarifas_detalle', args=[propuesta.pk])
        )
        self.assertContains(consulta, 'Con cobro')
        self.assertContains(consulta, 'Gratuito')
        self.assertNotContains(consulta, 'Guardar borrador')
        self.assertNotContains(consulta, 'Agregar servicio')
        self.servicio.refresh_from_db()
        self.otro_servicio.refresh_from_db()
        self.assertEqual(self.servicio.precio, Decimal('600.00'))
        self.assertEqual(self.otro_servicio.precio, Decimal('900.00'))

    def test_edita_borrador_y_sustituye_servicio_en_misma_pantalla(self):
        propuesta = self.crear_propuesta()
        detalle = self.agregar_detalle(propuesta)
        self.client.force_login(self.recepcion)

        response = self.client.post(
            reverse('propuesta_tarifas_detalle', args=[propuesta.pk]),
            self.datos_pantalla(
                [
                    {
                        'id': detalle.pk,
                        'propuesta': propuesta.pk,
                        'servicio': self.servicio.pk,
                        'precio': '650.00',
                        'eliminar': True,
                    },
                    {
                        'propuesta': propuesta.pk,
                        'servicio': self.otro_servicio.pk,
                        'precio': '975.00',
                    },
                ],
                iniciales=1,
                observaciones='Borrador corregido',
            ),
        )

        self.assertRedirects(
            response,
            reverse('propuesta_tarifas_detalle', args=[propuesta.pk]),
        )
        propuesta.refresh_from_db()
        self.assertEqual(propuesta.observaciones, 'Borrador corregido')
        self.assertEqual(propuesta.detalles.count(), 1)
        self.assertEqual(propuesta.detalles.get().servicio, self.otro_servicio)
        self.assertEqual(
            propuesta.detalles.get().precio_propuesto,
            Decimal('975.00'),
        )

    def test_servicio_duplicado_se_rechaza_sin_crear_propuesta(self):
        self.client.force_login(self.recepcion)

        response = self.client.post(
            reverse('propuesta_tarifas_nueva'),
            self.datos_pantalla([
                {'servicio': self.servicio.pk, 'precio': '700.00'},
                {'servicio': self.servicio.pk, 'precio': '725.00'},
            ], accion='enviar'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Cada servicio puede aparecer una sola vez en la propuesta.',
        )
        self.assertFalse(PropuestaTarifas.objects.exists())
        self.assertFalse(PropuestaTarifaDetalle.objects.exists())

    def test_valida_precio_y_gratuidad_antes_de_guardar(self):
        self.client.force_login(self.recepcion)

        con_cobro_cero = self.client.post(
            reverse('propuesta_tarifas_nueva'),
            self.datos_pantalla([
                {'servicio': self.servicio.pk, 'precio': '0.00'},
            ]),
        )
        gratuita_con_precio = self.client.post(
            reverse('propuesta_tarifas_nueva'),
            self.datos_pantalla([
                {
                    'servicio': self.otro_servicio.pk,
                    'precio': '10.00',
                    'gratuita': True,
                },
            ]),
        )

        self.assertContains(
            con_cobro_cero,
            'Una tarifa con cobro debe ser mayor que cero.',
        )
        self.assertContains(
            gratuita_con_precio,
            'Un servicio gratuito debe tener precio igual a cero.',
        )
        self.assertFalse(PropuestaTarifas.objects.exists())

    def test_error_en_una_linea_revierte_envio_completo(self):
        sin_fiscal = Servicio.objects.create(
            nombre='Servicio sin tratamiento fiscal',
            codigo='SIN-FISCAL',
            activo=True,
        )
        self.client.force_login(self.recepcion)

        response = self.client.post(
            reverse('propuesta_tarifas_nueva'),
            self.datos_pantalla([
                {'servicio': self.servicio.pk, 'precio': '700.00'},
                {'servicio': sin_fiscal.pk, 'precio': '500.00'},
            ], accion='enviar'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'tratamiento fiscal pendiente')
        self.assertFalse(PropuestaTarifas.objects.exists())
        self.assertFalse(PropuestaTarifaDetalle.objects.exists())
        self.assertFalse(NotificacionTarifa.objects.exists())


class PantallaUnicaConCitaTests(ClinicaTestDataMixin, TestCase):
    def test_aprobacion_publica_tarifa_sin_cambiar_servicio_ni_cita(self):
        self.servicio.tratamiento_iva = Servicio.IVA_INCLUIDO_16
        self.servicio.save(update_fields=['tratamiento_iva'])
        cita = self.crear_cita(costo=Decimal('321.50'))
        vigencia = timezone.localdate() + timedelta(days=10)
        self.client.force_login(self.staff)
        datos = {
            'vigencia_propuesta': vigencia.isoformat(),
            'observaciones': 'Propuesta completa',
            'accion': 'enviar',
            'detalles-TOTAL_FORMS': '1',
            'detalles-INITIAL_FORMS': '0',
            'detalles-MIN_NUM_FORMS': '0',
            'detalles-MAX_NUM_FORMS': '1000',
            'detalles-0-id': '',
            'detalles-0-propuesta': '',
            'detalles-0-servicio': str(self.servicio.pk),
            'detalles-0-precio_propuesto': '700.00',
            'detalles-0-gratuita_propuesta': 'False',
        }

        response = self.client.post(reverse('propuesta_tarifas_nueva'), datos)
        propuesta = PropuestaTarifas.objects.get()
        self.assertRedirects(
            response,
            reverse('propuesta_tarifas_detalle', args=[propuesta.pk]),
        )
        self.client.post(
            reverse('propuesta_tarifas_aprobar', args=[propuesta.pk])
        )

        propuesta.refresh_from_db()
        cita.refresh_from_db()
        self.servicio.refresh_from_db()
        self.assertEqual(propuesta.estado, PropuestaTarifas.ESTADO_APROBADA)
        self.assertEqual(
            TarifaServicio.objects.get(servicio=self.servicio).precio_final,
            Decimal('700.00'),
        )
        self.assertEqual(self.servicio.precio, Decimal('600.00'))
        self.assertEqual(cita.costo, Decimal('321.50'))
