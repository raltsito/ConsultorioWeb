from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .forms import CheckoutCitaForm
from .models import Cita, CobroCita, Pago, SolicitudCita
from .tests_helpers import ClinicaTestDataMixin


class CheckoutTerapeutaSinPagoFormalTests(ClinicaTestDataMixin, TestCase):
    def setUp(self):
        self.client.force_login(self.usuario_terapeuta)

    def checkout(self, cita, **datos):
        payload = {"estatus": Cita.ESTATUS_SI_ASISTIO}
        payload.update(datos)
        return self.client.post(reverse("checkout_cita", args=[cita.pk]), payload)

    def test_formulario_conserva_campos_originales_y_retira_importe_recibido(self):
        form = CheckoutCitaForm()
        self.assertEqual(
            set(form.fields),
            {
                "estatus", "metodo_pago", "costo", "solicitar_siguiente",
                "siguiente_fecha", "siguiente_hora", "notas_recepcion",
            },
        )
        self.assertNotIn("importe_recibido", form.fields)

    def test_checkout_guarda_estatus_metodo_y_costo_sin_crear_pago(self):
        cita = self.crear_cita(
            costo=Decimal("500.00"),
            metodo_pago=None,
            estatus=Cita.ESTATUS_CONFIRMADA,
        )
        respuesta = self.checkout(
            cita,
            metodo_pago="Efectivo",
            costo="475.00",
        )
        self.assertEqual(respuesta.status_code, 302)
        cita.refresh_from_db()
        self.assertEqual(cita.estatus, Cita.ESTATUS_SI_ASISTIO)
        self.assertEqual(cita.metodo_pago, "Efectivo")
        self.assertEqual(cita.costo, Decimal("475.00"))
        self.assertFalse(CobroCita.objects.filter(cita=cita).exists())
        self.assertFalse(Pago.objects.filter(cobro__cita=cita).exists())

    def test_checkout_sin_costo_nuevo_conserva_costo_existente(self):
        cita = self.crear_cita(costo=Decimal("500.00"), metodo_pago=None)
        self.checkout(cita, metodo_pago="Transferencia")
        cita.refresh_from_db()
        self.assertEqual(cita.costo, Decimal("500.00"))
        self.assertEqual(cita.metodo_pago, "Transferencia")
        self.assertFalse(Pago.objects.filter(cobro__cita=cita).exists())

    def test_checkout_puede_crear_solicitud_de_seguimiento_sin_pago(self):
        cita = self.crear_cita(costo=Decimal("500.00"))
        fecha_siguiente = self.fecha + timedelta(days=7)
        self.checkout(
            cita,
            metodo_pago="Pase",
            costo="500.00",
            solicitar_siguiente="on",
            siguiente_fecha=fecha_siguiente.isoformat(),
            siguiente_hora="11:30",
            notas_recepcion="Prefiere horario matutino.",
        )
        solicitud = SolicitudCita.objects.get(terapeuta=self.terapeuta)
        self.assertEqual(solicitud.paciente_nombre, cita.paciente.nombre)
        self.assertEqual(solicitud.fecha_deseada, fecha_siguiente)
        self.assertEqual(solicitud.hora_deseada.strftime("%H:%M"), "11:30")
        self.assertEqual(solicitud.notas_paciente, "Prefiere horario matutino.")
        self.assertFalse(Pago.objects.filter(cobro__cita=cita).exists())

    def test_resultados_originales_se_guardan_sin_crear_pago(self):
        for indice, estatus in enumerate((
            Cita.ESTATUS_NO_ASISTIO,
            Cita.ESTATUS_CANCELO,
            Cita.ESTATUS_INCIDENCIA,
        )):
            with self.subTest(estatus=estatus):
                cita = self.crear_cita(
                    fecha=self.fecha + timedelta(days=indice + 1),
                    estatus=Cita.ESTATUS_CONFIRMADA,
                )
                self.checkout(
                    cita,
                    estatus=estatus,
                    metodo_pago="Efectivo",
                    costo="350.00",
                )
                cita.refresh_from_db()
                self.assertEqual(cita.estatus, estatus)
                self.assertEqual(cita.metodo_pago, "Efectivo")
                self.assertEqual(cita.costo, Decimal("350.00"))
                self.assertFalse(Pago.objects.filter(cobro__cita=cita).exists())

    def test_modal_conserva_checkout_y_no_muestra_importe_recibido(self):
        respuesta = self.client.get(reverse("portal_terapeuta"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'name="estatus"')
        self.assertContains(respuesta, 'name="metodo_pago"')
        self.assertContains(respuesta, 'name="costo"')
        self.assertContains(respuesta, 'name="solicitar_siguiente"')
        self.assertContains(respuesta, 'name="siguiente_fecha"')
        self.assertContains(respuesta, 'name="siguiente_hora"')
        self.assertContains(respuesta, 'name="notas_recepcion"')
        self.assertNotContains(respuesta, 'name="importe_recibido"')
        self.assertNotContains(respuesta, "Importe recibido")
