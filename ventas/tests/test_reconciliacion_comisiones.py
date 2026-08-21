from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from clinica.models import CorteSemanal, LineaNomina, MovimientoEconomicoCita
from clinica.services import anular_movimiento_economico
from ventas.models import ComisionCaptacion, EventoCaptacion
from ventas.services import (
    evaluar_y_generar_comision,
    reconciliar_comisiones_generadas,
    reconciliar_estado_comision,
)
from ventas.tests.test_generacion_comisiones import GeneracionComisionMixin


class ReconciliacionComisionesTests(GeneracionComisionMixin, TestCase):
    def preparar_comision(self, *, pago="200.00", servicio="450.00"):
        captacion = self.crear_captacion(porcentaje=7)
        cita = self.crear_cita_asistida(costo=Decimal(servicio))
        pago_objeto = self.registrar_pago_cita(
            cita,
            importe=pago,
            importe_servicio=servicio,
        )
        comision = evaluar_y_generar_comision(
            captacion,
            usuario=self.staff,
        ).comision
        return comision, cita, pago_objeto

    def contar_eventos(self, accion):
        return EventoCaptacion.objects.filter(accion=accion).count()

    def test_unico_pago_anulado_suspende_y_audita(self):
        comision, _, pago = self.preparar_comision()
        anular_movimiento_economico(movimiento=pago, usuario=self.staff, motivo="Pago incorrecto")

        resultado = reconciliar_estado_comision(comision, usuario=self.staff)
        comision.refresh_from_db()

        self.assertEqual(resultado.estado, "suspendida")
        self.assertEqual(comision.estado, ComisionCaptacion.ESTADO_SUSPENDIDA)
        self.assertEqual(
            self.contar_eventos(EventoCaptacion.ACCION_COMISION_SUSPENDIDA),
            1,
        )

    def test_otro_pago_vigente_evitar_suspension(self):
        comision, cita, pago_uno = self.preparar_comision()
        self.registrar_pago_cita(cita, importe="100.00")
        anular_movimiento_economico(movimiento=pago_uno, usuario=self.staff, motivo="Duplicado")

        resultado = reconciliar_estado_comision(comision)
        comision.refresh_from_db()

        self.assertEqual(resultado.estado, "sin_cambios")
        self.assertEqual(
            comision.estado,
            ComisionCaptacion.ESTADO_PENDIENTE_PAGO,
        )
        self.assertEqual(
            self.contar_eventos(EventoCaptacion.ACCION_COMISION_SUSPENDIDA),
            0,
        )

    def test_todos_los_pagos_anulados_suspenden(self):
        comision, cita, pago_uno = self.preparar_comision()
        pago_dos = self.registrar_pago_cita(cita, importe="100.00")
        anular_movimiento_economico(movimiento=pago_uno, usuario=self.staff, motivo="Primero")
        anular_movimiento_economico(movimiento=pago_dos, usuario=self.staff, motivo="Segundo")

        reconciliar_estado_comision(comision)
        comision.refresh_from_db()

        self.assertEqual(comision.estado, ComisionCaptacion.ESTADO_SUSPENDIDA)

    def test_nuevo_pago_reactiva_y_audita(self):
        comision, cita, pago = self.preparar_comision()
        anular_movimiento_economico(movimiento=pago, usuario=self.staff, motivo="CorrecciÃ³n")
        reconciliar_estado_comision(comision)
        self.registrar_pago_cita(cita, importe="50.00")

        resultado = reconciliar_estado_comision(comision, usuario=self.staff)
        comision.refresh_from_db()

        self.assertEqual(resultado.estado, "reactivada")
        self.assertEqual(
            comision.estado,
            ComisionCaptacion.ESTADO_PENDIENTE_PAGO,
        )
        self.assertEqual(
            self.contar_eventos(EventoCaptacion.ACCION_COMISION_REACTIVADA),
            1,
        )

    def test_suspension_y_reactivacion_conservan_snapshots(self):
        comision, cita, pago = self.preparar_comision()
        valores_originales = (
            comision.pk,
            comision.captacion_id,
            comision.cita_generadora_id,
            comision.base_calculo,
            comision.porcentaje_aplicado,
            comision.monto_calculado,
            comision.captador_nombre_snapshot,
            comision.paciente_nombre_snapshot,
        )
        anular_movimiento_economico(movimiento=pago, usuario=self.staff, motivo="CorrecciÃ³n")
        reconciliar_estado_comision(comision)
        self.registrar_pago_cita(cita, importe="50.00")
        reconciliar_estado_comision(comision)
        comision.refresh_from_db()

        self.assertEqual(
            (
                comision.pk,
                comision.captacion_id,
                comision.cita_generadora_id,
                comision.base_calculo,
                comision.porcentaje_aplicado,
                comision.monto_calculado,
                comision.captador_nombre_snapshot,
                comision.paciente_nombre_snapshot,
            ),
            valores_originales,
        )

    def test_nuevo_pago_de_importe_distinto_no_recalcula(self):
        comision, cita, pago = self.preparar_comision(pago="200.00")
        anular_movimiento_economico(movimiento=pago, usuario=self.staff, motivo="CorrecciÃ³n")
        reconciliar_estado_comision(comision)
        self.registrar_pago_cita(cita, importe="50.00")

        reconciliar_estado_comision(comision)
        comision.refresh_from_db()

        self.assertEqual(comision.base_calculo, Decimal("450.00"))
        self.assertEqual(comision.monto_calculado, Decimal("31.50"))

    def test_suspension_es_idempotente(self):
        comision, _, pago = self.preparar_comision()
        anular_movimiento_economico(movimiento=pago, usuario=self.staff, motivo="CorrecciÃ³n")

        for _ in range(3):
            reconciliar_estado_comision(comision)

        self.assertEqual(
            self.contar_eventos(EventoCaptacion.ACCION_COMISION_SUSPENDIDA),
            1,
        )

    def test_reactivacion_es_idempotente(self):
        comision, cita, pago = self.preparar_comision()
        anular_movimiento_economico(movimiento=pago, usuario=self.staff, motivo="CorrecciÃ³n")
        reconciliar_estado_comision(comision)
        self.registrar_pago_cita(cita, importe="20.00")

        for _ in range(3):
            reconciliar_estado_comision(comision)

        self.assertEqual(
            self.contar_eventos(EventoCaptacion.ACCION_COMISION_REACTIVADA),
            1,
        )

    def test_cuenta_sin_pago_no_sustituye_dinero_recibido(self):
        comision, cita, pago = self.preparar_comision()
        anular_movimiento_economico(movimiento=pago, usuario=self.staff, motivo="CorrecciÃ³n")

        reconciliar_estado_comision(comision)
        comision.refresh_from_db()

        self.assertIsNotNone(cita.importe_servicio_snapshot)
        self.assertEqual(comision.estado, ComisionCaptacion.ESTADO_SUSPENDIDA)

    def test_adeudo_no_suspende(self):
        comision, _, _ = self.preparar_comision(pago="50.00")

        resultado = reconciliar_estado_comision(comision)

        self.assertEqual(resultado.estado, "sin_cambios")
        self.assertEqual(comision.base_calculo, Decimal("450.00"))

    def test_saldo_a_favor_no_modifica(self):
        comision, _, _ = self.preparar_comision(pago="450.00")

        reconciliar_estado_comision(comision)
        comision.refresh_from_db()

        self.assertEqual(comision.base_calculo, Decimal("450.00"))
        self.assertEqual(comision.monto_calculado, Decimal("31.50"))

    def test_penalizacion_no_modifica(self):
        comision, cita, _ = self.preparar_comision(
            pago="625.00",
            servicio="450.00",
        )
        reconciliar_estado_comision(comision)
        comision.refresh_from_db()

        self.assertEqual(comision.base_calculo, Decimal("450.00"))
        self.assertEqual(comision.monto_calculado, Decimal("31.50"))

    def test_reactivacion_no_crea_nueva_comision(self):
        comision, cita, pago = self.preparar_comision()
        cantidad_original = ComisionCaptacion.objects.count()
        anular_movimiento_economico(movimiento=pago, usuario=self.staff, motivo="CorrecciÃ³n")
        reconciliar_estado_comision(comision)
        self.registrar_pago_cita(cita, importe="20.00")

        reconciliar_estado_comision(comision)

        self.assertEqual(ComisionCaptacion.objects.count(), cantidad_original)
        self.assertTrue(ComisionCaptacion.objects.filter(pk=comision.pk).exists())

    def test_reconciliacion_no_modifica_finanzas(self):
        comision, cita, pago = self.preparar_comision()
        cita.refresh_from_db()
        estado_original = (
            MovimientoEconomicoCita.objects.count(),
            pago.estado,
            pago.importe,
            cita.importe_servicio_snapshot,
        )

        reconciliar_estado_comision(comision)
        pago.refresh_from_db()
        cita.refresh_from_db()

        self.assertEqual(
            (
                MovimientoEconomicoCita.objects.count(),
                pago.estado,
                pago.importe,
                cita.importe_servicio_snapshot,
            ),
            estado_original,
        )

    def test_reconciliacion_no_modifica_nomina(self):
        comision, _, _ = self.preparar_comision()
        estado_original = (
            LineaNomina.objects.count(),
            CorteSemanal.objects.count(),
        )

        reconciliar_estado_comision(comision)

        self.assertEqual(
            (
                LineaNomina.objects.count(),
                CorteSemanal.objects.count(),
            ),
            estado_original,
        )

    def test_reconciliador_general_y_comando(self):
        comision, _, pago = self.preparar_comision()
        anular_movimiento_economico(movimiento=pago, usuario=self.staff, motivo="CorrecciÃ³n")

        resumen = reconciliar_comisiones_generadas(comision_id=comision.pk)
        salida = StringIO()
        call_command(
            "reconciliar_estado_comisiones",
            comision_id=comision.pk,
            stdout=salida,
        )

        self.assertEqual(resumen.conteos["suspendida"], 1)
        self.assertIn("Evaluadas: 1", salida.getvalue())
        self.assertIn("Sin cambios: 1", salida.getvalue())
        self.assertIn("Errores: 0", salida.getvalue())
