from datetime import date, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from .models import Cita, Paciente, Servicio, SolicitudCita, TarifaServicio
from .services_tarifas import (
    IntegridadTarifasError,
    cancelar_tarifa_futura,
    obtener_proxima_tarifa,
    obtener_tarifa_vigente,
    publicar_tarifa_servicio,
)


class TarifasTestBase(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(username='direccion')
        self.servicio = Servicio.objects.create(
            nombre='Servicio con IVA',
            codigo='SERV-IVA',
            activo=True,
            tratamiento_iva=Servicio.IVA_INCLUIDO_16,
            precio=Decimal('777.00'),
        )
        self.servicio_exento = Servicio.objects.create(
            nombre='Servicio exento',
            codigo='SERV-EXENTO',
            activo=True,
            tratamiento_iva=Servicio.IVA_EXENTO,
            precio=Decimal('900.00'),
        )

    def publicar(
        self,
        *,
        servicio=None,
        precio='500.00',
        gratuita=False,
        desde=date(2026, 1, 1),
        origen=TarifaServicio.ORIGEN_DIRECCION,
        motivo='',
    ):
        return publicar_tarifa_servicio(
            servicio=servicio or self.servicio,
            precio_final=Decimal(precio),
            gratuita=gratuita,
            vigente_desde=desde,
            actor=self.actor,
            origen=origen,
            motivo=motivo,
        )

    def tarifa_directa(
        self,
        *,
        servicio=None,
        precio='500.00',
        desde=date(2026, 1, 1),
        hasta=None,
        estado=TarifaServicio.ESTADO_PUBLICADA,
    ):
        return TarifaServicio.objects.create(
            servicio=servicio or self.servicio,
            precio_final=Decimal(precio),
            gratuita=False,
            vigente_desde=desde,
            vigente_hasta=hasta,
            estado=estado,
            origen=TarifaServicio.ORIGEN_DIRECCION,
            tratamiento_iva_snapshot=Servicio.IVA_INCLUIDO_16,
            tasa_iva_snapshot=Decimal('16.00'),
            creada_por=self.actor,
            publicada_por=self.actor,
            publicada_en=timezone.now(),
        )


class TarifaServicioModeloTests(TarifasTestBase):
    def test_servicio_conserva_multiples_tarifas_historicas(self):
        primera = self.publicar(precio='500.00', desde=date(2026, 1, 1))
        segunda = self.publicar(precio='550.00', desde=date(2026, 9, 1))
        primera.refresh_from_db()
        self.assertEqual(self.servicio.tarifas.count(), 2)
        self.assertEqual(primera.vigente_hasta, date(2026, 8, 31))
        self.assertIsNone(segunda.vigente_hasta)

    def test_precio_final_permanece_decimal(self):
        tarifa = self.publicar(precio='500.00')
        tarifa.refresh_from_db()
        self.assertIsInstance(tarifa.precio_final, Decimal)
        with self.assertRaises(ValidationError):
            publicar_tarifa_servicio(
                servicio=self.servicio,
                precio_final=500.0,
                gratuita=False,
                vigente_desde=date(2027, 1, 1),
                actor=self.actor,
                origen=TarifaServicio.ORIGEN_DIRECCION,
            )

    def test_gratuita_exige_precio_cero(self):
        tarifa = TarifaServicio(
            servicio=self.servicio,
            precio_final=Decimal('1.00'),
            gratuita=True,
            vigente_desde=date(2026, 1, 1),
            estado=TarifaServicio.ESTADO_PUBLICADA,
            origen=TarifaServicio.ORIGEN_DIRECCION,
            tratamiento_iva_snapshot=Servicio.IVA_INCLUIDO_16,
            tasa_iva_snapshot=Decimal('16.00'),
            creada_por=self.actor,
            publicada_por=self.actor,
            publicada_en=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            tarifa.full_clean()

    def test_no_gratuita_exige_precio_mayor_que_cero(self):
        with self.assertRaises(ValidationError):
            self.publicar(precio='0.00', gratuita=False)

    def test_vigente_hasta_no_puede_ser_anterior(self):
        tarifa = self.tarifa_directa()
        tarifa.vigente_hasta = date(2025, 12, 31)
        with self.assertRaises(ValidationError):
            tarifa.full_clean()

    def test_clean_detecta_solapamiento_complementario(self):
        self.tarifa_directa(desde=date(2026, 1, 1))
        solapada = TarifaServicio(
            servicio=self.servicio,
            precio_final=Decimal('550.00'),
            gratuita=False,
            vigente_desde=date(2026, 2, 1),
            estado=TarifaServicio.ESTADO_PUBLICADA,
            origen=TarifaServicio.ORIGEN_DIRECCION,
            tratamiento_iva_snapshot=Servicio.IVA_INCLUIDO_16,
            tasa_iva_snapshot=Decimal('16.00'),
            creada_por=self.actor,
            publicada_por=self.actor,
            publicada_en=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            solapada.full_clean()

    def test_eliminar_servicio_referenciado_esta_protegido(self):
        self.publicar()
        with self.assertRaises(ProtectedError):
            self.servicio.delete()

    def test_snapshot_fiscal_no_se_reinterpreta(self):
        tarifa = self.publicar(precio='500.00')
        self.servicio.tratamiento_iva = Servicio.IVA_EXENTO
        self.servicio.save(update_fields=['tratamiento_iva'])
        tarifa.refresh_from_db()
        self.assertEqual(tarifa.tratamiento_iva_snapshot, Servicio.IVA_INCLUIDO_16)
        self.assertEqual(tarifa.tasa_iva_snapshot, Decimal('16.00'))


class CalculoIvaTests(TarifasTestBase):
    def test_iva_incluido_desglosa_precio_final(self):
        tarifa = self.publicar(precio='500.00')
        self.assertEqual(tarifa.subtotal, Decimal('431.03'))
        self.assertEqual(tarifa.importe_iva, Decimal('68.97'))
        self.assertEqual(tarifa.total, Decimal('500.00'))
        self.assertEqual(tarifa.subtotal + tarifa.importe_iva, tarifa.total)

    def test_exento_no_calcula_iva(self):
        tarifa = self.publicar(
            servicio=self.servicio_exento,
            precio='900.00',
        )
        self.assertEqual(tarifa.subtotal, Decimal('900.00'))
        self.assertEqual(tarifa.importe_iva, Decimal('0.00'))
        self.assertEqual(tarifa.total, Decimal('900.00'))


class ConsultaTarifasTests(TarifasTestBase):
    def test_limites_inclusivos_y_cambio_al_dia_siguiente(self):
        primera = self.publicar(precio='500.00', desde=date(2026, 1, 1))
        segunda = self.publicar(precio='550.00', desde=date(2026, 9, 1))
        self.assertIsNone(obtener_tarifa_vigente(self.servicio, date(2025, 12, 31)))
        self.assertEqual(obtener_tarifa_vigente(self.servicio, date(2026, 1, 1)), primera)
        self.assertEqual(obtener_tarifa_vigente(self.servicio, date(2026, 5, 1)), primera)
        self.assertEqual(obtener_tarifa_vigente(self.servicio, date(2026, 8, 31)), primera)
        self.assertEqual(obtener_tarifa_vigente(self.servicio, date(2026, 9, 1)), segunda)

    def test_servicio_sin_tarifas_devuelve_none(self):
        self.assertIsNone(
            obtener_tarifa_vigente(self.servicio, date(2026, 1, 1))
        )

    def test_tarifa_cancelada_es_ignorada(self):
        tarifa = self.tarifa_directa()
        TarifaServicio.objects.filter(pk=tarifa.pk).update(
            estado=TarifaServicio.ESTADO_CANCELADA,
            cancelada_por=self.actor,
            cancelada_en=timezone.now(),
            motivo_cancelacion='No usar',
        )
        self.assertIsNone(
            obtener_tarifa_vigente(self.servicio, date(2026, 2, 1))
        )

    def test_doble_coincidencia_genera_error_integridad(self):
        self.tarifa_directa(desde=date(2026, 1, 1))
        self.tarifa_directa(desde=date(2026, 2, 1))
        with self.assertRaises(IntegridadTarifasError):
            obtener_tarifa_vigente(self.servicio, date(2026, 3, 1))

    def test_obtener_proxima_tarifa(self):
        self.publicar(precio='500.00', desde=date(2026, 1, 1))
        futura = self.publicar(precio='550.00', desde=date(2026, 9, 1))
        self.assertEqual(
            obtener_proxima_tarifa(self.servicio, desde=date(2026, 8, 25)),
            futura,
        )
        self.assertIsNone(
            obtener_proxima_tarifa(self.servicio, desde=date(2026, 9, 1))
        )


class PublicacionTarifasTests(TarifasTestBase):
    def test_primera_publicacion_guarda_actor_origen_y_snapshot(self):
        tarifa = self.publicar(
            precio='500.00',
            origen=TarifaServicio.ORIGEN_PROPUESTA,
            motivo='Aprobación futura',
        )
        self.assertEqual(tarifa.creada_por, self.actor)
        self.assertEqual(tarifa.publicada_por, self.actor)
        self.assertEqual(tarifa.origen, TarifaServicio.ORIGEN_PROPUESTA)
        self.assertEqual(tarifa.motivo_publicacion, 'Aprobación futura')
        self.assertIsNotNone(tarifa.publicada_en)
        self.assertEqual(tarifa.tasa_iva_snapshot, Decimal('16.00'))

    def test_servicio_inactivo_es_rechazado(self):
        self.servicio.activo = False
        self.servicio.save(update_fields=['activo'])
        with self.assertRaises(ValidationError):
            self.publicar()

    def test_variante_historica_es_rechazada(self):
        variante = Servicio.objects.create(
            nombre='Variante',
            activo=False,
            reemplazado_por=self.servicio,
            tratamiento_iva=Servicio.IVA_INCLUIDO_16,
        )
        with self.assertRaises(ValidationError):
            self.publicar(servicio=variante)

    def test_servicio_sin_tratamiento_fiscal_es_rechazado(self):
        sin_fiscal = Servicio.objects.create(nombre='Sin fiscal', activo=True)
        with self.assertRaisesMessage(
            ValidationError,
            'El servicio no tiene tratamiento fiscal definido.',
        ):
            self.publicar(servicio=sin_fiscal)

    def test_tarifa_gratuita_correcta(self):
        tarifa = self.publicar(precio='0.00', gratuita=True)
        self.assertTrue(tarifa.gratuita)
        self.assertEqual(tarifa.total, Decimal('0.00'))

    def test_fecha_igual_o_anterior_a_publicada_es_rechazada(self):
        self.publicar(desde=date(2026, 9, 1))
        with self.assertRaises(ValidationError):
            self.publicar(desde=date(2026, 8, 1))
        with self.assertRaises(ValidationError):
            self.publicar(desde=date(2026, 9, 1))

    def test_no_programa_dos_tarifas_futuras(self):
        primera_fecha = timezone.localdate() + timedelta(days=10)
        segunda_fecha = timezone.localdate() + timedelta(days=20)
        self.publicar(desde=primera_fecha)

        with self.assertRaises(ValidationError):
            self.publicar(precio='550.00', desde=segunda_fecha)

    def test_error_intermedio_revierte_cierre_anterior(self):
        anterior = self.publicar(desde=date(2026, 1, 1))
        guardar_original = TarifaServicio.save

        def guardar_con_error(instancia, *args, **kwargs):
            if instancia.pk is None:
                raise RuntimeError('Error controlado')
            return guardar_original(instancia, *args, **kwargs)

        with patch.object(
            TarifaServicio,
            'save',
            autospec=True,
            side_effect=guardar_con_error,
        ):
            with self.assertRaises(RuntimeError):
                self.publicar(precio='550.00', desde=date(2026, 9, 1))

        anterior.refresh_from_db()
        self.assertIsNone(anterior.vigente_hasta)
        self.assertEqual(self.servicio.tarifas.count(), 1)

    def test_no_modifica_precio_legacy(self):
        self.publicar(precio='500.00')
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.precio, Decimal('777.00'))

    def test_no_modifica_cita_ni_fks_historicas(self):
        paciente = Paciente.objects.create(
            nombre='Paciente tarifa',
            fecha_nacimiento=date(1990, 1, 1),
            sexo='Femenino',
            telefono='5550000000',
            servicio_inicial=self.servicio,
        )
        cita = Cita.objects.create(
            paciente=paciente,
            fecha=date(2026, 7, 1),
            hora=time(10, 0),
            servicio=self.servicio,
            costo=Decimal('321.00'),
        )
        solicitud = SolicitudCita.objects.create(
            paciente_nombre='Paciente tarifa',
            telefono='5550000000',
            fecha_deseada=date(2026, 7, 2),
            paciente=paciente,
            servicio=self.servicio,
        )

        self.publicar(precio='500.00')
        paciente.refresh_from_db()
        cita.refresh_from_db()
        solicitud.refresh_from_db()

        self.assertEqual(paciente.servicio_inicial_id, self.servicio.id)
        self.assertEqual(cita.servicio_id, self.servicio.id)
        self.assertEqual(cita.costo, Decimal('321.00'))
        self.assertEqual(solicitud.servicio_id, self.servicio.id)


class CancelacionTarifaFuturaTests(TarifasTestBase):
    def setUp(self):
        super().setUp()
        self.actual = self.publicar(desde=date(2026, 1, 1))
        self.futura = self.publicar(
            precio='550.00',
            desde=date(2026, 9, 1),
        )

    def cancelar(self, **overrides):
        datos = {
            'tarifa': self.futura,
            'actor': self.actor,
            'motivo': 'Cambio autorizado',
            'fecha_operativa': date(2026, 8, 25),
        }
        datos.update(overrides)
        return cancelar_tarifa_futura(**datos)

    def test_cancela_futura_con_auditoria_y_repara_anterior(self):
        cancelada = self.cancelar()
        self.actual.refresh_from_db()
        self.assertEqual(cancelada.estado, TarifaServicio.ESTADO_CANCELADA)
        self.assertEqual(cancelada.cancelada_por, self.actor)
        self.assertIsNotNone(cancelada.cancelada_en)
        self.assertEqual(cancelada.motivo_cancelacion, 'Cambio autorizado')
        self.assertIsNone(self.actual.vigente_hasta)
        self.assertEqual(
            obtener_tarifa_vigente(self.servicio, date(2026, 9, 1)),
            self.actual,
        )

    def test_cancelacion_exige_motivo(self):
        with self.assertRaises(ValidationError):
            self.cancelar(motivo='  ')

    def test_no_cancela_tarifa_vigente(self):
        with self.assertRaises(ValidationError):
            cancelar_tarifa_futura(
                tarifa=self.actual,
                actor=self.actor,
                motivo='No procede',
                fecha_operativa=date(2026, 8, 25),
            )

    def test_no_cancela_tarifa_historica(self):
        with self.assertRaises(ValidationError):
            cancelar_tarifa_futura(
                tarifa=self.actual,
                actor=self.actor,
                motivo='No procede',
                fecha_operativa=date(2027, 1, 1),
            )

    def test_no_cancela_dos_veces(self):
        self.cancelar()
        with self.assertRaises(ValidationError):
            self.cancelar()
