from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from clinica.models import CorteSemanal, Empresa, LineaNomina, Terapeuta
from clinica.tests_helpers import ClinicaTestDataMixin
from clinica.models import MovimientoEconomicoCita
from ventas.classification import (
    captador_es_elegible_para_liquidacion,
    captador_es_terapeuta,
)
from ventas.models import (
    Captacion,
    Captador,
    ComisionCaptacion,
    EventoLiquidacion,
    LineaLiquidacionComision,
    LiquidacionComisiones,
)


class LiquidacionesTestMixin(ClinicaTestDataMixin):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.captador = Captador.objects.create(
            tipo=Captador.TIPO_EXTERNO,
            nombre_externo="Escuela ABC",
            tipo_organizacion=Captador.ORG_ESCUELA,
        )

    def crear_comision(self, captador=None, paciente=None, hora=None, **cambios):
        captador = captador or self.captador
        paciente = paciente or self.paciente
        captacion = Captacion.objects.create(
            paciente=paciente,
            captador=captador,
            codigo=captador.codigo_activo,
            captador_nombre_snapshot=captador.nombre_display,
            captador_tipo_snapshot=captador.clasificacion_display,
        )
        cita = self.crear_cita(
            paciente=paciente,
            hora=hora or self.hora,
        )
        datos = {
            "captacion": captacion,
            "cita_generadora": cita,
            "captador_nombre_snapshot": captador.nombre_display,
            "paciente_nombre_snapshot": paciente.nombre,
            "porcentaje_aplicado": 7,
            "base_calculo": Decimal("400.00"),
            "monto_calculado": Decimal("28.00"),
        }
        datos.update(cambios)
        return ComisionCaptacion.objects.create(**datos)

    def crear_liquidacion(self, captador=None, **cambios):
        captador = captador or self.captador
        datos = {
            "captador": captador,
            "beneficiario_nombre_snapshot": captador.nombre_display,
            "creada_por": self.staff,
        }
        datos.update(cambios)
        return LiquidacionComisiones.objects.create(**datos)


class EstructuraLiquidacionTests(LiquidacionesTestMixin, TestCase):
    def test_liquidacion_nace_como_borrador_con_snapshot_y_auditoria(self):
        liquidacion = self.crear_liquidacion()

        self.assertEqual(liquidacion.estado, LiquidacionComisiones.ESTADO_BORRADOR)
        self.assertEqual(liquidacion.beneficiario_nombre_snapshot, "Escuela ABC")
        self.assertEqual(liquidacion.creada_por, self.staff)
        self.assertIsNotNone(liquidacion.creada_en)

    def test_captador_y_snapshot_son_obligatorios(self):
        casos = (
            {"beneficiario_nombre_snapshot": "Escuela ABC"},
            {"captador": self.captador, "beneficiario_nombre_snapshot": ""},
        )
        for datos in casos:
            with self.subTest(datos=datos):
                with self.assertRaises(ValidationError):
                    LiquidacionComisiones(**datos).full_clean()

    def test_linea_guarda_relaciones_usuario_fecha_y_activa_por_defecto(self):
        liquidacion = self.crear_liquidacion()
        comision = self.crear_comision()
        linea = LineaLiquidacionComision.objects.create(
            liquidacion=liquidacion,
            comision=comision,
            agregada_por=self.staff,
        )

        self.assertTrue(linea.activa)
        self.assertEqual(linea.agregada_por, self.staff)
        self.assertIsNotNone(linea.agregada_en)
        self.assertEqual(linea.liquidacion, liquidacion)
        self.assertEqual(linea.comision, comision)

    def test_comision_solo_admite_una_linea_activa(self):
        comision = self.crear_comision()
        primera = LineaLiquidacionComision.objects.create(
            liquidacion=self.crear_liquidacion(),
            comision=comision,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            LineaLiquidacionComision.objects.create(
                liquidacion=self.crear_liquidacion(),
                comision=comision,
            )

        primera.activa = False
        primera.save(update_fields=["activa"])
        segunda = LineaLiquidacionComision.objects.create(
            liquidacion=self.crear_liquidacion(),
            comision=comision,
        )
        self.assertTrue(segunda.activa)

    def test_rechaza_comision_de_otro_captador(self):
        otro_captador = Captador.objects.create(
            tipo=Captador.TIPO_EXTERNO,
            nombre_externo="Escuela B",
            tipo_organizacion=Captador.ORG_ESCUELA,
        )
        comision = self.crear_comision(captador=otro_captador)
        linea = LineaLiquidacionComision(
            liquidacion=self.crear_liquidacion(),
            comision=comision,
        )

        with self.assertRaises(ValidationError) as contexto:
            linea.full_clean()
        self.assertIn("comision", contexto.exception.message_dict)

    def test_rechaza_comision_suspendida(self):
        comision = self.crear_comision(
            estado=ComisionCaptacion.ESTADO_SUSPENDIDA,
        )
        linea = LineaLiquidacionComision(
            liquidacion=self.crear_liquidacion(),
            comision=comision,
        )
        with self.assertRaises(ValidationError):
            linea.full_clean()

    def test_evento_conserva_datos_sin_crearse_automaticamente(self):
        liquidacion = self.crear_liquidacion()
        self.assertFalse(EventoLiquidacion.objects.exists())

        evento = EventoLiquidacion.objects.create(
            liquidacion=liquidacion,
            accion=EventoLiquidacion.ACCION_LIQUIDACION_CREADA,
            usuario=self.staff,
            detalle={"origen": "prueba estructural"},
        )
        self.assertEqual(evento.liquidacion, liquidacion)
        self.assertEqual(evento.usuario, self.staff)
        self.assertEqual(evento.detalle["origen"], "prueba estructural")
        self.assertIsNotNone(evento.creado_en)

    def test_estructuras_no_producen_efectos_financieros(self):
        comision = self.crear_comision()
        estado_inicial = comision.estado
        LineaLiquidacionComision.objects.create(
            liquidacion=self.crear_liquidacion(),
            comision=comision,
        )

        comision.refresh_from_db()
        self.assertEqual(comision.estado, estado_inicial)
        self.assertFalse(MovimientoEconomicoCita.objects.exists())
        self.assertFalse(CorteSemanal.objects.exists())
        self.assertFalse(LineaNomina.objects.exists())


class ClasificacionCaptadoresTests(TestCase):
    def test_externo_es_elegible(self):
        captador = Captador.objects.create(
            tipo=Captador.TIPO_EXTERNO,
            nombre_externo="Universidad Externa",
            tipo_organizacion=Captador.ORG_UNIVERSIDAD,
        )
        self.assertTrue(captador_es_elegible_para_liquidacion(captador))
    def test_empresa_es_elegible(self):
        empresa = Empresa.objects.create(nombre="Empresa Convenio")
        captador = Captador.objects.create(
            tipo=Captador.TIPO_EMPRESA,
            empresa=empresa,
        )
        self.assertTrue(captador_es_elegible_para_liquidacion(captador))
    def test_interno_no_clinico_es_elegible(self):
        usuario = User.objects.create_user("administrativo")
        captador = Captador.objects.create(
            tipo=Captador.TIPO_INTERNO,
            usuario=usuario,
        )
        self.assertFalse(captador_es_terapeuta(captador))
        self.assertTrue(captador_es_elegible_para_liquidacion(captador))
    def test_interno_terapeuta_no_es_elegible(self):
        usuario = User.objects.create_user("terapeuta_captador")
        Terapeuta.objects.create(usuario=usuario, nombre="Terapeuta Captador")
        captador = Captador.objects.create(
            tipo=Captador.TIPO_INTERNO,
            usuario=usuario,
        )
        self.assertTrue(captador_es_terapeuta(captador))
        self.assertFalse(captador_es_elegible_para_liquidacion(captador))

    def test_nombre_de_grupo_no_define_si_es_terapeuta(self):
        usuario = User.objects.create_user("interno_con_grupo")
        grupo = Group.objects.create(name="Terapeutas")
        usuario.groups.add(grupo)
        captador = Captador.objects.create(
            tipo=Captador.TIPO_INTERNO,
            usuario=usuario,
        )
        self.assertFalse(captador_es_terapeuta(captador))
        self.assertTrue(captador_es_elegible_para_liquidacion(captador))
