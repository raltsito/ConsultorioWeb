from datetime import date, datetime, time
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Cita, MovimientoEconomicoCita
from .services import (
    anular_movimiento_economico,
    registrar_movimiento_economico,
    registrar_movimiento_recepcion_desde_cita,
)
from .tests_helpers import ClinicaTestDataMixin


class FlujoRecepcionMovimientoTests(ClinicaTestDataMixin, TestCase):
    def datos_edicion(self, cita):
        return {
            "paciente": cita.paciente_id,
            "fecha": cita.fecha.isoformat(),
            "hora": cita.hora.strftime("%H:%M"),
            "tipo_paciente": cita.tipo_paciente,
            "division": cita.division_id,
            "consultorio": cita.consultorio_id,
            "servicio": cita.servicio_id,
            "terapeuta": cita.terapeuta_id,
            "costo": str(cita.costo),
            "metodo_pago": cita.metodo_pago,
            "estatus": Cita.ESTATUS_SI_ASISTIO,
            "tiene_descuento": "false",
        }

    def test_guardar_dos_veces_no_duplica_movimiento(self):
        cita = self.crear_cita(
            costo=Decimal("200.00"),
            metodo_pago="Efectivo",
            estatus=Cita.ESTATUS_CONFIRMADA,
        )
        self.client.force_login(self.staff)
        datos = self.datos_edicion(cita)

        primera_respuesta = self.client.post(
            reverse("editar_cita", args=[cita.id]),
            datos,
        )
        segunda_respuesta = self.client.post(
            reverse("editar_cita", args=[cita.id]),
            datos,
        )

        self.assertEqual(primera_respuesta.status_code, 302)
        self.assertEqual(segunda_respuesta.status_code, 302)
        self.assertEqual(
            MovimientoEconomicoCita.objects.filter(cita=cita).count(),
            1,
        )

    def test_bloqueo_de_cita_no_incluye_select_related_nullable(self):
        cita = self.crear_cita(
            costo=Decimal("450.00"),
            metodo_pago="Efectivo",
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )

        with patch.object(Cita.objects, "select_for_update") as bloquear:
            queryset_bloqueado = bloquear.return_value
            queryset_bloqueado.get.return_value = cita

            movimiento, creado = registrar_movimiento_recepcion_desde_cita(
                cita=cita,
                usuario=self.staff,
            )

        bloquear.assert_called_once_with()
        queryset_bloqueado.get.assert_called_once_with(pk=cita.pk)
        queryset_bloqueado.select_related.assert_not_called()
        self.assertTrue(creado)
        self.assertEqual(movimiento.importe, Decimal("450.00"))
        self.assertEqual(movimiento.metodo, "Efectivo")

    def test_checkout_no_crea_movimiento(self):
        cita = self.crear_cita(
            costo=Decimal("200.00"),
            metodo_pago="Efectivo",
            estatus=Cita.ESTATUS_CONFIRMADA,
        )
        self.client.force_login(self.usuario_terapeuta)

        respuesta = self.client.post(
            reverse("checkout_cita", args=[cita.id]),
            {
                "estatus": Cita.ESTATUS_SI_ASISTIO,
                "costo": "200.00",
                "metodo_pago": "Efectivo",
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(
            MovimientoEconomicoCita.objects.filter(cita=cita).exists()
        )


class BitacoraMovimientosTests(ClinicaTestDataMixin, TestCase):
    def setUp(self):
        self.client.force_login(self.staff)

    def test_columna_pago_muestra_movimiento_y_no_precio_servicio(self):
        self.servicio.precio = Decimal("850.00")
        self.servicio.save(update_fields=["precio"])
        cita = self.crear_cita(
            costo=Decimal("200.00"),
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )
        registrar_movimiento_economico(
            cita=cita,
            importe=Decimal("200.00"),
            metodo="Efectivo",
            usuario=self.staff,
        )

        respuesta = self.client.get(
            reverse("bitacora_diaria"),
            {"fecha": cita.fecha.isoformat()},
        )

        self.assertContains(respuesta, "$200,00 recibido")
        self.assertNotContains(respuesta, "$850,00 recibido")

    def test_cita_sin_movimiento_no_inventa_pago(self):
        cita = self.crear_cita(
            costo=Decimal("200.00"),
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )

        respuesta = self.client.get(
            reverse("bitacora_diaria"),
            {"fecha": cita.fecha.isoformat()},
        )

        self.assertContains(respuesta, "Sin movimiento registrado")
        self.assertNotContains(respuesta, "$200,00 recibido")

    def test_tarjeta_suma_confirmados_por_fecha_y_excluye_anulados(self):
        fecha_consulta = date(2030, 1, 7)
        cita_confirmada = self.crear_cita(
            fecha=fecha_consulta,
            costo=Decimal("200.00"),
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )
        cita_anulada = self.crear_cita(
            paciente=self.otro_paciente,
            fecha=fecha_consulta,
            hora=time(11, 0),
            costo=Decimal("850.00"),
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )
        movimiento_confirmado, _ = registrar_movimiento_economico(
            cita=cita_confirmada,
            importe=Decimal("200.00"),
            metodo="Efectivo",
            usuario=self.staff,
        )
        movimiento_anulado, _ = registrar_movimiento_economico(
            cita=cita_anulada,
            importe=Decimal("850.00"),
            metodo="Efectivo",
            usuario=self.staff,
        )
        instante = timezone.make_aware(
            datetime.combine(fecha_consulta, time(12, 0)),
            timezone.get_current_timezone(),
        )
        MovimientoEconomicoCita.objects.filter(
            pk__in=(movimiento_confirmado.pk, movimiento_anulado.pk),
        ).update(registrado_en=instante)
        movimiento_anulado.refresh_from_db()
        anular_movimiento_economico(
            movimiento=movimiento_anulado,
            usuario=self.staff,
            motivo="Movimiento de prueba anulado",
        )

        respuesta = self.client.get(
            reverse("bitacora_diaria"),
            {"fecha": fecha_consulta.isoformat()},
        )

        self.assertEqual(
            respuesta.context["monto_dia"],
            Decimal("200.00"),
        )


class MovimientoHistoricoTests(ClinicaTestDataMixin, TestCase):
    def test_anulacion_excluye_movimiento_del_total_recibido(self):
        cita = self.crear_cita(estatus=Cita.ESTATUS_SI_ASISTIO)
        movimiento, _ = registrar_movimiento_economico(
            cita=cita,
            importe=Decimal("200.00"),
            metodo="Efectivo",
            usuario=self.staff,
        )

        movimiento_anulado, creado = anular_movimiento_economico(
            movimiento=movimiento,
            usuario=self.staff,
            motivo="Corrección de prueba",
        )

        self.assertTrue(creado)
        self.assertEqual(
            movimiento_anulado.estado,
            MovimientoEconomicoCita.ESTADO_ANULADO,
        )
        self.assertIsNotNone(movimiento_anulado.anulado_en)
        self.assertEqual(movimiento_anulado.anulado_por, self.staff)

    def test_datos_historicos_del_movimiento_son_inmutables(self):
        cita = self.crear_cita(estatus=Cita.ESTATUS_SI_ASISTIO)
        movimiento, _ = registrar_movimiento_economico(
            cita=cita,
            importe=Decimal("200.00"),
            metodo="Efectivo",
            usuario=self.staff,
        )
        otra_cita = self.crear_cita(
            paciente=self.otro_paciente,
            hora=time(11, 0),
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )
        valores_originales = {
            "cita_id": movimiento.cita_id,
            "importe": movimiento.importe,
            "metodo": movimiento.metodo,
            "registrado_en": movimiento.registrado_en,
            "registrado_por_id": movimiento.registrado_por_id,
        }

        cambios_prohibidos = {
            "cita_id": otra_cita.id,
            "importe": Decimal("999.00"),
            "metodo": "Transferencia",
            "registrado_en": timezone.now(),
            "registrado_por_id": self.usuario_terapeuta.id,
        }
        for campo, valor in cambios_prohibidos.items():
            with self.subTest(campo=campo):
                movimiento.refresh_from_db()
                setattr(movimiento, campo, valor)
                with self.assertRaises(ValidationError):
                    movimiento.save()

        movimiento.refresh_from_db()
        self.assertEqual(movimiento.cita_id, valores_originales["cita_id"])
        self.assertEqual(movimiento.importe, valores_originales["importe"])
        self.assertEqual(movimiento.metodo, valores_originales["metodo"])
        self.assertEqual(
            movimiento.registrado_en,
            valores_originales["registrado_en"],
        )
        self.assertEqual(
            movimiento.registrado_por_id,
            valores_originales["registrado_por_id"],
        )
