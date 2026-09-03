from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from clinica.models import Empresa
from ventas.forms import CaptadorForm
from ventas.models import Captador


class AltaEmpresaNuevaDesdeCaptadorTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            "gestion_empresas",
            password="pruebas",
        )
        self.usuario.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="ventas",
                codename="manage_captadores",
            )
        )
        self.client.force_login(self.usuario)
        self.url = reverse("ventas:captador_nuevo")

    def datos(self, **cambios):
        datos = {
            "tipo": CaptadorForm.EMPRESA_NUEVA,
            "empresa_nueva_nombre": "Empresa Nueva INTRA",
            "contacto": "Contacto",
            "correo": "contacto@example.com",
            "telefono": "5551234567",
            "porcentaje_comision": "7",
        }
        datos.update(cambios)
        return datos

    def test_empresa_nueva_crea_empresa_captador_codigo_y_comision(self):
        respuesta = self.client.post(self.url, self.datos())

        self.assertEqual(respuesta.status_code, 302)
        empresa = Empresa.objects.get(nombre="Empresa Nueva INTRA")
        captador = Captador.objects.get(empresa=empresa)
        self.assertEqual(captador.tipo, Captador.TIPO_EMPRESA)
        self.assertTrue(empresa.activo)
        self.assertIsNotNone(captador.codigo_activo)
        self.assertEqual(captador.codigo_activo.porcentaje_comision, 7)

    def test_nombre_existente_no_duplica_empresa(self):
        Empresa.objects.create(nombre="EMPRESA NUEVA INTRA", activo=False)

        respuesta = self.client.post(self.url, self.datos())

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Empresa.objects.count(), 1)
        self.assertEqual(Captador.objects.count(), 0)
        self.assertContains(
            respuesta,
            "Ya existe una empresa con este nombre. "
            "Selecciona Empresa existente.",
        )

    @patch(
        "ventas.signals.CodigoCaptacion.objects.create",
        side_effect=RuntimeError("Fallo posterior simulado"),
    )
    def test_fallo_posterior_revierte_empresa_nueva(self, _crear_codigo):
        with self.assertRaises(RuntimeError):
            self.client.post(self.url, self.datos())

        self.assertFalse(
            Empresa.objects.filter(nombre="Empresa Nueva INTRA").exists()
        )
        self.assertEqual(Captador.objects.count(), 0)

    def test_empresa_existente_no_crea_otra_empresa(self):
        empresa = Empresa.objects.create(nombre="Empresa Existente")

        respuesta = self.client.post(
            self.url,
            self.datos(
                tipo=Captador.TIPO_EMPRESA,
                empresa=str(empresa.pk),
                empresa_nueva_nombre="Debe ignorarse",
            ),
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Empresa.objects.count(), 1)
        self.assertEqual(Captador.objects.get().empresa, empresa)

    def test_interno_conserva_comportamiento_previo(self):
        interno = get_user_model().objects.create_user("captador_interno_nuevo")

        respuesta = self.client.post(
            self.url,
            self.datos(
                tipo=Captador.TIPO_INTERNO,
                usuario=str(interno.pk),
                empresa_nueva_nombre="Debe ignorarse",
            ),
        )

        self.assertEqual(respuesta.status_code, 302)
        captador = Captador.objects.get(usuario=interno)
        self.assertIsNone(captador.empresa)
        self.assertEqual(Empresa.objects.count(), 0)

    def test_externo_conserva_comportamiento_previo(self):
        respuesta = self.client.post(
            self.url,
            self.datos(
                tipo=Captador.TIPO_EXTERNO,
                nombre_externo="Organización Externa",
                tipo_organizacion=Captador.ORG_ORGANIZACION,
                empresa_nueva_nombre="Debe ignorarse",
            ),
        )

        self.assertEqual(respuesta.status_code, 302)
        captador = Captador.objects.get()
        self.assertEqual(captador.tipo, Captador.TIPO_EXTERNO)
        self.assertIsNone(captador.empresa)
        self.assertEqual(Empresa.objects.count(), 0)
