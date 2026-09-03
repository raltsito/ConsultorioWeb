from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from clinica.models import Empresa

from ventas.models import Captador, EventoCaptador


class VentasViewMixin:
    def conceder(self, usuario, *codigos):
        permisos = Permission.objects.filter(
            content_type__app_label="ventas",
            codename__in=codigos,
        )
        usuario.user_permissions.add(*permisos)


class AdministracionCaptadoresTests(VentasViewMixin, TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin_ventas", password="pruebas")
        self.no_autorizado = User.objects.create_user("sin_permiso", password="pruebas")
        self.conceder(self.admin, "manage_captadores")

    def test_usuario_no_autorizado_no_administra(self):
        self.client.force_login(self.no_autorizado)
        response = self.client.get(reverse("ventas:captadores_lista"))
        self.assertEqual(response.status_code, 403)

    def test_crea_captador_interno_sin_duplicar_usuario(self):
        interno = User.objects.create_user("interno_existente")
        total_usuarios = User.objects.count()
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("ventas:captador_nuevo"),
            {
                "tipo": Captador.TIPO_INTERNO,
                "usuario": interno.id,
            },
        )
        self.assertEqual(response.status_code, 302)
        captador = Captador.objects.get(usuario=interno)
        self.assertEqual(User.objects.count(), total_usuarios)
        self.assertIsNotNone(captador.codigo_activo)
        self.assertTrue(
            captador.eventos.filter(
                accion=EventoCaptador.ACCION_CREADO
            ).exists()
        )

    def test_crea_captador_de_empresa_existente(self):
        empresa = Empresa.objects.create(nombre="Empresa Vista")
        self.client.force_login(self.admin)
        self.client.post(
            reverse("ventas:captador_nuevo"),
            {
                "tipo": Captador.TIPO_EMPRESA,
                "empresa": empresa.id,
                "contacto": "Contacto Empresa",
            },
        )
        self.assertEqual(Captador.objects.get().empresa, empresa)
        self.assertEqual(Empresa.objects.count(), 1)

    def test_crea_organizacion_externa_sin_user_ficticio(self):
        total_usuarios = User.objects.count()
        self.client.force_login(self.admin)
        self.client.post(
            reverse("ventas:captador_nuevo"),
            {
                "tipo": Captador.TIPO_EXTERNO,
                "nombre_externo": "Universidad Vista",
                "tipo_organizacion": Captador.ORG_UNIVERSIDAD,
                "contacto": "Persona Sintética",
                "correo": "contacto@example.com",
            },
        )
        captador = Captador.objects.get()
        self.assertIsNone(captador.usuario)
        self.assertIsNone(captador.empresa)
        self.assertEqual(User.objects.count(), total_usuarios)

    def test_desactivar_y_reactivar_conserva_exactamente_el_token(self):
        interno = User.objects.create_user("estado_interno")
        captador = Captador.objects.create(tipo=Captador.TIPO_INTERNO, usuario=interno)
        token = captador.codigo_activo.token
        self.client.force_login(self.admin)
        self.client.post(
            reverse("ventas:captador_desactivar", args=[captador.id]),
            {"motivo": "Pausa de prueba"},
        )
        captador.refresh_from_db()
        self.assertFalse(captador.activo)
        self.assertEqual(captador.codigo_activo.token, token)
        self.assertIsNotNone(captador.desactivado_en)

        self.client.post(reverse("ventas:captador_reactivar", args=[captador.id]))
        captador.refresh_from_db()
        self.assertTrue(captador.activo)
        self.assertEqual(captador.codigo_activo.token, token)
        self.assertEqual(captador.codigos.count(), 1)

    def test_lista_y_detalle_renderizan_codigo_y_qr(self):
        interno = User.objects.create_user("render_interno")
        captador = Captador.objects.create(tipo=Captador.TIPO_INTERNO, usuario=interno)
        self.client.force_login(self.admin)
        lista = self.client.get(reverse("ventas:captadores_lista"))
        detalle = self.client.get(reverse("ventas:captador_detalle", args=[captador.id]))
        self.assertEqual(lista.status_code, 200)
        self.assertContains(lista, captador.nombre_display)
        self.assertContains(lista, captador.codigo_activo.codigo_publico)
        self.assertNotContains(lista, captador.codigo_activo.token)
        self.assertEqual(detalle.status_code, 200)
        self.assertContains(detalle, captador.codigo_activo.codigo_publico)
        self.assertNotContains(detalle, captador.codigo_activo.token)


class ValidacionYQRTests(VentasViewMixin, TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("duenio_qr", password="pruebas")
        self.captador = Captador.objects.create(
            tipo=Captador.TIPO_INTERNO, usuario=self.usuario
        )
        self.recepcion = User.objects.create_user("recepcion_qr", password="pruebas")
        self.conceder(self.recepcion, "validate_codigo")

    def test_recepcion_con_permiso_puede_validar(self):
        self.client.force_login(self.recepcion)
        response = self.client.get(
            reverse("ventas:validar_codigo"),
            {"codigo": self.captador.codigo_activo.token},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Código válido")
        self.assertContains(response, self.captador.nombre_display)

    def test_validacion_publica_distingue_activo_inactivo_e_invalido(self):
        url = reverse("ventas:validar_token", args=[self.captador.codigo_activo.token])
        self.assertContains(self.client.get(url), "Código de captación válido")
        self.captador.activo = False
        self.captador.save(update_fields=["activo"])
        self.assertContains(self.client.get(url), "Código de captación inactivo")
        self.assertContains(
            self.client.get(reverse("ventas:validar_token", args=["token-inexistente"])),
            "Código de captación no válido",
            status_code=404,
        )

    @patch("ventas.views.qrcode.QRCode")
    def test_qr_codifica_solo_url_con_token_sin_datos_economicos(self, qr_mock):
        imagen = qr_mock.return_value.make_image.return_value
        imagen.save.side_effect = lambda buffer, format: buffer.write(b"PNG")
        self.conceder(self.usuario, "view_codigo_propio")
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("ventas:captador_qr", args=[self.captador.id]))
        self.assertEqual(response.status_code, 200)
        contenido = qr_mock.return_value.add_data.call_args.args[0]
        self.assertIn(self.captador.codigo_activo.token, contenido)
        self.assertNotIn(self.captador.codigo_activo.codigo_publico, contenido)
        self.assertNotIn("comision", contenido.lower())
        self.assertNotIn("descuento", contenido.lower())
        self.assertNotIn("porcentaje", contenido.lower())

    def test_captador_solo_consulta_su_qr(self):
        self.conceder(self.usuario, "view_codigo_propio")
        otro_usuario = User.objects.create_user("otro_duenio")
        otro = Captador.objects.create(tipo=Captador.TIPO_INTERNO, usuario=otro_usuario)
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(reverse("ventas:mi_qr")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("ventas:captador_qr", args=[otro.id])).status_code,
            403,
        )

    def test_endpoint_qr_real_responde_png(self):
        self.conceder(self.usuario, "view_codigo_propio")
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("ventas:captador_qr", args=[self.captador.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertTrue(response.content.startswith(b"\x89PNG"))

    def test_acceso_rapido_ventas_respeta_permiso(self):
        self.client.force_login(self.recepcion)
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Ventas")
        sin_permiso = User.objects.create_user("home_sin_permiso")
        self.client.force_login(sin_permiso)
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, "Captación y comisiones")
