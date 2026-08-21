import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Cita, LineaNomina, MovimientoEconomicoCita
from .services import (
    calcular_nomina_semanal,
    registrar_movimiento_economico,
)
from .tests_helpers import ClinicaTestDataMixin


class CitasTardiasTests(ClinicaTestDataMixin, TestCase):
    def setUp(self):
        self.ayer = date.today() - timedelta(days=1)
        self.client.force_login(self.staff)

    def test_cierre_tardio_asistido_marca_sin_bono_y_no_crea_movimiento(self):
        self.crear_regla(
            pago_por_sesion=Decimal("210.00"),
            bono_umbral_monto=Decimal("100.00"),
            bono_umbral_pacientes=1,
        )
        cita = self.crear_cita(
            fecha=self.ayer,
            estatus=Cita.ESTATUS_CONFIRMADA,
            sin_bono=False,
            metodo_pago="Efectivo",
        )
        response = self.client.post(
            reverse("citas_tardias"),
            {"cita_id": cita.id, "estatus": Cita.ESTATUS_SI_ASISTIO},
        )
        self.assertEqual(response.status_code, 302)
        cita.refresh_from_db()
        self.assertEqual(cita.estatus, Cita.ESTATUS_SI_ASISTIO)
        self.assertTrue(cita.sin_bono)
        self.assertFalse(
            MovimientoEconomicoCita.objects.filter(cita=cita).exists()
        )

        corte = calcular_nomina_semanal(self.terapeuta, self.ayer, self.ayer)
        self.assertEqual(corte.subtotal_sesiones, Decimal("210.00"))
        self.assertEqual(corte.total_bonos, Decimal("0.00"))
        self.assertEqual(corte.lineas.filter(tipo=LineaNomina.TIPO_SESION).count(), 1)

    def test_citas_tardias_admite_estados_operativos_actuales(self):
        for indice, estatus in enumerate((
            Cita.ESTATUS_NO_ASISTIO,
            Cita.ESTATUS_CANCELO,
            Cita.ESTATUS_INCIDENCIA,
        )):
            with self.subTest(estatus=estatus):
                cita = self.crear_cita(
                    paciente=self.paciente if indice % 2 == 0 else self.otro_paciente,
                    fecha=self.ayer - timedelta(days=indice),
                    estatus=Cita.ESTATUS_CONFIRMADA,
                )
                self.client.post(
                    reverse("citas_tardias"),
                    {"cita_id": cita.id, "estatus": estatus},
                )
                cita.refresh_from_db()
                self.assertEqual(cita.estatus, estatus)
                self.assertTrue(cita.sin_bono)


class ReportesFinancierosCaracterizacionTests(ClinicaTestDataMixin, TestCase):
    def setUp(self):
        self.client.force_login(self.staff)

    def registrar_pago_en_fecha(self, cita, importe):
        movimiento, _ = registrar_movimiento_economico(
            cita=cita,
            importe=Decimal(importe),
            metodo="Efectivo",
            referencia="",
            usuario=self.staff,
            clave_idempotencia=uuid.uuid4(),
        )
        confirmado_en = timezone.make_aware(
            datetime.combine(self.fecha, time(12, 0)),
            timezone.get_current_timezone(),
        )
        MovimientoEconomicoCita.objects.filter(pk=movimiento.pk).update(
            registrado_en=confirmado_en,
        )
        return movimiento

    def test_bitacora_suma_pago_confirmado_no_costo_de_asistencias(self):
        cita = self.crear_cita(
            costo=Decimal("510.00"),
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )
        self.registrar_pago_en_fecha(cita, "100.00")
        self.crear_cita(
            paciente=self.otro_paciente,
            costo=Decimal("900.00"),
            estatus=Cita.ESTATUS_CANCELO,
        )
        response = self.client.get(
            reverse("bitacora_diaria"), {"fecha": self.fecha.isoformat()}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["monto_dia"], Decimal("100.00"))
        self.assertEqual(response.context["asistieron"], 1)

    def test_reporte_general_separa_pago_de_importe_citas(self):
        cita = self.crear_cita(
            costo=Decimal("430.00"),
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )
        self.registrar_pago_en_fecha(cita, "100.00")
        self.crear_cita(
            paciente=self.otro_paciente,
            costo=Decimal("870.00"),
            estatus=Cita.ESTATUS_NO_ASISTIO,
        )
        response = self.client.get(
            reverse("reporte_general"),
            {"fecha_inicio": self.fecha.isoformat(), "fecha_fin": self.fecha.isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total"], 2)
        self.assertEqual(response.context["asistieron"], 1)
        self.assertEqual(response.context["monto_total"], Decimal("100.00"))
        self.assertEqual(
            response.context["importe_citas_atendidas"],
            Decimal("430.00"),
        )

    def test_panel_nomina_reporta_valor_citas_sin_cambiar_calculo(self):
        self.crear_regla()
        self.crear_cita(costo=Decimal("615.00"), estatus=Cita.ESTATUS_SI_ASISTIO)
        response = self.client.get(
            reverse("nomina_lista"),
            {"fecha_inicio": self.fecha.isoformat(), "fecha_fin": self.fecha.isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["filas"]), 1)
        self.assertEqual(
            response.context["filas"][0]["valor_citas_atendidas"],
            Decimal("615.00"),
        )
        self.assertEqual(response.context["total_clinica_global"], Decimal("615.00"))
