from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from clinica.models import (
    CategoriaServicio,
    Cita,
    MovimientoEconomicoCita,
    Pago,
    Servicio,
    TarifaServicio,
)
from clinica.services_beneficios import crear_regla_beneficio
from clinica.services_pagos import anular_pago, confirmar_pago, registrar_pago
from clinica.services_tarifas import publicar_tarifa_servicio
from clinica.tests_helpers import ClinicaTestDataMixin
from ventas.models import Captacion, Captador, ComisionCaptacion
from ventas.services import (
    aprobar_captacion,
    evaluar_y_generar_comision,
    registrar_captacion,
)


class ComisionesConPagoFormalTests(ClinicaTestDataMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.categoria = CategoriaServicio.objects.create(
            codigo='PSICO-COMISION',
            nombre='Psicoterapia comisión',
        )
        cls.servicio.categoria = cls.categoria
        cls.servicio.tratamiento_iva = Servicio.IVA_EXENTO
        cls.servicio.save(update_fields=['categoria', 'tratamiento_iva'])
        cls.tarifa = publicar_tarifa_servicio(
            servicio=cls.servicio,
            precio_final=Decimal('600.00'),
            gratuita=False,
            vigente_desde=timezone.localdate(),
            actor=cls.staff,
            origen=TarifaServicio.ORIGEN_DIRECCION,
        )
        crear_regla_beneficio(
            categoria=cls.categoria,
            porcentaje_descuento=Decimal('25.00'),
            vigente_desde=timezone.localdate(),
            actor=cls.staff,
        )
        cls.captador = Captador.objects.create(
            tipo=Captador.TIPO_EXTERNO,
            nombre_externo='Captador pago formal',
            tipo_organizacion=Captador.ORG_ESCUELA,
        )

    def crear_captacion(self, paciente=None, porcentaje=7):
        captacion = registrar_captacion(
            paciente=paciente or self.paciente,
            codigo=self.captador.codigo_activo,
            usuario=self.staff,
        )
        return aprobar_captacion(
            captacion=captacion,
            porcentaje=porcentaje,
            usuario=self.staff,
        )

    def crear_consulta(self, paciente=None, **cambios):
        cambios.setdefault('paciente', paciente or self.paciente)
        cambios.setdefault('estatus', Cita.ESTATUS_SI_ASISTIO)
        cambios.setdefault('costo', Decimal('999.00'))
        return self.crear_cita(**cambios)

    def registrar_recepcion(
        self,
        cita,
        *,
        esperado='450.00',
        recibido='450.00',
    ):
        return registrar_pago(
            cita=cita,
            importe_esperado=esperado,
            importe_reportado=recibido,
            metodo_pago='Efectivo',
            origen_registro=Pago.ORIGEN_RECEPCION,
            registrado_por=self.staff,
        )[0]

    def registrar_terapeuta(self, cita, *, esperado='450.00', recibido='450.00'):
        return registrar_pago(
            cita=cita,
            importe_esperado=esperado,
            importe_reportado=recibido,
            metodo_pago='Efectivo',
            origen_registro=Pago.ORIGEN_TERAPEUTA,
            registrado_por=self.usuario_terapeuta,
        )[0]

    def test_paciente_sin_captacion_no_genera_comision(self):
        cita = self.crear_consulta()

        self.registrar_recepcion(cita)

        self.assertFalse(ComisionCaptacion.objects.exists())

    def test_captacion_con_cita_no_asistida_no_genera(self):
        self.crear_captacion()
        cita = self.crear_consulta(estatus=Cita.ESTATUS_NO_ASISTIO)

        self.registrar_recepcion(cita)

        self.assertFalse(ComisionCaptacion.objects.exists())

    def test_asistencia_sin_cobro_formal_no_genera(self):
        captacion = self.crear_captacion()
        self.crear_consulta()

        resultado = evaluar_y_generar_comision(captacion)

        self.assertEqual(resultado.estado, 'cita_sin_pago')
        self.assertFalse(ComisionCaptacion.objects.exists())

    def test_pago_pendiente_no_genera(self):
        captacion = self.crear_captacion()
        cita = self.crear_consulta()
        self.registrar_terapeuta(cita)

        resultado = evaluar_y_generar_comision(captacion)

        self.assertEqual(resultado.estado, 'cita_sin_pago')
        self.assertFalse(ComisionCaptacion.objects.exists())

    def test_pago_anulado_no_genera(self):
        captacion = self.crear_captacion()
        cita = self.crear_consulta()
        pago = self.registrar_terapeuta(cita)
        anular_pago(
            pago=pago,
            anulado_por=self.staff,
            motivo='Pago inválido para la prueba.',
        )

        resultado = evaluar_y_generar_comision(captacion)

        self.assertEqual(resultado.estado, 'cita_sin_pago')
        self.assertFalse(ComisionCaptacion.objects.exists())

    def test_pago_parcial_no_genera_hasta_cubrir_totalmente(self):
        self.crear_captacion()
        cita = self.crear_consulta()

        self.registrar_recepcion(cita, recibido='400.00')
        self.assertFalse(ComisionCaptacion.objects.exists())

        self.registrar_recepcion(cita, recibido='50.00')
        self.assertEqual(ComisionCaptacion.objects.count(), 1)

    def test_confirmar_pago_completo_genera_comision_pendiente(self):
        captacion = self.crear_captacion(porcentaje=7)
        cita = self.crear_consulta()
        pago = self.registrar_terapeuta(cita)

        confirmar_pago(
            pago=pago,
            importe_verificado='450.00',
            verificado_por=self.staff,
        )

        comision = ComisionCaptacion.objects.get(captacion=captacion)
        self.assertEqual(comision.cita_generadora, cita)
        self.assertEqual(comision.base_calculo, Decimal('450.00'))
        self.assertEqual(comision.porcentaje_aplicado, 7)
        self.assertEqual(comision.monto_calculado, Decimal('31.50'))
        self.assertEqual(
            comision.estado,
            ComisionCaptacion.ESTADO_PENDIENTE_PAGO,
        )

    def test_segunda_consulta_no_duplica_comision(self):
        captacion = self.crear_captacion()
        primera = self.crear_consulta()
        segunda = self.crear_consulta(hora=self.hora.replace(hour=11))
        self.registrar_recepcion(primera)

        self.registrar_recepcion(segunda)

        self.assertEqual(ComisionCaptacion.objects.count(), 1)
        self.assertEqual(
            ComisionCaptacion.objects.get(captacion=captacion).cita_generadora,
            primera,
        )

    def test_reprocesar_no_duplica_comision(self):
        captacion = self.crear_captacion()
        cita = self.crear_consulta()
        self.registrar_recepcion(cita)
        original = ComisionCaptacion.objects.get()

        resultado = evaluar_y_generar_comision(captacion)

        self.assertEqual(resultado.estado, 'ya_existia')
        self.assertEqual(resultado.comision.pk, original.pk)
        self.assertEqual(ComisionCaptacion.objects.count(), 1)

    def test_tarifa_y_porcentaje_posteriores_no_recalculan_historico(self):
        captacion = self.crear_captacion(porcentaje=7)
        cita = self.crear_consulta()
        self.registrar_recepcion(cita)
        comision = ComisionCaptacion.objects.get()
        valores = (
            comision.base_calculo,
            comision.porcentaje_aplicado,
            comision.monto_calculado,
        )
        publicar_tarifa_servicio(
            servicio=self.servicio,
            precio_final=Decimal('800.00'),
            gratuita=False,
            vigente_desde=self.fecha + timedelta(days=1),
            actor=self.staff,
            origen=TarifaServicio.ORIGEN_DIRECCION,
        )
        Captacion.objects.filter(pk=captacion.pk).update(porcentaje_comision=10)

        evaluar_y_generar_comision(captacion)
        comision.refresh_from_db()

        self.assertEqual(
            (
                comision.base_calculo,
                comision.porcentaje_aplicado,
                comision.monto_calculado,
            ),
            valores,
        )

    def test_costo_no_es_evidencia_y_movimiento_legacy_no_se_usa(self):
        captacion = self.crear_captacion()
        cita = self.crear_consulta(costo=Decimal('4500.00'))
        MovimientoEconomicoCita.objects.create(
            cita=cita,
            importe=Decimal('4500.00'),
            metodo='Efectivo',
            registrado_por=self.staff,
        )

        resultado = evaluar_y_generar_comision(captacion)

        self.assertEqual(resultado.estado, 'cita_sin_pago')
        self.assertFalse(ComisionCaptacion.objects.exists())

    def test_generacion_no_crea_movimiento_economico(self):
        self.crear_captacion()
        cita = self.crear_consulta()
        movimientos_antes = MovimientoEconomicoCita.objects.count()

        self.registrar_recepcion(cita)

        self.assertEqual(
            MovimientoEconomicoCita.objects.count(),
            movimientos_antes,
        )

    def test_sin_porcentaje_configurado_no_genera(self):
        captacion = self.crear_captacion()
        Captacion.objects.filter(pk=captacion.pk).update(porcentaje_comision=None)
        cita = self.crear_consulta()

        self.registrar_recepcion(cita)
        resultado = evaluar_y_generar_comision(captacion)

        self.assertEqual(resultado.estado, 'datos_inconsistentes')
        self.assertFalse(ComisionCaptacion.objects.exists())

    def test_porcentaje_cero_es_valido_y_no_genera_comision(self):
        codigo = self.captador.codigo_activo
        codigo.porcentaje_comision = 0
        codigo.save(update_fields=['porcentaje_comision'])
        captacion = registrar_captacion(
            paciente=self.paciente,
            codigo=codigo,
            usuario=self.staff,
        )
        cita = self.crear_consulta()

        pago = self.registrar_recepcion(cita)
        resultado = evaluar_y_generar_comision(captacion)

        self.assertEqual(resultado.estado, 'sin_comision')
        self.assertEqual(captacion.porcentaje_comision, 0)
        self.assertIsNotNone(pago.pk)
        self.assertFalse(ComisionCaptacion.objects.exists())
