from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from clinica.models import Empresa
from ventas.forms import ConvenioEmpresaForm
from ventas.models import Captador, ConvenioEmpresa


class ConvenioEmpresaModelTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nombre="Empresa Uno")

    def convenio(self, **cambios):
        datos = {
            "empresa": self.empresa,
            "modalidad": ConvenioEmpresa.MODALIDAD_TARIFA_ESPECIAL,
            "quien_paga": ConvenioEmpresa.PAGA_EMPRESA,
        }
        datos.update(cambios)
        return ConvenioEmpresa(**datos)

    def test_empresa_puede_tener_un_convenio(self):
        convenio = self.convenio()
        convenio.full_clean()
        convenio.save()
        self.assertEqual(convenio.empresa, self.empresa)

    def test_empresa_conserva_varios_convenios_historicos(self):
        anterior = self.convenio(activo=False)
        anterior.full_clean()
        anterior.save()
        vigente = self.convenio(activo=True)
        vigente.full_clean()
        vigente.save()
        self.assertEqual(self.empresa.convenios_ventas.count(), 2)

    def test_no_permite_dos_convenios_activos_de_una_empresa(self):
        self.convenio().save()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.convenio().save()

    def test_dos_empresas_pueden_tener_convenio_activo(self):
        otra = Empresa.objects.create(nombre="Empresa Dos")
        self.convenio().save()
        self.convenio(empresa=otra).save()
        self.assertEqual(ConvenioEmpresa.objects.filter(activo=True).count(), 2)

    def test_vigencia_final_anterior_es_invalida(self):
        convenio = self.convenio(
            vigencia_desde=date(2026, 9, 2),
            vigencia_hasta=date(2026, 9, 1),
        )
        with self.assertRaises(ValidationError):
            convenio.full_clean()

    def test_limite_cero_es_invalido(self):
        with self.assertRaises(ValidationError):
            self.convenio(limite_consultas_mensual=0).full_clean()

    def test_consultas_por_pase_cero_es_invalido(self):
        with self.assertRaises(ValidationError):
            self.convenio(consultas_por_pase=0).full_clean()

    def test_consultas_por_pase_vacio_es_valido(self):
        self.convenio(
            modalidad=ConvenioEmpresa.MODALIDAD_PASE,
            consultas_por_pase=None,
        ).full_clean()

    def test_monto_mensual_negativo_es_invalido(self):
        with self.assertRaises(ValidationError):
            self.convenio(monto_mensual=Decimal("-0.01")).full_clean()

    def test_pase_no_requiere_identificador_por_defecto(self):
        self.assertFalse(self.convenio().pase_requiere_identificador)


class ConvenioEmpresaFormYVistaTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.usuario = User.objects.create_user("direccion", password="test")
        permiso = Permission.objects.get(
            content_type__app_label="ventas",
            codename="manage_captadores",
        )
        self.usuario.user_permissions.add(permiso)
        self.client.force_login(self.usuario)
        self.empresa = Empresa.objects.create(nombre="Empresa Convenio")
        self.otra_empresa = Empresa.objects.create(nombre="Empresa Ajena")
        self.captador = Captador.objects.create(
            tipo=Captador.TIPO_EMPRESA,
            empresa=self.empresa,
            creado_por=self.usuario,
        )
        self.url = reverse("ventas:captador_convenio", args=[self.captador.pk])

    def datos(self, **cambios):
        datos = {
            "activo": "on",
            "modalidad": ConvenioEmpresa.MODALIDAD_PASE,
            "quien_paga": ConvenioEmpresa.PAGA_EMPRESA,
            "vigencia_desde": "",
            "vigencia_hasta": "",
            "limite_consultas_mensual": "",
            "monto_mensual": "",
            "consultas_por_pase": "",
            "observaciones": "Convenio base",
        }
        datos.update(cambios)
        return datos

    def test_captador_empresa_puede_acceder(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_captador_interno_no_puede_configurar_convenio(self):
        interno = Captador.objects.create(
            tipo=Captador.TIPO_INTERNO,
            usuario=get_user_model().objects.create_user("interno"),
        )
        respuesta = self.client.get(
            reverse("ventas:captador_convenio", args=[interno.pk])
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_captador_externo_no_puede_configurar_convenio(self):
        externo = Captador.objects.create(
            tipo=Captador.TIPO_EXTERNO,
            nombre_externo="Externo",
        )
        respuesta = self.client.get(
            reverse("ventas:captador_convenio", args=[externo.pk])
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_empresa_proviene_del_captador_y_post_no_la_cambia(self):
        datos = self.datos(empresa=str(self.otra_empresa.pk))
        self.client.post(self.url, datos)
        convenio = ConvenioEmpresa.objects.get()
        self.assertEqual(convenio.empresa, self.empresa)

    def test_creacion_registra_autoria(self):
        self.client.post(self.url, self.datos())
        convenio = ConvenioEmpresa.objects.get()
        self.assertEqual(convenio.creado_por, self.usuario)
        self.assertEqual(convenio.actualizado_por, self.usuario)

    def test_edicion_conserva_empresa_y_creador_y_actualiza_usuario(self):
        creador = get_user_model().objects.create_user("creador")
        convenio = ConvenioEmpresa.objects.create(
            empresa=self.empresa,
            modalidad=ConvenioEmpresa.MODALIDAD_TARIFA_ESPECIAL,
            quien_paga=ConvenioEmpresa.PAGA_PACIENTE,
            creado_por=creador,
            actualizado_por=creador,
        )
        self.client.post(
            self.url,
            self.datos(modalidad=ConvenioEmpresa.MODALIDAD_PAQUETE_MENSUAL),
        )
        convenio.refresh_from_db()
        self.assertEqual(convenio.empresa, self.empresa)
        self.assertEqual(convenio.creado_por, creador)
        self.assertEqual(convenio.actualizado_por, self.usuario)
        self.assertEqual(
            convenio.modalidad,
            ConvenioEmpresa.MODALIDAD_PAQUETE_MENSUAL,
        )

    def test_pase_permite_identificador_falso_y_consultas_vacias(self):
        formulario = ConvenioEmpresaForm(self.datos())
        self.assertTrue(formulario.is_valid(), formulario.errors)
        self.assertFalse(formulario.cleaned_data["pase_requiere_identificador"])
        self.assertIsNone(formulario.cleaned_data["consultas_por_pase"])

    def test_pase_permite_identificador_verdadero(self):
        formulario = ConvenioEmpresaForm(
            self.datos(pase_requiere_identificador="on")
        )
        self.assertTrue(formulario.is_valid(), formulario.errors)
        self.assertTrue(formulario.cleaned_data["pase_requiere_identificador"])


class ConvenioEmpresaTemplateTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.usuario = User.objects.create_user("gestion", password="test")
        self.usuario.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="ventas",
                codename="manage_captadores",
            )
        )
        self.client.force_login(self.usuario)
        self.empresa = Empresa.objects.create(nombre="Empresa Visual")
        self.captador = Captador.objects.create(
            tipo=Captador.TIPO_EMPRESA,
            empresa=self.empresa,
        )

    def detalle(self, captador=None):
        return self.client.get(
            reverse("ventas:captador_detalle", args=[(captador or self.captador).pk])
        )

    def test_empresa_sin_convenio_muestra_sin_configurar(self):
        respuesta = self.detalle()
        self.assertContains(respuesta, "Convenio empresarial")
        self.assertContains(respuesta, "Sin configurar")

    def test_paquete_muestra_modalidad_limite_y_monto(self):
        ConvenioEmpresa.objects.create(
            empresa=self.empresa,
            modalidad=ConvenioEmpresa.MODALIDAD_PAQUETE_MENSUAL,
            quien_paga=ConvenioEmpresa.PAGA_EMPRESA,
            limite_consultas_mensual=10,
            monto_mensual=Decimal("8000.00"),
        )
        respuesta = self.detalle()
        self.assertContains(respuesta, "Paquete mensual")
        self.assertContains(respuesta, "Consultas incluidas por mes")
        self.assertContains(respuesta, "8,000.00")

    def test_pase_muestra_identificador_y_consultas_no_definidas(self):
        ConvenioEmpresa.objects.create(
            empresa=self.empresa,
            modalidad=ConvenioEmpresa.MODALIDAD_PASE,
            quien_paga=ConvenioEmpresa.PAGA_ASOCIACION,
            pase_requiere_identificador=True,
        )
        respuesta = self.detalle()
        self.assertContains(respuesta, "Pase / autorización")
        self.assertContains(respuesta, "Usa folio o identificador")
        self.assertContains(respuesta, "No definido")

    def test_interno_y_externo_no_muestran_tarjeta(self):
        interno = Captador.objects.create(
            tipo=Captador.TIPO_INTERNO,
            usuario=get_user_model().objects.create_user("interno-template"),
        )
        externo = Captador.objects.create(
            tipo=Captador.TIPO_EXTERNO,
            nombre_externo="Externo template",
        )
        self.assertNotContains(self.detalle(interno), "Convenio empresarial")
        self.assertNotContains(self.detalle(externo), "Convenio empresarial")
