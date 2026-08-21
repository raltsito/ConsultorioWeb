from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import (
    BonoExtra,
    Cita,
    CorteSemanal,
    LineaNomina,
    ReglaTerapeuta,
    ReporteIncidente,
)
from .services import (
    _resolver_monto_sesion,
    aprobar_corte_semanal,
    calcular_nomina_semanal,
)
from .tests_helpers import ClinicaTestDataMixin


class PrioridadHonorarioTests(ClinicaTestDataMixin, TestCase):
    def test_pareja_tiene_prioridad_sobre_individual_y_tarifa_plana(self):
        regla = self.crear_regla(
            pago_por_sesion=Decimal("200.00"),
            pago_individual=Decimal("250.00"),
            pago_pareja=Decimal("350.00"),
        )
        cita = self.crear_cita()
        cita.pacientes_adicionales.add(self.otro_paciente)
        monto, concepto = _resolver_monto_sesion(cita, regla)
        self.assertEqual(monto, Decimal("350.00"))
        self.assertIn("pareja", concepto.lower())

    def test_individual_tiene_prioridad_sobre_pago_por_sesion(self):
        regla = self.crear_regla(
            pago_por_sesion=Decimal("200.00"), pago_individual=Decimal("275.00")
        )
        monto, _ = _resolver_monto_sesion(self.crear_cita(), regla)
        self.assertEqual(monto, Decimal("275.00"))

    def test_pago_por_sesion_se_usa_si_no_hay_modalidad(self):
        regla = self.crear_regla(pago_por_sesion=Decimal("225.00"))
        monto, _ = _resolver_monto_sesion(self.crear_cita(), regla)
        self.assertEqual(monto, Decimal("225.00"))

    def test_tabulador_general_es_fallback_dentro_de_regla(self):
        tabulador = self.crear_tabulador(pago_base=Decimal("190.00"))
        regla = self.crear_regla(pago_por_sesion=None, tabulador_base=tabulador)
        monto, _ = _resolver_monto_sesion(self.crear_cita(), regla)
        self.assertEqual(monto, Decimal("190.00"))

    def test_sin_valor_configurado_resuelve_cero(self):
        regla = self.crear_regla(pago_por_sesion=None)
        monto, concepto = _resolver_monto_sesion(self.crear_cita(), regla)
        self.assertEqual(monto, Decimal("0.00"))
        self.assertIn("sin tarifa", concepto)

    def test_tabulador_existente_sin_regla_no_permite_calcular(self):
        self.crear_tabulador()
        self.crear_cita(estatus=Cita.ESTATUS_SI_ASISTIO)
        with self.assertRaisesMessage(ValueError, "no tiene una ReglaTerapeuta"):
            calcular_nomina_semanal(self.terapeuta, self.fecha, self.fecha)

    def test_honorario_no_depende_de_costo_de_cita_ni_precio_de_servicio(self):
        self.crear_regla(pago_por_sesion=Decimal("230.00"))
        cita = self.crear_cita(
            costo=Decimal("1.00"), estatus=Cita.ESTATUS_SI_ASISTIO
        )
        self.servicio.precio = Decimal("9999.00")
        self.servicio.save(update_fields=["precio"])
        corte = calcular_nomina_semanal(self.terapeuta, self.fecha, self.fecha)
        self.assertEqual(corte.subtotal_sesiones, Decimal("230.00"))
        self.assertEqual(corte.lineas.get(tipo=LineaNomina.TIPO_SESION).cita, cita)


class SesionesYBonosNominaTests(ClinicaTestDataMixin, TestCase):
    def test_solo_asistencias_generan_pago_ordinario(self):
        self.crear_regla(pago_por_sesion=Decimal("200.00"))
        self.crear_cita(estatus=Cita.ESTATUS_SI_ASISTIO)
        self.crear_cita(
            paciente=self.otro_paciente,
            fecha=date(2030, 1, 8),
            estatus=Cita.ESTATUS_CANCELO,
        )
        self.crear_cita(
            paciente=self.otro_paciente,
            fecha=date(2030, 1, 9),
            estatus=Cita.ESTATUS_NO_ASISTIO,
        )
        corte = calcular_nomina_semanal(
            self.terapeuta, date(2030, 1, 7), date(2030, 1, 13)
        )
        self.assertEqual(corte.total_sesiones, 1)
        self.assertEqual(corte.subtotal_sesiones, Decimal("200.00"))
        self.assertEqual(corte.lineas.filter(tipo=LineaNomina.TIPO_SESION).count(), 1)

    def test_sin_bono_recibe_base_pero_no_cuenta_para_umbral(self):
        self.crear_regla(
            pago_por_sesion=Decimal("200.00"),
            bono_umbral_monto=Decimal("100.00"),
            bono_umbral_pacientes=2,
        )
        self.crear_cita(estatus=Cita.ESTATUS_SI_ASISTIO)
        self.crear_cita(
            paciente=self.otro_paciente,
            fecha=date(2030, 1, 8),
            estatus=Cita.ESTATUS_SI_ASISTIO,
            sin_bono=True,
        )
        corte = calcular_nomina_semanal(
            self.terapeuta, date(2030, 1, 7), date(2030, 1, 13)
        )
        self.assertEqual(corte.total_sesiones, 2)
        self.assertEqual(corte.subtotal_sesiones, Decimal("400.00"))
        self.assertEqual(corte.total_bonos, Decimal("0.00"))

    def test_bono_umbral_individual_es_repetible(self):
        self.crear_regla(
            pago_por_sesion=Decimal("100.00"),
            bono_umbral_monto=Decimal("75.00"),
            bono_umbral_pacientes=2,
        )
        for indice in range(4):
            self.crear_cita(
                paciente=self.paciente if indice % 2 == 0 else self.otro_paciente,
                fecha=date(2030, 1, 7 + indice),
                estatus=Cita.ESTATUS_SI_ASISTIO,
            )
        corte = calcular_nomina_semanal(
            self.terapeuta, date(2030, 1, 7), date(2030, 1, 13)
        )
        self.assertEqual(corte.total_bonos, Decimal("150.00"))

    def test_bono_por_paciente_actualmente_cuenta_sesiones(self):
        self.crear_regla(
            pago_por_sesion=Decimal("100.00"), bono_por_paciente=Decimal("25.00")
        )
        self.crear_cita(estatus=Cita.ESTATUS_SI_ASISTIO)
        self.crear_cita(
            fecha=date(2030, 1, 8), estatus=Cita.ESTATUS_SI_ASISTIO
        )
        corte = calcular_nomina_semanal(
            self.terapeuta, date(2030, 1, 7), date(2030, 1, 13)
        )
        self.assertEqual(corte.total_bonos, Decimal("50.00"))

    def test_bono_de_tabulador_es_fallback(self):
        tabulador = self.crear_tabulador(
            pago_base=Decimal("100.00"),
            bono_monto=Decimal("80.00"),
            bono_umbral_pacientes=2,
        )
        self.crear_regla(pago_por_sesion=None, tabulador_base=tabulador)
        self.crear_cita(estatus=Cita.ESTATUS_SI_ASISTIO)
        self.crear_cita(
            paciente=self.otro_paciente,
            fecha=date(2030, 1, 8),
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )
        corte = calcular_nomina_semanal(
            self.terapeuta, date(2030, 1, 7), date(2030, 1, 13)
        )
        self.assertEqual(corte.total_bonos, Decimal("80.00"))


class RecalculoNominaTests(ClinicaTestDataMixin, TestCase):
    def setUp(self):
        self.regla = self.crear_regla(pago_por_sesion=Decimal("200.00"))
        self.cita = self.crear_cita(estatus=Cita.ESTATUS_SI_ASISTIO)
        self.corte = calcular_nomina_semanal(self.terapeuta, self.fecha, self.fecha)

    def test_recalculo_reconstruye_lineas_ordinarias_y_bonos_automaticos(self):
        linea_original = self.corte.lineas.get(tipo=LineaNomina.TIPO_SESION)
        id_original = linea_original.id
        self.regla.pago_por_sesion = Decimal("215.00")
        self.regla.bono_por_paciente = Decimal("10.00")
        self.regla.save(update_fields=["pago_por_sesion", "bono_por_paciente"])

        calcular_nomina_semanal(self.terapeuta, self.fecha, self.fecha)
        self.assertFalse(LineaNomina.objects.filter(id=id_original).exists())
        self.corte.refresh_from_db()
        self.assertEqual(self.corte.subtotal_sesiones, Decimal("215.00"))
        self.assertEqual(self.corte.total_bonos, Decimal("10.00"))

    def test_recalculo_preserva_penalizacion_expositor_y_bono_extra(self):
        penalizacion = LineaNomina.objects.create(
            corte=self.corte,
            cita=self.cita,
            tipo=LineaNomina.TIPO_PENALIZACION,
            concepto="Penalización manual de prueba",
            monto=Decimal("40.00"),
        )
        expositor = LineaNomina.objects.create(
            corte=self.corte,
            cita=None,
            tipo=LineaNomina.TIPO_EXPOSITOR,
            concepto="Expositor de prueba",
            monto=Decimal("60.00"),
        )
        BonoExtra.objects.create(
            corte=self.corte,
            concepto="Bono extra de prueba",
            monto=Decimal("30.00"),
            registrado_por=self.staff,
        )
        calcular_nomina_semanal(self.terapeuta, self.fecha, self.fecha)
        self.assertTrue(LineaNomina.objects.filter(id=penalizacion.id).exists())
        self.assertTrue(LineaNomina.objects.filter(id=expositor.id).exists())
        self.corte.refresh_from_db()
        self.assertEqual(self.corte.total_bonos, Decimal("70.00"))
        self.assertEqual(self.corte.total_pago, Decimal("330.00"))


class AprobacionYConfirmacionCorteTests(ClinicaTestDataMixin, TestCase):
    def setUp(self):
        self.crear_regla()
        self.crear_cita(estatus=Cita.ESTATUS_SI_ASISTIO)
        self.corte = calcular_nomina_semanal(self.terapeuta, self.fecha, self.fecha)

    def test_aprobar_sella_corte_e_impide_recalculo(self):
        aprobar_corte_semanal(self.corte, self.staff)
        self.corte.refresh_from_db()
        self.assertEqual(self.corte.estatus, CorteSemanal.ESTATUS_APROBADO)
        self.assertEqual(self.corte.aprobado_por, self.staff)
        self.assertIsNotNone(self.corte.aprobado_en)
        with self.assertRaisesMessage(ValueError, "no puede recalcularse"):
            calcular_nomina_semanal(self.terapeuta, self.fecha, self.fecha)

    def test_terapeuta_confirma_corte(self):
        self.client.force_login(self.usuario_terapeuta)
        response = self.client.post(
            reverse("confirmar_nomina_terapeuta", args=[self.corte.id]),
            {"accion": "confirmo"},
        )
        self.assertEqual(response.status_code, 302)
        self.corte.refresh_from_db()
        self.assertEqual(
            self.corte.confirmacion_terapeuta,
            CorteSemanal.CONFIRMACION_ACEPTADO,
        )

    def test_terapeuta_reporta_incidencia_de_corte(self):
        self.client.force_login(self.usuario_terapeuta)
        self.client.post(
            reverse("confirmar_nomina_terapeuta", args=[self.corte.id]),
            {"accion": "algo_mal", "descripcion": "Monto incorrecto de prueba"},
        )
        self.corte.refresh_from_db()
        self.assertEqual(
            self.corte.confirmacion_terapeuta,
            CorteSemanal.CONFIRMACION_INCIDENCIA,
        )
        self.assertTrue(
            ReporteIncidente.objects.filter(terapeuta=self.terapeuta).exists()
        )
