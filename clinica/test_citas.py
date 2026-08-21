from datetime import date, time
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .forms import CitaForm
from .models import BloqueoAgendaTerapeuta, Cita, MovimientoEconomicoCita
from .tests_helpers import ClinicaTestDataMixin


class CitaModeloYPrecioTests(ClinicaTestDataMixin, TestCase):
    def test_cita_con_datos_validos_conserva_costo_manual_y_estado(self):
        cita = self.crear_cita(costo=Decimal("487.50"), estatus=Cita.ESTATUS_SIN_CONFIRMAR)

        self.assertEqual(cita.costo, Decimal("487.50"))
        self.assertEqual(cita.estatus, Cita.ESTATUS_SIN_CONFIRMAR)
        self.assertEqual(cita.servicio, self.servicio)
        self.assertEqual(cita.terapeuta, self.terapeuta)
        self.assertEqual(cita.consultorio, self.consultorio)

    def test_servicio_precio_y_cita_costo_son_independientes(self):
        cita = self.crear_cita(costo=Decimal("450.00"))
        self.servicio.precio = Decimal("725.00")
        self.servicio.save(update_fields=["precio"])
        cita.refresh_from_db()
        self.assertEqual(cita.costo, Decimal("450.00"))

        cita.costo = Decimal("410.00")
        cita.save(update_fields=["costo"])
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.precio, Decimal("725.00"))

    def test_agendar_desde_paciente_muestra_costo_inicial_hardcodeado(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("agendar_cita", args=[self.paciente.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial["costo"], 500)


class CitaFormColisionesTests(ClinicaTestDataMixin, TestCase):
    def datos_form(self, **overrides):
        datos = {
            "paciente": self.paciente.id,
            "fecha": self.fecha.isoformat(),
            "hora": self.hora.strftime("%H:%M"),
            "tipo_paciente": Cita.TIPO_SEGUIMIENTO,
            "division": self.division.id,
            "consultorio": self.consultorio.id,
            "servicio": self.servicio.id,
            "terapeuta": self.terapeuta.id,
            "costo": "500.00",
            "estatus": Cita.ESTATUS_CONFIRMADA,
            "tiene_descuento": "false",
        }
        datos.update(overrides)
        return datos

    def test_paciente_principal_no_puede_empalmarse(self):
        self.crear_cita()
        form = CitaForm(data=self.datos_form(terapeuta=self.otro_terapeuta.id, consultorio=self.otro_consultorio.id))
        self.assertFalse(form.is_valid())
        self.assertIn("paciente", form.errors)

    def test_paciente_adicional_no_puede_empalmarse(self):
        self.crear_cita(paciente=self.otro_paciente)
        form = CitaForm(data=self.datos_form(pacientes_extra=[self.otro_paciente.id]))
        self.assertFalse(form.is_valid())
        self.assertIn("pacientes_extra", form.errors)

    def test_horario_fuera_de_rango_es_rechazado(self):
        form = CitaForm(data=self.datos_form(hora="20:00"))
        self.assertFalse(form.is_valid())
        self.assertIn("hora", form.errors)

    def test_bloqueo_del_terapeuta_es_rechazado(self):
        BloqueoAgendaTerapeuta.objects.create(
            terapeuta=self.terapeuta,
            tipo_bloqueo=BloqueoAgendaTerapeuta.TIPO_TEMPORAL,
            alcance=BloqueoAgendaTerapeuta.ALCANCE_FECHA,
            fecha_inicio=self.fecha,
            fecha_fin=self.fecha,
        )
        form = CitaForm(data=self.datos_form())
        self.assertFalse(form.is_valid())
        self.assertIn("terapeuta", form.errors)

    def test_vista_crear_rechaza_terapeuta_ocupado(self):
        self.crear_cita(paciente=self.otro_paciente)
        self.client.force_login(self.staff)
        response = self.client.post(reverse("crear_cita"), self.datos_form(consultorio=self.otro_consultorio.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Cita.objects.count(), 1)

    def test_vista_crear_rechaza_consultorio_ocupado(self):
        self.crear_cita(paciente=self.otro_paciente, terapeuta=self.otro_terapeuta)
        self.client.force_login(self.staff)
        response = self.client.post(reverse("crear_cita"), self.datos_form())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Cita.objects.count(), 1)


class EdicionCitaTests(ClinicaTestDataMixin, TestCase):
    def test_servicio_850_costo_200_registra_unicamente_200(self):
        self.servicio.precio = Decimal("850.00")
        self.servicio.save(update_fields=["precio"])
        cita = self.crear_cita(
            costo=Decimal("200.00"),
            estatus=Cita.ESTATUS_CONFIRMADA,
        )
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("editar_cita", args=[cita.id]),
            {
                "paciente": self.paciente.id,
                "fecha": self.fecha.isoformat(),
                "hora": self.hora.strftime("%H:%M"),
                "tipo_paciente": Cita.TIPO_SEGUIMIENTO,
                "division": self.division.id,
                "consultorio": self.consultorio.id,
                "servicio": self.servicio.id,
                "terapeuta": self.terapeuta.id,
                "costo": "200.00",
                "metodo_pago": "Efectivo",
                "estatus": Cita.ESTATUS_SI_ASISTIO,
                "tiene_descuento": "false",
            },
        )

        self.assertEqual(response.status_code, 302)
        movimiento = MovimientoEconomicoCita.objects.get(cita=cita)
        self.assertEqual(movimiento.importe, Decimal("200.00"))
        self.assertEqual(movimiento.metodo, "Efectivo")
        self.assertNotEqual(movimiento.importe, Decimal("850.00"))

        cita.refresh_from_db()
        self.assertEqual(
            cita.precio_servicio_base_snapshot,
            Decimal("850.00"),
        )
        self.assertEqual(
            cita.descuento_captacion_porcentaje_snapshot,
            Decimal("0.00"),
        )
        self.assertEqual(cita.importe_servicio_snapshot, Decimal("850.00"))

    def test_edicion_persiste_campos_permitidos_actuales(self):
        cita = self.crear_cita()
        self.client.force_login(self.staff)
        nueva_fecha = date(2030, 1, 14)
        response = self.client.post(
            reverse("editar_cita", args=[cita.id]),
            {
                "paciente": self.paciente.id,
                "fecha": nueva_fecha.isoformat(),
                "hora": "11:00",
                "tipo_paciente": Cita.TIPO_NUEVO,
                "division": self.division.id,
                "consultorio": self.otro_consultorio.id,
                "servicio": self.otro_servicio.id,
                "terapeuta": self.otro_terapeuta.id,
                "costo": "777.00",
                "metodo_pago": "Transferencia",
                "estatus": Cita.ESTATUS_INCIDENCIA,
                "tiene_descuento": "true",
            },
        )
        self.assertEqual(response.status_code, 302)
        cita.refresh_from_db()
        self.assertEqual(cita.fecha, nueva_fecha)
        self.assertEqual(cita.hora, time(11, 0))
        self.assertEqual(cita.terapeuta, self.otro_terapeuta)
        self.assertEqual(cita.servicio, self.otro_servicio)
        self.assertEqual(cita.costo, Decimal("777.00"))
        self.assertEqual(cita.estatus, Cita.ESTATUS_INCIDENCIA)
