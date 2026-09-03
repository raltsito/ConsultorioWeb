from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from clinica.models import Paciente

from ventas.forms import (
    AprobarCaptacionForm,
    CaptacionForm,
    CaptadorForm,
    ConfigurarComisionCaptadorForm,
)
from ventas.models import Captacion, Captador, CodigoCaptacion
from ventas.services import buscar_codigo_captacion, registrar_captacion


class CodigoPublicoModeloTests(TestCase):
    def test_formato_depende_del_pk_sin_persistir_otro_campo(self):
        self.assertEqual(CodigoCaptacion(pk=1).codigo_publico, "INTRA0001")
        self.assertEqual(CodigoCaptacion(pk=25).codigo_publico, "INTRA0025")
        self.assertEqual(CodigoCaptacion(pk=9999).codigo_publico, "INTRA9999")
        self.assertEqual(CodigoCaptacion(pk=10000).codigo_publico, "INTRA10000")

    def test_objeto_sin_pk_no_inventa_codigo_persistente(self):
        self.assertEqual(CodigoCaptacion().codigo_publico, "")


class CodigoPublicoResolucionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user("captador_codigo_publico")
        cls.captador = Captador.objects.create(
            tipo=Captador.TIPO_INTERNO,
            usuario=cls.usuario,
        )
        cls.codigo = cls.captador.codigo_activo
        cls.codigo.porcentaje_comision = 5
        cls.codigo.save(update_fields=["porcentaje_comision"])

    def assertResuelve(self, entrada):
        codigo, estado = buscar_codigo_captacion(entrada)
        self.assertEqual(estado, "valido")
        self.assertEqual(codigo, self.codigo)

    def test_resuelve_codigo_publico_sin_importar_mayusculas(self):
        numero = f"{self.codigo.pk:04d}"
        self.assertResuelve(f"INTRA{numero}")
        self.assertResuelve(f"intra{numero}")
        self.assertResuelve(f"InTrA{numero}")

    def test_conserva_token_y_url_historicos(self):
        self.assertResuelve(self.codigo.token)
        self.assertResuelve(
            "https://intra.example/ventas/captacion/"
            f"{self.codigo.token}/"
        )

    def test_rechaza_formatos_publicos_invalidos(self):
        for entrada in (
            "INTRA",
            "INTRA1",
            "INTRA0000",
            "INTRA00001",
            "INTRAABC",
            "INTRA-1",
            "INTRA_1",
        ):
            with self.subTest(entrada=entrada):
                self.assertEqual(buscar_codigo_captacion(entrada), (None, "inexistente"))

    def test_conserva_validaciones_posteriores_a_la_resolucion(self):
        self.codigo.activo = False
        self.codigo.save(update_fields=["activo"])
        self.assertEqual(
            buscar_codigo_captacion(self.codigo.codigo_publico)[1],
            "codigo_inactivo",
        )
        self.codigo.activo = True
        self.codigo.save(update_fields=["activo"])
        self.captador.activo = False
        self.captador.save(update_fields=["activo"])
        self.assertEqual(
            buscar_codigo_captacion(self.codigo.codigo_publico)[1],
            "inactivo",
        )

    def test_conserva_validacion_de_comision_configurada(self):
        self.codigo.porcentaje_comision = None
        self.codigo.save(update_fields=["porcentaje_comision"])
        self.assertEqual(
            buscar_codigo_captacion(self.codigo.codigo_publico)[1],
            "sin_configurar",
        )

    def test_porcentaje_cero_es_valido_por_codigo_publico_y_token(self):
        self.codigo.porcentaje_comision = 0
        self.codigo.save(update_fields=["porcentaje_comision"])

        self.assertResuelve(self.codigo.codigo_publico)
        self.assertResuelve(self.codigo.token)


class PorcentajeComisionFormulariosTests(TestCase):
    def formularios(self, porcentaje):
        return (
            CaptadorForm({
                "tipo": Captador.TIPO_EXTERNO,
                "nombre_externo": "Captador formulario",
                "tipo_organizacion": Captador.ORG_ESCUELA,
                "porcentaje_comision": porcentaje,
            }),
            ConfigurarComisionCaptadorForm({
                "porcentaje_comision": porcentaje,
            }),
            AprobarCaptacionForm({
                "porcentaje_comision": porcentaje,
            }),
        )

    def test_formularios_aceptan_0_1_y_10_como_enteros(self):
        for porcentaje in (0, 1, 10):
            with self.subTest(porcentaje=porcentaje):
                for formulario in self.formularios(porcentaje):
                    self.assertTrue(formulario.is_valid(), formulario.errors)
                    self.assertEqual(
                        formulario.cleaned_data["porcentaje_comision"],
                        porcentaje,
                    )

    def test_formularios_rechazan_menos_uno_y_once(self):
        for porcentaje in (-1, 11):
            with self.subTest(porcentaje=porcentaje):
                for formulario in self.formularios(porcentaje):
                    self.assertFalse(formulario.is_valid())


class CodigoPublicoFormularioYVistasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user(
            "captador_codigo_publico_ui",
            password="pruebas",
        )
        cls.captador = Captador.objects.create(
            tipo=Captador.TIPO_INTERNO,
            usuario=cls.usuario,
        )
        cls.codigo = cls.captador.codigo_activo
        cls.codigo.porcentaje_comision = 5
        cls.codigo.save(update_fields=["porcentaje_comision"])
        cls.paciente = Paciente.objects.create(
            nombre="Paciente código público",
            fecha_nacimiento="1990-01-01",
            sexo="Femenino",
        )
        cls.recepcion = User.objects.create_user(
            "recepcion_codigo_publico",
            password="pruebas",
        )
        permisos = Permission.objects.filter(
            content_type__app_label="ventas",
            codename__in=(
                "manage_captadores",
                "register_captacion",
                "validate_codigo",
                "view_captaciones",
            ),
        )
        cls.recepcion.user_permissions.add(*permisos)

    def test_porcentaje_cero_registra_captacion_y_conserva_snapshot(self):
        self.codigo.porcentaje_comision = 0
        self.codigo.save(update_fields=["porcentaje_comision"])

        captacion = registrar_captacion(
            paciente=self.paciente,
            codigo=self.codigo,
            usuario=self.recepcion,
            canal="Nuevo expediente",
        )

        self.assertEqual(captacion.estado, Captacion.ESTADO_APROBADA)
        self.assertEqual(captacion.porcentaje_comision, 0)
        self.assertEqual(captacion.eventos.get().porcentaje_comision, 0)

    def test_listado_muestra_cero_como_porcentaje_configurado(self):
        self.codigo.porcentaje_comision = 0
        self.codigo.save(update_fields=["porcentaje_comision"])
        registrar_captacion(
            paciente=self.paciente,
            codigo=self.codigo,
            usuario=self.recepcion,
        )
        self.client.force_login(self.recepcion)

        respuesta = self.client.get(reverse("ventas:captaciones_lista"))

        self.assertContains(respuesta, "0 %")

    def test_detalle_distingue_cero_de_sin_configurar(self):
        self.codigo.porcentaje_comision = 0
        self.codigo.save(update_fields=["porcentaje_comision"])
        self.client.force_login(self.recepcion)

        respuesta = self.client.get(
            reverse("ventas:captador_detalle", args=[self.captador.pk])
        )

        self.assertContains(respuesta, "0 %")
        self.assertNotContains(respuesta, "Sin configurar")

    def test_detalle_mantiene_none_como_sin_configurar(self):
        self.codigo.porcentaje_comision = None
        self.codigo.save(update_fields=["porcentaje_comision"])
        self.client.force_login(self.recepcion)

        respuesta = self.client.get(
            reverse("ventas:captador_detalle", args=[self.captador.pk])
        )

        self.assertContains(respuesta, "Sin configurar")

    def test_captacion_form_acepta_codigo_publico_y_token(self):
        for entrada in (self.codigo.codigo_publico, self.codigo.token):
            with self.subTest(entrada=entrada):
                form = CaptacionForm({
                    "paciente": self.paciente.pk,
                    "codigo": entrada,
                })
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.codigo_validado, self.codigo)

    def test_validadores_html_y_json_aceptan_codigo_publico(self):
        self.client.force_login(self.recepcion)
        html = self.client.get(
            reverse("ventas:validar_codigo"),
            {"codigo": self.codigo.codigo_publico},
        )
        self.assertContains(html, "Código válido")
        json = self.client.get(
            reverse("ventas:validar_codigo"),
            {"formato": "json", "codigo": self.codigo.codigo_publico},
        )
        self.assertTrue(json.json()["valido"])

    def test_panel_y_detalle_muestran_publico_y_ocultan_token(self):
        self.client.force_login(self.recepcion)
        lista = self.client.get(reverse("ventas:captadores_lista"))
        detalle = self.client.get(
            reverse("ventas:captador_detalle", args=[self.captador.pk])
        )
        for respuesta in (lista, detalle):
            self.assertContains(respuesta, self.codigo.codigo_publico)
            self.assertNotContains(respuesta, self.codigo.token)

    def test_mi_qr_muestra_publico_y_oculta_token(self):
        permiso = Permission.objects.get(
            content_type__app_label="ventas",
            codename="view_codigo_propio",
        )
        self.usuario.user_permissions.add(permiso)
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("ventas:mi_qr"))
        self.assertContains(respuesta, self.codigo.codigo_publico)
        self.assertNotContains(respuesta, self.codigo.token)

    def test_confirmacion_muestra_publico_y_conserva_token_oculto(self):
        self.client.force_login(self.recepcion)
        respuesta = self.client.post(
            reverse("ventas:captacion_nueva"),
            {
                "paciente": self.paciente.pk,
                "codigo": self.codigo.codigo_publico,
                "accion": "validar",
            },
        )
        self.assertContains(respuesta, self.codigo.codigo_publico)
        self.assertContains(
            respuesta,
            f'name="codigo" value="{self.codigo.token}"',
            html=False,
        )

    @patch("ventas.views.qrcode.QRCode")
    def test_qr_conserva_token_y_no_incluye_codigo_publico(self, qr_mock):
        imagen = qr_mock.return_value.make_image.return_value
        imagen.save.side_effect = lambda buffer, format: buffer.write(b"PNG")
        permiso = Permission.objects.get(
            content_type__app_label="ventas",
            codename="view_codigo_propio",
        )
        self.usuario.user_permissions.add(permiso)
        self.client.force_login(self.usuario)
        self.client.get(reverse("ventas:captador_qr", args=[self.captador.pk]))
        payload = qr_mock.return_value.add_data.call_args.args[0]
        self.assertIn(self.codigo.token, payload)
        self.assertNotIn(self.codigo.codigo_publico, payload)
        self.assertIn(
            reverse("ventas:validar_token", args=[self.codigo.token]),
            payload,
        )

    def test_url_publica_conserva_contrato_del_token(self):
        response = self.client.get(
            reverse("ventas:validar_token", args=[self.codigo.token])
        )
        self.assertContains(response, "Código de captación válido")
