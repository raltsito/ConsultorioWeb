from decimal import Decimal

from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
from django.test import TestCase

from clinica.models import Cita
from clinica.tests_helpers import ClinicaTestDataMixin

from ventas.models import Captacion, Captador, ComisionCaptacion
from ventas.services import (
    aprobar_captacion,
    calcular_monto_comision,
    registrar_captacion,
)


class ComisionCaptacionMixin(ClinicaTestDataMixin):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.captador = Captador.objects.create(
            tipo=Captador.TIPO_EXTERNO,
            nombre_externo="Escuela Comisión",
            tipo_organizacion=Captador.ORG_ESCUELA,
        )

    def crear_captacion(self, paciente=None):
        return registrar_captacion(
            paciente=paciente or self.paciente,
            codigo=self.captador.codigo_activo,
            usuario=self.staff,
        )

    def crear_comision(self, captacion=None, cita=None, **cambios):
        captacion = captacion or self.crear_captacion()
        cita = cita or self.crear_cita()
        datos = {
            "captacion": captacion,
            "cita_generadora": cita,
            "captador_nombre_snapshot": captacion.captador_nombre_snapshot,
            "paciente_nombre_snapshot": captacion.paciente.nombre,
            "porcentaje_aplicado": 7,
            "base_calculo": Decimal("450.00"),
            "monto_calculado": Decimal("31.50"),
            "moneda": "MXN",
        }
        datos.update(cambios)
        return ComisionCaptacion.objects.create(**datos)


class EstructuraComisionCaptacionTests(ComisionCaptacionMixin, TestCase):
    def test_una_captacion_admite_maximo_una_comision(self):
        comision = self.crear_comision()
        otra_cita = self.crear_cita(
            paciente=self.otro_paciente,
            hora=self.hora.replace(hour=11),
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.crear_comision(
                captacion=comision.captacion,
                cita=otra_cita,
            )

    def test_una_cita_admite_maximo_una_comision(self):
        cita = self.crear_cita()
        self.crear_comision(cita=cita)
        otra_captacion = self.crear_captacion(paciente=self.otro_paciente)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.crear_comision(
                captacion=otra_captacion,
                cita=cita,
            )

    def test_campos_monetarios_se_recuperan_como_decimal(self):
        comision = self.crear_comision()
        comision.refresh_from_db()
        self.assertIsInstance(comision.base_calculo, Decimal)
        self.assertIsInstance(comision.monto_calculado, Decimal)
        self.assertEqual(comision.base_calculo, Decimal("450.00"))
        self.assertEqual(comision.monto_calculado, Decimal("31.50"))

    def test_porcentaje_snapshot_valido_supera_validacion_del_modelo(self):
        captacion = self.crear_captacion()
        cita = self.crear_cita()
        for porcentaje in (1, 10):
            with self.subTest(porcentaje=porcentaje):
                comision = self.crear_comision(
                    captacion=captacion,
                    cita=cita,
                    porcentaje_aplicado=porcentaje,
                )
                comision.full_clean()
                comision.delete()

    def test_porcentaje_fuera_de_rango_falla_validacion(self):
        captacion = self.crear_captacion()
        cita = self.crear_cita()
        for porcentaje in (0, 11):
            with self.subTest(porcentaje=porcentaje):
                comision = ComisionCaptacion(
                    captacion=captacion,
                    cita_generadora=cita,
                    captador_nombre_snapshot="Escuela Comisión",
                    paciente_nombre_snapshot=self.paciente.nombre,
                    porcentaje_aplicado=porcentaje,
                    base_calculo=Decimal("100.00"),
                    monto_calculado=Decimal("1.00"),
                )
                with self.assertRaises(ValidationError) as contexto:
                    comision.full_clean()
                self.assertIn("porcentaje_aplicado", contexto.exception.message_dict)


class CalculoPuroComisionTests(TestCase):
    def test_calcula_un_por_ciento(self):
        monto = calcular_monto_comision(
            base_calculo=Decimal("450.00"),
            porcentaje=1,
        )
        self.assertEqual(monto, Decimal("4.50"))

    def test_calcula_diez_por_ciento(self):
        monto = calcular_monto_comision(
            base_calculo=Decimal("450.00"),
            porcentaje=10,
        )
        self.assertEqual(monto, Decimal("45.00"))

    def test_redondeo_monetario_es_half_up(self):
        monto = calcular_monto_comision(
            base_calculo=Decimal("10.05"),
            porcentaje=10,
        )
        self.assertEqual(monto, Decimal("1.01"))


class ComisionPermaneceInerteTests(ComisionCaptacionMixin, TestCase):
    def test_registrar_captacion_no_crea_comision(self):
        self.crear_captacion()
        self.assertFalse(ComisionCaptacion.objects.exists())

    def test_aprobar_captacion_no_crea_comision(self):
        captacion = self.crear_captacion()
        aprobar_captacion(
            captacion=captacion,
            porcentaje=7,
            usuario=self.staff,
        )
        self.assertFalse(ComisionCaptacion.objects.exists())

    def test_marcar_cita_como_asistida_no_crea_comision(self):
        self.crear_captacion()
        cita = self.crear_cita()
        cita.estatus = Cita.ESTATUS_SI_ASISTIO
        cita.save(update_fields=["estatus"])
        self.assertFalse(ComisionCaptacion.objects.exists())
