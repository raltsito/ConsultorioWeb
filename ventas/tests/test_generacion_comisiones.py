import uuid
from datetime import datetime
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from clinica.models import (
    Cita,
    CorteSemanal,
    LineaNomina,
    Paciente,
    TabuladorGeneral,
)
from clinica.tests_helpers import ClinicaTestDataMixin
from clinica.models import MovimientoEconomicoCita
from clinica.services import (
    anular_movimiento_economico,
    registrar_movimiento_economico,
    registrar_movimiento_recepcion_desde_cita,
)
from ventas.models import (
    Captacion,
    Captador,
    ComisionCaptacion,
    EventoCaptacion,
)
from ventas.services import (
    aprobar_captacion,
    evaluar_y_generar_comision,
    reconciliar_comisiones_pendientes,
    registrar_captacion,
)


class GeneracionComisionMixin(ClinicaTestDataMixin):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.captador = Captador.objects.create(
            tipo=Captador.TIPO_EXTERNO,
            nombre_externo="Captador GeneraciÃ³n",
            tipo_organizacion=Captador.ORG_ESCUELA,
        )

    def crear_captacion(self, paciente=None, aprobar=True, porcentaje=7):
        captacion = registrar_captacion(
            paciente=paciente or self.paciente,
            codigo=self.captador.codigo_activo,
            usuario=self.staff,
        )
        if aprobar:
            captacion = aprobar_captacion(
                captacion=captacion,
                porcentaje=porcentaje,
                usuario=self.staff,
            )
        return captacion

    def crear_cita_asistida(self, paciente=None, **cambios):
        cambios.setdefault("estatus", Cita.ESTATUS_SI_ASISTIO)
        cambios.setdefault("paciente", paciente or self.paciente)
        return self.crear_cita(**cambios)

    def registrar_pago_cita(
        self,
        cita,
        importe="200.00",
        importe_servicio="450.00",
    ):
        cita.precio_servicio_base_snapshot = Decimal(importe_servicio)
        cita.descuento_captacion_porcentaje_snapshot = Decimal("0.00")
        cita.importe_servicio_snapshot = Decimal(importe_servicio)
        cita.save(
            update_fields=[
                "precio_servicio_base_snapshot",
                "descuento_captacion_porcentaje_snapshot",
                "importe_servicio_snapshot",
            ]
        )
        return registrar_movimiento_economico(
            cita=cita,
            importe=Decimal(importe),
            metodo="Efectivo",
            referencia="",
            usuario=self.staff,
            clave_idempotencia=uuid.uuid4(),
        )[0]

    def crear_otro_paciente(self, nombre, telefono):
        return Paciente.objects.create(
            nombre=nombre,
            fecha_nacimiento=self.paciente.fecha_nacimiento,
            sexo=self.paciente.sexo,
            telefono=telefono,
            servicio_inicial=self.servicio,
            division=self.division,
        )


class ElegibilidadYGeneracionTests(GeneracionComisionMixin, TestCase):
    def test_captacion_congela_descuento_25_sin_inferir_dinero(self):
        self.servicio.precio = Decimal("800.00")
        self.servicio.save(update_fields=["precio"])
        self.crear_captacion(porcentaje=7)
        cita = self.crear_cita_asistida(
            costo=Decimal("600.00"),
            metodo_pago="Efectivo",
        )

        movimiento, creado = registrar_movimiento_recepcion_desde_cita(
            cita=cita,
            usuario=self.staff,
        )

        self.assertTrue(creado)
        self.assertEqual(movimiento.importe, Decimal("600.00"))
        cita.refresh_from_db()
        self.assertEqual(
            cita.precio_servicio_base_snapshot,
            Decimal("800.00"),
        )
        self.assertEqual(
            cita.descuento_captacion_porcentaje_snapshot,
            Decimal("25.00"),
        )
        self.assertEqual(
            cita.importe_servicio_snapshot,
            Decimal("600.00"),
        )

    def test_captacion_aprobada_completa_genera_comision(self):
        captacion = self.crear_captacion(porcentaje=7)
        cita = self.crear_cita_asistida(costo=Decimal("400.00"))
        self.registrar_pago_cita(cita)
        resultado = evaluar_y_generar_comision(captacion, usuario=self.staff)
        self.assertEqual(resultado.estado, "generada")
        comision = resultado.comision
        self.assertEqual(comision.cita_generadora, cita)
        self.assertEqual(comision.base_calculo, Decimal("450.00"))
        self.assertEqual(comision.porcentaje_aplicado, 7)
        self.assertEqual(comision.monto_calculado, Decimal("31.50"))
        self.assertEqual(
            comision.estado,
            ComisionCaptacion.ESTADO_PENDIENTE_PAGO,
        )
        self.assertTrue(
            EventoCaptacion.objects.filter(
                captacion=captacion,
                accion=EventoCaptacion.ACCION_COMISION_GENERADA,
            ).exists()
        )

    def test_captacion_pendiente_o_rechazada_no_genera(self):
        pendiente = self.crear_captacion(aprobar=False)
        cita = self.crear_cita_asistida(costo=Decimal("400.00"))
        self.registrar_pago_cita(cita)
        self.assertEqual(
            evaluar_y_generar_comision(pendiente).estado,
            "captacion_no_aprobada",
        )
        pendiente.estado = Captacion.ESTADO_RECHAZADA
        pendiente.save(update_fields=["estado"])
        self.assertEqual(
            evaluar_y_generar_comision(pendiente).estado,
            "captacion_no_aprobada",
        )
        self.assertFalse(ComisionCaptacion.objects.exists())

    def test_sin_cita_asistida_no_genera(self):
        captacion = self.crear_captacion()
        self.crear_cita(estatus=Cita.ESTATUS_CONFIRMADA)
        resultado = evaluar_y_generar_comision(captacion)
        self.assertEqual(resultado.estado, "sin_cita_asistida")

    def test_cancelacion_y_no_show_no_sustituyen_primera_asistencia(self):
        casos = (
            (self.paciente, Cita.ESTATUS_CANCELO),
            (self.otro_paciente, Cita.ESTATUS_NO_ASISTIO),
        )
        for paciente, estatus in casos:
            with self.subTest(estatus=estatus):
                captacion = self.crear_captacion(paciente=paciente)
                self.crear_cita(paciente=paciente, estatus=estatus)
                asistida = self.crear_cita_asistida(
                    paciente=paciente,
                    hora=self.hora.replace(hour=11),
                    costo=Decimal("400.00"),
                )
                self.registrar_pago_cita(asistida)
                resultado = evaluar_y_generar_comision(captacion)
                self.assertEqual(resultado.estado, "generada")
                self.assertEqual(resultado.comision.cita_generadora, asistida)

    def test_segunda_asistencia_con_pago_no_reemplaza_primera_sin_pago(self):
        captacion = self.crear_captacion()
        primera = self.crear_cita_asistida(costo=Decimal("400.00"))
        primera.importe_servicio_snapshot = Decimal("400.00")
        primera.save(
            update_fields=["importe_servicio_snapshot"],
        )
        segunda = self.crear_cita_asistida(
            hora=self.hora.replace(hour=11),
            costo=Decimal("400.00"),
        )
        self.registrar_pago_cita(segunda)
        resultado = evaluar_y_generar_comision(captacion)
        self.assertEqual(resultado.estado, "cita_sin_pago")
        self.assertEqual(resultado.cita, primera)
        self.assertFalse(ComisionCaptacion.objects.exists())

    def test_cuenta_sin_dinero_no_habilita_comision(self):
        captacion = self.crear_captacion()
        cita = self.crear_cita_asistida(costo=Decimal("400.00"))
        cita.importe_servicio_snapshot = Decimal("400.00")
        cita.save(
            update_fields=["importe_servicio_snapshot"],
        )
        resultado = evaluar_y_generar_comision(captacion)
        self.assertEqual(resultado.estado, "cita_sin_pago")

    def test_pago_parcial_usa_servicio_completo_como_base(self):
        captacion = self.crear_captacion()
        cita = self.crear_cita_asistida(costo=Decimal("400.00"))
        self.registrar_pago_cita(cita, importe="100.00")
        comision = evaluar_y_generar_comision(captacion).comision
        self.assertEqual(comision.base_calculo, Decimal("450.00"))
        self.assertEqual(comision.monto_calculado, Decimal("31.50"))

    def test_saldo_favor_y_penalizacion_no_cambian_base(self):
        casos = (
            (self.paciente, "450.00", "450.00", "400.00"),
            (self.otro_paciente, "625.00", "450.00", "625.00"),
        )
        for paciente, pago, servicio, total in casos:
            with self.subTest(movimiento=pago, total=total):
                captacion = self.crear_captacion(paciente=paciente)
                cita = self.crear_cita_asistida(
                    paciente=paciente,
                    costo=Decimal(total),
                )
                self.registrar_pago_cita(
                    cita,
                    importe=pago,
                    importe_servicio=servicio,
                )
                comision = evaluar_y_generar_comision(captacion).comision
                self.assertEqual(comision.base_calculo, Decimal("450.00"))

    def test_pago_anulado_no_cuenta_y_otro_vigente_si(self):
        captacion = self.crear_captacion()
        cita = self.crear_cita_asistida(costo=Decimal("400.00"))
        pago = self.registrar_pago_cita(cita)
        anular_movimiento_economico(movimiento=pago, usuario=self.staff, motivo="Prueba")
        self.assertEqual(
            evaluar_y_generar_comision(captacion).estado,
            "cita_sin_pago",
        )
        self.registrar_pago_cita(cita, importe="100.00")
        self.assertEqual(
            evaluar_y_generar_comision(captacion).estado,
            "generada",
        )

    def test_snapshot_null_no_utiliza_fallback(self):
        captacion = self.crear_captacion()
        cita = self.crear_cita_asistida(costo=Decimal("625.00"))
        MovimientoEconomicoCita.objects.create(
            cita=cita,
            importe=Decimal("625.00"),
            metodo="Efectivo",
            registrado_por=self.staff,
        )
        resultado = evaluar_y_generar_comision(captacion)
        self.assertEqual(resultado.estado, "sin_importe_servicio")
        self.assertFalse(ComisionCaptacion.objects.exists())

    def test_movimiento_sin_snapshot_reporta_sin_importe_servicio(self):
        captacion = self.crear_captacion()
        cita = self.crear_cita_asistida(costo=Decimal("400.00"))
        MovimientoEconomicoCita.objects.create(
            cita=cita,
            importe=Decimal("100.00"),
            metodo="Efectivo",
            registrado_por=self.staff,
        )
        resultado = evaluar_y_generar_comision(captacion)
        self.assertEqual(resultado.estado, "sin_importe_servicio")
        self.assertFalse(ComisionCaptacion.objects.exists())

    def test_idempotencia_conserva_snapshots(self):
        captacion = self.crear_captacion()
        cita = self.crear_cita_asistida(costo=Decimal("400.00"))
        self.registrar_pago_cita(cita)
        primera = evaluar_y_generar_comision(captacion).comision
        valores = (
            primera.pk,
            primera.cita_generadora_id,
            primera.base_calculo,
            primera.porcentaje_aplicado,
            primera.monto_calculado,
        )
        segunda = evaluar_y_generar_comision(captacion)
        self.assertEqual(segunda.estado, "ya_existia")
        segunda.comision.refresh_from_db()
        self.assertEqual(
            (
                segunda.comision.pk,
                segunda.comision.cita_generadora_id,
                segunda.comision.base_calculo,
                segunda.comision.porcentaje_aplicado,
                segunda.comision.monto_calculado,
            ),
            valores,
        )
        self.assertEqual(ComisionCaptacion.objects.count(), 1)
    def test_dos_citas_con_pago_generan_solo_por_primera(self):
        captacion = self.crear_captacion()
        primera = self.crear_cita_asistida(costo=Decimal("400.00"))
        segunda = self.crear_cita_asistida(
            hora=self.hora.replace(hour=11),
            costo=Decimal("400.00"),
        )
        self.registrar_pago_cita(primera)
        self.registrar_pago_cita(segunda)
        reconciliar_comisiones_pendientes()
        reconciliar_comisiones_pendientes()
        self.assertEqual(ComisionCaptacion.objects.count(), 1)
        self.assertEqual(
            ComisionCaptacion.objects.get().cita_generadora,
            primera,
        )

    def test_anulacion_posterior_no_modifica_comision_en_fase_5a(self):
        captacion = self.crear_captacion()
        cita = self.crear_cita_asistida(costo=Decimal("400.00"))
        pago = self.registrar_pago_cita(cita)
        comision = evaluar_y_generar_comision(captacion).comision
        valores = (comision.base_calculo, comision.monto_calculado, comision.estado)
        anular_movimiento_economico(movimiento=pago, usuario=self.staff, motivo="Posterior")
        resultado = evaluar_y_generar_comision(captacion)
        resultado.comision.refresh_from_db()
        self.assertEqual(resultado.estado, "ya_existia")
        self.assertEqual(
            (
                resultado.comision.base_calculo,
                resultado.comision.monto_calculado,
                resultado.comision.estado,
            ),
            valores,
        )

    def test_asistencia_previa_incompatible_reporta_datos_inconsistentes(self):
        captacion = self.crear_captacion()
        cita = self.crear_cita_asistida(costo=Decimal("400.00"))
        self.registrar_pago_cita(cita)
        fecha_posterior = timezone.make_aware(datetime(2031, 1, 1, 12, 0))
        Captacion.objects.filter(pk=captacion.pk).update(
            fecha_captacion=fecha_posterior
        )
        captacion.refresh_from_db()
        resultado = evaluar_y_generar_comision(captacion)
        self.assertEqual(resultado.estado, "datos_inconsistentes")
        self.assertFalse(ComisionCaptacion.objects.exists())

    def test_pareja_con_principal_captado_genera_una_comision(self):
        principal = self.crear_captacion(
            paciente=self.paciente,
            porcentaje=8,
        )
        cita = self.crear_cita_asistida(costo=Decimal("600.00"))
        cita.pacientes_adicionales.add(self.otro_paciente)
        self.registrar_pago_cita(
            cita,
            importe="200.00",
            importe_servicio="450.00",
        )
        resultado_principal = evaluar_y_generar_comision(principal)

        self.assertEqual(resultado_principal.estado, "generada")
        self.assertEqual(ComisionCaptacion.objects.count(), 1)
        self.assertEqual(
            resultado_principal.comision.base_calculo,
            Decimal("450.00"),
        )
        self.assertEqual(resultado_principal.comision.porcentaje_aplicado, 8)
        self.assertEqual(
            resultado_principal.comision.monto_calculado,
            Decimal("36.00"),
        )

    def test_adicional_con_captacion_no_genera_segunda_comision(self):
        principal = self.crear_captacion(paciente=self.paciente, porcentaje=8)
        adicional = self.crear_captacion(paciente=self.otro_paciente)
        cita = self.crear_cita_asistida(costo=Decimal("600.00"))
        cita.pacientes_adicionales.add(self.otro_paciente)
        self.registrar_pago_cita(
            cita,
            importe="200.00",
            importe_servicio="450.00",
        )

        resultado_principal = evaluar_y_generar_comision(principal)
        resultado_adicional = evaluar_y_generar_comision(adicional)

        self.assertEqual(resultado_principal.estado, "generada")
        self.assertEqual(resultado_adicional.estado, "sin_cita_asistida")
        self.assertEqual(ComisionCaptacion.objects.count(), 1)
    def test_varios_adicionales_mantienen_una_comision_maxima(self):
        principal = self.crear_captacion(paciente=self.paciente, porcentaje=8)
        ana = self.crear_otro_paciente("Ana Adicional", "5550000003")
        luis = self.crear_otro_paciente("Luis Adicional", "5550000004")
        cita = self.crear_cita_asistida(costo=Decimal("600.00"))
        cita.pacientes_adicionales.add(self.otro_paciente, ana, luis)
        self.registrar_pago_cita(
            cita,
            importe="200.00",
            importe_servicio="450.00",
        )

        reconciliar_comisiones_pendientes()

        self.assertEqual(ComisionCaptacion.objects.count(), 1)
        self.assertEqual(
            ComisionCaptacion.objects.get().captacion,
            principal,
        )

    def test_precio_familiar_no_se_multiplica_por_integrantes(self):
        captacion = self.crear_captacion(porcentaje=8)
        ana = self.crear_otro_paciente("Ana Familiar", "5550000005")
        luis = self.crear_otro_paciente("Luis Familiar", "5550000006")
        cita = self.crear_cita_asistida(costo=Decimal("600.00"))
        cita.pacientes_adicionales.add(self.otro_paciente, ana, luis)
        self.registrar_pago_cita(
            cita,
            importe="200.00",
            importe_servicio="450.00",
        )

        comision = evaluar_y_generar_comision(captacion).comision

        self.assertEqual(comision.base_calculo, Decimal("450.00"))
        self.assertNotEqual(comision.base_calculo, Decimal("2400.00"))

    def test_comision_familiar_no_se_multiplica_por_integrantes(self):
        captacion = self.crear_captacion(porcentaje=8)
        ana = self.crear_otro_paciente("Ana Pareja", "5550000007")
        luis = self.crear_otro_paciente("Luis Pareja", "5550000008")
        cita = self.crear_cita_asistida(costo=Decimal("600.00"))
        cita.pacientes_adicionales.add(self.otro_paciente, ana, luis)
        self.registrar_pago_cita(
            cita,
            importe="200.00",
            importe_servicio="450.00",
        )

        comision = evaluar_y_generar_comision(captacion).comision

        self.assertEqual(comision.monto_calculado, Decimal("36.00"))
        self.assertNotEqual(comision.monto_calculado, Decimal("192.00"))

    def test_adicional_captado_sin_principal_captado_no_genera(self):
        adicional = self.crear_captacion(paciente=self.otro_paciente)
        cita = self.crear_cita_asistida(costo=Decimal("600.00"))
        cita.pacientes_adicionales.add(self.otro_paciente)
        self.registrar_pago_cita(
            cita,
            importe="200.00",
            importe_servicio="600.00",
        )

        resultado = evaluar_y_generar_comision(adicional)

        self.assertEqual(resultado.estado, "sin_cita_asistida")
        self.assertFalse(ComisionCaptacion.objects.exists())


class NoIntegracionYComandoTests(GeneracionComisionMixin, TestCase):
    def test_reconciliador_continua_despues_de_error_aislado(self):
        primera = self.crear_captacion(paciente=self.paciente)
        self.crear_captacion(paciente=self.otro_paciente)
        evaluador_real = evaluar_y_generar_comision

        def evaluador_controlado(captacion, *, usuario=None):
            if captacion.pk == primera.pk:
                raise RuntimeError("Fallo aislado de prueba")
            return evaluador_real(captacion, usuario=usuario)

        with patch(
            "ventas.services.evaluar_y_generar_comision",
            side_effect=evaluador_controlado,
        ):
            resumen = reconciliar_comisiones_pendientes()

        self.assertEqual(resumen.evaluadas, 2)
        self.assertEqual(resumen.conteos["error"], 1)
        self.assertEqual(resumen.conteos["sin_cita_asistida"], 1)

    def test_generar_no_modifica_finanzas_ni_nomina(self):
        captacion = self.crear_captacion()
        cita = self.crear_cita_asistida(costo=Decimal("400.00"))
        pago = self.registrar_pago_cita(cita)
        estado_financiero = (
            MovimientoEconomicoCita.objects.count(),
            pago.importe,
            cita.importe_servicio_snapshot,
        )
        estado_nomina = (
            LineaNomina.objects.count(),
            CorteSemanal.objects.count(),
            TabuladorGeneral.objects.count(),
        )
        evaluar_y_generar_comision(captacion)
        pago.refresh_from_db()
        cita.refresh_from_db()
        self.assertEqual(
            (
                MovimientoEconomicoCita.objects.count(),
                pago.importe,
                cita.importe_servicio_snapshot,
            ),
            estado_financiero,
        )
        self.assertEqual(
            (
                LineaNomina.objects.count(),
                CorteSemanal.objects.count(),
                TabuladorGeneral.objects.count(),
            ),
            estado_nomina,
        )

    def test_comando_reconcilia_y_muestra_resumen(self):
        captacion = self.crear_captacion()
        cita = self.crear_cita_asistida(costo=Decimal("400.00"))
        self.registrar_pago_cita(cita)
        salida = StringIO()
        call_command(
            "reconciliar_comisiones_captacion",
            captacion_id=captacion.pk,
            stdout=salida,
        )
        self.assertIn("Evaluadas: 1", salida.getvalue())
        self.assertIn("Generadas: 1", salida.getvalue())
        self.assertIn("Errores: 0", salida.getvalue())
        self.assertEqual(ComisionCaptacion.objects.count(), 1)
