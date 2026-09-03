from django.contrib.auth.models import Permission, User
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from clinica.models import Cita
from clinica.tests_helpers import ClinicaTestDataMixin

from ventas.forms import CaptacionForm
from ventas.models import Captacion, Captador, IntentoCaptacionRechazado
from ventas.services import evaluar_elegibilidad_captacion, registrar_captacion


class ElegibilidadCaptacionTests(ClinicaTestDataMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.captador = Captador.objects.create(
            tipo=Captador.TIPO_EXTERNO,
            nombre_externo="Colegio ABC",
            tipo_organizacion=Captador.ORG_ESCUELA,
        )

    def test_paciente_recien_creado_es_elegible(self):
        self.assertTrue(evaluar_elegibilidad_captacion(self.paciente).elegible)

    def test_cita_futura_no_elimina_elegibilidad(self):
        self.crear_cita(estatus=Cita.ESTATUS_CONFIRMADA)
        self.assertTrue(evaluar_elegibilidad_captacion(self.paciente).elegible)

    def test_cita_cancelada_no_elimina_elegibilidad(self):
        self.crear_cita(estatus=Cita.ESTATUS_CANCELO)
        self.assertTrue(evaluar_elegibilidad_captacion(self.paciente).elegible)

    def test_inasistencia_no_elimina_elegibilidad(self):
        self.crear_cita(estatus=Cita.ESTATUS_NO_ASISTIO)
        self.assertTrue(evaluar_elegibilidad_captacion(self.paciente).elegible)

    def test_cita_asistida_elimina_elegibilidad(self):
        self.crear_cita(estatus=Cita.ESTATUS_SI_ASISTIO)
        resultado = evaluar_elegibilidad_captacion(self.paciente)
        self.assertFalse(resultado.elegible)
        self.assertEqual(resultado.codigo, "atencion_previa")

    def test_asistencia_como_paciente_adicional_tambien_cuenta(self):
        cita = self.crear_cita(
            paciente=self.otro_paciente, estatus=Cita.ESTATUS_SI_ASISTIO
        )
        cita.pacientes_adicionales.add(self.paciente)
        self.assertFalse(evaluar_elegibilidad_captacion(self.paciente).elegible)

    def test_paciente_ya_captado_no_es_elegible(self):
        registrar_captacion(
            paciente=self.paciente,
            codigo=self.captador.codigo_activo,
            usuario=self.staff,
        )
        resultado = evaluar_elegibilidad_captacion(self.paciente)
        self.assertFalse(resultado.elegible)
        self.assertEqual(resultado.codigo, "ya_captado")

    def test_unicidad_por_paciente_tambien_existe_en_base_de_datos(self):
        datos = {
            "paciente": self.paciente,
            "captador": self.captador,
            "codigo": self.captador.codigo_activo,
            "captador_nombre_snapshot": "Colegio ABC",
            "captador_tipo_snapshot": "Escuela",
        }
        Captacion.objects.create(**datos)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Captacion.objects.create(**datos)


class CaptacionViewTests(ClinicaTestDataMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.recepcion = User.objects.create_user(
            "recepcion_captaciones",
            password="pruebas",
        )
        permisos = Permission.objects.filter(
            content_type__app_label="ventas",
            codename__in=("register_captacion", "view_captaciones"),
        )
        cls.recepcion.user_permissions.add(*permisos)
        cls.sin_permiso = User.objects.create_user(
            "sin_permiso_captaciones",
            password="pruebas",
        )
        cls.captador = Captador.objects.create(
            tipo=Captador.TIPO_EXTERNO,
            nombre_externo="Colegio ABC",
            tipo_organizacion=Captador.ORG_ESCUELA,
        )

    def enviar(self, token=None, accion="registrar"):
        return self.client.post(
            reverse("ventas:captacion_nueva"),
            {
                "paciente": self.paciente.pk,
                "codigo": token or self.captador.codigo_activo.token,
                "accion": accion,
            },
        )

    def test_usuario_sin_permiso_recibe_403(self):
        self.client.force_login(self.sin_permiso)
        self.assertEqual(
            self.client.get(reverse("ventas:captaciones_lista")).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse("ventas:captacion_nueva")).status_code,
            403,
        )

    def test_validacion_muestra_confirmacion_sin_crear_registro(self):
        self.client.force_login(self.recepcion)
        response = self.enviar(accion="validar")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirma la captación")
        self.assertContains(response, "Colegio ABC")
        self.assertEqual(Captacion.objects.count(), 0)

    def test_codigo_activo_crea_captacion_pendiente_y_snapshot(self):
        self.client.force_login(self.recepcion)
        response = self.enviar()
        captacion = Captacion.objects.get()
        self.assertRedirects(
            response,
            reverse("ventas:captacion_detalle", args=[captacion.pk]),
        )
        self.assertEqual(captacion.estado, Captacion.ESTADO_PENDIENTE)
        self.assertEqual(captacion.registrado_por, self.recepcion)
        self.assertEqual(captacion.captador_nombre_snapshot, "Colegio ABC")
        self.assertEqual(captacion.captador_tipo_snapshot, "Escuela")

    def test_codigo_publico_y_token_validan_el_mismo_codigo(self):
        self.client.force_login(self.recepcion)
        for entrada in (
            self.captador.codigo_activo.codigo_publico,
            self.captador.codigo_activo.token,
        ):
            with self.subTest(entrada=entrada):
                formulario = CaptacionForm({
                    "paciente": self.paciente.pk,
                    "codigo": entrada,
                })
                self.assertTrue(formulario.is_valid(), formulario.errors)
                self.assertEqual(
                    formulario.codigo_validado,
                    self.captador.codigo_activo,
                )

    def test_captador_inactivo_no_permite_captacion(self):
        self.captador.activo = False
        self.captador.save(update_fields=["activo"])
        self.client.force_login(self.recepcion)
        response = self.enviar()
        self.assertContains(response, "Este captador está inactivo")
        self.assertFalse(Captacion.objects.exists())

    def test_codigo_inexistente_no_permite_captacion(self):
        self.client.force_login(self.recepcion)
        response = self.enviar(token="codigo-inexistente")
        self.assertContains(response, "Código de captación no válido")
        self.assertFalse(Captacion.objects.exists())

    def test_doble_envio_crea_una_sola_captacion(self):
        self.client.force_login(self.recepcion)
        self.enviar()
        response = self.enviar()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ya cuenta con una captación")
        self.assertEqual(Captacion.objects.count(), 1)

    def test_paciente_atendido_no_permite_captacion(self):
        self.crear_cita(estatus=Cita.ESTATUS_SI_ASISTIO)
        self.client.force_login(self.recepcion)
        response = self.enviar()
        self.assertContains(response, "ya cuenta con atención previa")
        self.assertFalse(Captacion.objects.exists())
        intento = IntentoCaptacionRechazado.objects.get()
        self.assertEqual(intento.paciente, self.paciente)
        self.assertEqual(intento.registrado_por, self.recepcion)
        self.assertEqual(
            intento.motivo, IntentoCaptacionRechazado.MOTIVO_ATENCION_PREVIA
        )

    def test_lista_detalle_y_endpoint_de_elegibilidad(self):
        captacion = registrar_captacion(
            paciente=self.paciente,
            codigo=self.captador.codigo_activo,
            usuario=self.recepcion,
        )
        self.client.force_login(self.recepcion)
        lista = self.client.get(reverse("ventas:captaciones_lista"))
        detalle = self.client.get(reverse("ventas:captacion_detalle", args=[captacion.pk]))
        elegibilidad = self.client.get(
            reverse("ventas:elegibilidad_paciente", args=[self.otro_paciente.pk])
        )
        self.assertContains(lista, "Colegio ABC")
        self.assertContains(detalle, self.captador.codigo_activo.codigo_publico)
        self.assertNotContains(detalle, self.captador.codigo_activo.token)
        self.assertTrue(elegibilidad.json()["elegible"])

    def test_inicio_sustituye_validar_qr_por_captaciones(self):
        self.client.force_login(self.recepcion)
        response = self.client.get(reverse("ventas:inicio"))
        self.assertContains(response, "Captaciones")
        self.assertNotContains(response, ">Validar QR<")
