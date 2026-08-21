from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from clinica.models import Empresa

from ventas.models import Captador, CodigoCaptacion


class CaptadorIdentidadTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("captador_interno", password="pruebas")
        self.empresa = Empresa.objects.create(nombre="Empresa Sintética")

    def test_captador_interno_reutiliza_user_y_genera_codigo(self):
        captador = Captador.objects.create(tipo=Captador.TIPO_INTERNO, usuario=self.usuario)
        self.assertEqual(captador.usuario, self.usuario)
        self.assertEqual(captador.nombre_display, "captador_interno")
        self.assertEqual(captador.codigos.filter(activo=True).count(), 1)

    def test_mismo_usuario_no_puede_ser_dos_captadores(self):
        Captador.objects.create(tipo=Captador.TIPO_INTERNO, usuario=self.usuario)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Captador.objects.create(tipo=Captador.TIPO_INTERNO, usuario=self.usuario)

    def test_empresa_existente_se_reutiliza_sin_duplicarla(self):
        captador = Captador.objects.create(tipo=Captador.TIPO_EMPRESA, empresa=self.empresa)
        self.assertEqual(captador.empresa, self.empresa)
        self.assertEqual(Empresa.objects.count(), 1)
        self.assertEqual(captador.nombre_display, "Empresa Sintética")

    def test_externo_libre_no_crea_usuario_ni_empresa(self):
        captador = Captador.objects.create(
            tipo=Captador.TIPO_EXTERNO,
            nombre_externo="Escuela Sintética",
            tipo_organizacion=Captador.ORG_ESCUELA,
            contacto="Contacto de prueba",
        )
        self.assertIsNone(captador.usuario)
        self.assertIsNone(captador.empresa)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Empresa.objects.count(), 1)

    def test_identidades_incoherentes_fallan_validacion(self):
        captador = Captador(
            tipo=Captador.TIPO_INTERNO,
            usuario=self.usuario,
            empresa=self.empresa,
        )
        with self.assertRaises(ValidationError):
            captador.full_clean()

    def test_captador_sin_identidad_falla_validacion(self):
        with self.assertRaises(ValidationError):
            Captador(tipo=Captador.TIPO_INTERNO).full_clean()


class CodigoCaptacionTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("codigo_interno")
        self.captador = Captador.objects.create(
            tipo=Captador.TIPO_INTERNO, usuario=self.usuario
        )

    def test_token_es_unico_no_vacio_y_no_derivado_trivialmente(self):
        codigo = self.captador.codigo_activo
        otro_usuario = User.objects.create_user("codigo_otro")
        otro = Captador.objects.create(tipo=Captador.TIPO_INTERNO, usuario=otro_usuario)
        self.assertGreaterEqual(len(codigo.token), 32)
        self.assertNotEqual(codigo.token, str(self.usuario.id))
        self.assertNotIn(self.usuario.username, codigo.token)
        self.assertNotEqual(codigo.token, otro.codigo_activo.token)

    def test_solo_un_codigo_activo_por_captador(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            CodigoCaptacion.objects.create(captador=self.captador, activo=True)

    def test_modelo_permite_codigo_historico_revocado(self):
        codigo = self.captador.codigo_activo
        codigo.activo = False
        codigo.save(update_fields=["activo"])
        nuevo = CodigoCaptacion.objects.create(captador=self.captador)
        self.assertNotEqual(codigo.token, nuevo.token)
        self.assertEqual(self.captador.codigos.count(), 2)
