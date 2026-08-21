import uuid
from datetime import date, datetime, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Cita, DireccionComercial, MovimientoEconomicoCita
from .services import (
    anular_movimiento_economico,
    registrar_movimiento_economico,
)
from .tests_helpers import ClinicaTestDataMixin


class ReportesFinancierosFormalesTests(ClinicaTestDataMixin, TestCase):
    fecha_financiera = date(2026, 8, 20)

    def setUp(self):
        self.client.force_login(self.staff)

    def registrar(self, cita, importe, *, fecha=None, hora=time(10, 0)):
        movimiento, _ = registrar_movimiento_economico(
            cita=cita,
            importe=Decimal(importe),
            metodo="Efectivo",
            referencia="",
            usuario=self.staff,
            clave_idempotencia=uuid.uuid4(),
        )
        instante = timezone.make_aware(
            datetime.combine(fecha or self.fecha_financiera, hora),
            timezone.get_current_timezone(),
        )
        MovimientoEconomicoCita.objects.filter(pk=movimiento.pk).update(
            registrado_en=instante,
        )
        movimiento.refresh_from_db()
        return movimiento

    def reporte_general(self, fecha=None):
        fecha = fecha or self.fecha_financiera
        return self.client.get(
            reverse("reporte_general"),
            {
                "fecha_inicio": fecha.isoformat(),
                "fecha_fin": fecha.isoformat(),
            },
        )

    def test_pago_parcial_y_dos_abonos_suman_solo_dinero_recibido(self):
        cita = self.crear_cita(
            fecha=self.fecha_financiera,
            costo=Decimal("500.00"),
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )
        self.registrar(cita, "100.00", hora=time(10, 0))
        self.registrar(cita, "150.00", hora=time(14, 0))

        respuesta = self.reporte_general()

        self.assertEqual(respuesta.context["monto_total"], Decimal("250.00"))
        self.assertEqual(
            respuesta.context["importe_citas_atendidas"],
            Decimal("500.00"),
        )

    def test_pago_anulado_no_cuenta_como_recibido(self):
        cita = self.crear_cita(
            fecha=self.fecha_financiera,
            costo=Decimal("500.00"),
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )
        movimiento = self.registrar(cita, "100.00")
        anular_movimiento_economico(
            movimiento=movimiento,
            usuario=self.staff,
            motivo="Duplicado",
        )

        self.assertEqual(
            self.reporte_general().context["monto_total"],
            Decimal("0.00"),
        )

    def test_fecha_de_pago_no_fecha_de_cita_define_ingreso(self):
        cita = self.crear_cita(
            fecha=date(2026, 8, 19),
            costo=Decimal("500.00"),
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )
        self.registrar(cita, "100.00", fecha=self.fecha_financiera)

        self.assertEqual(
            self.reporte_general(date(2026, 8, 19)).context["monto_total"],
            Decimal("0.00"),
        )
        self.assertEqual(
            self.reporte_general(self.fecha_financiera).context["monto_total"],
            Decimal("100.00"),
        )

    def test_cambio_cita_costo_no_cambia_ingreso_formal(self):
        cita = self.crear_cita(
            fecha=self.fecha_financiera,
            costo=Decimal("500.00"),
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )
        self.registrar(cita, "100.00")
        cita.costo = Decimal("9999.00")
        cita.save(update_fields=["costo"])

        self.assertEqual(
            self.reporte_general().context["monto_total"],
            Decimal("100.00"),
        )

    def test_snapshot_sin_movimiento_no_es_dinero_recibido(self):
        cita = self.crear_cita(
            fecha=self.fecha_financiera,
            costo=Decimal("500.00"),
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )
        cita.importe_servicio_snapshot = Decimal("600.00")
        cita.save(
            update_fields=["importe_servicio_snapshot"],
        )

        respuesta = self.reporte_general()

        self.assertEqual(respuesta.context["monto_total"], Decimal("0.00"))
        self.assertEqual(
            respuesta.context["importe_citas_atendidas"],
            Decimal("500.00"),
        )

    def test_direccion_comercial_usa_pago_y_conserva_valor_servicios(self):
        usuario = User.objects.create_user(
            username="direccion_reportes",
            password="pruebas",
        )
        perfil = DireccionComercial.objects.create(
            usuario=usuario,
            nombre="Dirección Reportes",
        )
        perfil.divisiones.add(self.division)
        cita = self.crear_cita(
            fecha=self.fecha_financiera,
            costo=Decimal("500.00"),
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )
        self.registrar(cita, "100.00")
        self.client.force_login(usuario)

        respuesta = self.client.get(
            reverse("portal_direccion_comercial"),
            {"mes": "2026-08"},
        )

        self.assertEqual(respuesta.context["ingreso_real"], Decimal("100.00"))
        fila_paciente = next(
            fila
            for fila in respuesta.context["pacientes"]
            if fila["id"] == self.paciente.id
        )
        self.assertEqual(fila_paciente["valor_servicios"], Decimal("500.00"))

    def test_api_conserva_costo_legacy_y_agrega_importe_cita(self):
        cita = self.crear_cita(costo=Decimal("500.00"))

        respuesta = self.client.get(
            reverse("api_reporte_general"),
            {"fecha_inicio": cita.fecha.isoformat()},
        )
        registro = respuesta.json()[0]

        self.assertEqual(registro["costo"], 500.0)
        self.assertEqual(registro["importe_cita"], 500.0)
