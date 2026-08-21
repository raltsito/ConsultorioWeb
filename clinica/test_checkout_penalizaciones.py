from datetime import date, timedelta
from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from .models import Cita, CorteSemanal, LineaNomina, PenalizacionPaciente, Servicio, SolicitudCita
from .tests_helpers import ClinicaTestDataMixin


class CheckoutCitaTests(ClinicaTestDataMixin, TestCase):
    def checkout(self, cita, **datos):
        payload = {"estatus": Cita.ESTATUS_SI_ASISTIO}
        payload.update(datos)
        return self.client.post(reverse("checkout_cita", args=[cita.id]), payload)

    def test_solo_terapeuta_asignado_puede_cerrar(self):
        cita = self.crear_cita()
        self.client.force_login(self.usuario_otro_terapeuta)
        response = self.checkout(cita)
        self.assertEqual(response.status_code, 404)
        cita.refresh_from_db()
        self.assertEqual(cita.estatus, Cita.ESTATUS_CONFIRMADA)

    def test_usuario_sin_perfil_terapeuta_es_redirigido(self):
        cita = self.crear_cita()
        self.client.force_login(self.staff)
        response = self.checkout(cita)
        self.assertRedirects(response, reverse("home"))

    def test_checkout_admite_cuatro_resultados_actuales(self):
        self.client.force_login(self.usuario_terapeuta)
        for indice, estatus in enumerate((
            Cita.ESTATUS_SI_ASISTIO,
            Cita.ESTATUS_NO_ASISTIO,
            Cita.ESTATUS_CANCELO,
            Cita.ESTATUS_INCIDENCIA,
        )):
            with self.subTest(estatus=estatus):
                cita = self.crear_cita(
                    fecha=self.fecha + timedelta(days=7 * indice),
                    estatus=Cita.ESTATUS_CONFIRMADA,
                )
                response = self.checkout(
                    cita,
                    estatus=estatus,
                    metodo_pago="Efectivo",
                    costo="321.50",
                )
                self.assertEqual(response.status_code, 302)
                cita.refresh_from_db()
                self.assertEqual(cita.estatus, estatus)
                self.assertEqual(cita.metodo_pago, "Efectivo")
                self.assertEqual(cita.costo, Decimal("321.50"))

    def test_checkout_sin_metodo_ni_costo_conserva_valores_previos(self):
        cita = self.crear_cita(costo=Decimal("499.00"), metodo_pago="Transferencia")
        self.client.force_login(self.usuario_terapeuta)
        self.checkout(cita, estatus=Cita.ESTATUS_SI_ASISTIO)
        cita.refresh_from_db()
        self.assertEqual(cita.metodo_pago, "Transferencia")
        self.assertEqual(cita.costo, Decimal("499.00"))
        self.assertEqual(cita.estatus, Cita.ESTATUS_SI_ASISTIO)

    def test_checkout_puede_dejar_asistencia_sin_metodo_de_pago(self):
        cita = self.crear_cita(metodo_pago=None)
        self.client.force_login(self.usuario_terapeuta)
        self.checkout(cita, estatus=Cita.ESTATUS_SI_ASISTIO, costo="500.00")
        cita.refresh_from_db()
        self.assertIsNone(cita.metodo_pago)
        self.assertEqual(cita.estatus, Cita.ESTATUS_SI_ASISTIO)

    def test_checkout_crea_solicitud_de_seguimiento_opcional(self):
        cita = self.crear_cita()
        self.client.force_login(self.usuario_terapeuta)
        siguiente = date(2030, 1, 21)
        self.checkout(
            cita,
            estatus=Cita.ESTATUS_SI_ASISTIO,
            solicitar_siguiente="on",
            siguiente_fecha=siguiente.isoformat(),
            siguiente_hora="12:00",
            notas_recepcion="Horario de prueba",
        )
        solicitud = SolicitudCita.objects.get()
        self.assertEqual(solicitud.paciente_nombre, self.paciente.nombre)
        self.assertEqual(solicitud.terapeuta, self.terapeuta)
        self.assertEqual(solicitud.fecha_deseada, siguiente)
        self.assertEqual(solicitud.estado, "pendiente")


class PenalizacionSignalTests(ClinicaTestDataMixin, TestCase):
    def test_no_asistencia_genera_penalizacion_una_sola_vez(self):
        cita = self.crear_cita(estatus=Cita.ESTATUS_NO_ASISTIO)
        penalizacion = PenalizacionPaciente.objects.get()
        self.assertEqual(penalizacion.cita_origen, cita)
        self.assertEqual(penalizacion.paciente, self.paciente)
        self.assertEqual(penalizacion.monto, Decimal("300.00"))
        self.assertFalse(penalizacion.pagada)

        cita.notas = "Segundo guardado"
        cita.save()
        self.assertEqual(PenalizacionPaciente.objects.count(), 1)

    def test_servicio_sin_precio_no_genera_penalizacion(self):
        servicio = Servicio.objects.create(nombre="Servicio sin tarifa", precio=None)
        self.crear_cita(servicio=servicio, estatus=Cita.ESTATUS_NO_ASISTIO)
        self.assertFalse(PenalizacionPaciente.objects.exists())

    def test_cita_sin_servicio_no_genera_penalizacion(self):
        self.crear_cita(servicio=None, estatus=Cita.ESTATUS_NO_ASISTIO)
        self.assertFalse(PenalizacionPaciente.objects.exists())

    def test_cita_sin_paciente_no_es_admitida_por_el_modelo(self):
        with self.assertRaises(IntegrityError):
            self.crear_cita(paciente=None, estatus=Cita.ESTATUS_NO_ASISTIO)

    def test_siguiente_cita_suma_penalizacion_y_la_marca_pagada_al_agendar(self):
        origen = self.crear_cita(estatus=Cita.ESTATUS_NO_ASISTIO)
        penalizacion = origen.penalizacion_generada
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("crear_cita"),
            {
                "paciente": self.paciente.id,
                "fecha": date(2030, 1, 14).isoformat(),
                "hora": "10:00",
                "tipo_paciente": Cita.TIPO_SEGUIMIENTO,
                "division": self.division.id,
                "consultorio": self.consultorio.id,
                "servicio": self.servicio.id,
                "terapeuta": self.terapeuta.id,
                "costo": "500.00",
                "estatus": Cita.ESTATUS_CONFIRMADA,
                "tiene_descuento": "false",
            },
        )
        self.assertEqual(response.status_code, 302)
        siguiente = Cita.objects.exclude(pk=origen.pk).get()
        self.assertEqual(siguiente.costo, Decimal("800.00"))
        penalizacion.refresh_from_db()
        self.assertTrue(penalizacion.pagada)
        self.assertEqual(penalizacion.cita_cobro, siguiente)


class PagoPenalizacionTerapeutaTests(ClinicaTestDataMixin, TestCase):
    def test_asistencia_a_cita_de_cobro_crea_pago_50_por_ciento_sin_duplicar(self):
        self.crear_regla(pago_por_sesion=Decimal("240.00"))
        origen = self.crear_cita(estatus=Cita.ESTATUS_NO_ASISTIO)
        penalizacion = origen.penalizacion_generada
        cobro = self.crear_cita(
            fecha=date(2030, 1, 14),
            costo=Decimal("800.00"),
            estatus=Cita.ESTATUS_CONFIRMADA,
        )
        penalizacion.pagada = True
        penalizacion.cita_cobro = cobro
        penalizacion.save(update_fields=["pagada", "cita_cobro"])

        cobro.estatus = Cita.ESTATUS_SI_ASISTIO
        cobro.save(update_fields=["estatus"])

        linea = LineaNomina.objects.get(tipo=LineaNomina.TIPO_PENALIZACION)
        self.assertEqual(linea.cita, origen)
        self.assertEqual(linea.monto, Decimal("120.00"))
        self.assertEqual(linea.corte.terapeuta, self.terapeuta)
        self.assertEqual(linea.corte.fecha_inicio.weekday(), 4)

        cobro.save()
        self.assertEqual(
            LineaNomina.objects.filter(tipo=LineaNomina.TIPO_PENALIZACION).count(), 1
        )
        corte = CorteSemanal.objects.get()
        self.assertEqual(corte.total_bonos, Decimal("120.00"))
        self.assertEqual(corte.total_pago, Decimal("120.00"))
