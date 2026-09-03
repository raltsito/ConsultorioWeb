from dataclasses import FrozenInstanceError
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from ventas.models import (
    Captacion,
    Captador,
    ComisionCaptacion,
    LiquidacionComisiones,
)
from ventas.services import rechazar_captacion, registrar_captacion

from .models import (
    BonoExtra,
    CategoriaServicio,
    Cita,
    CorteSemanal,
    LineaNomina,
    MovimientoEconomicoCita,
    ReglaBeneficioReferido,
    Servicio,
    TarifaServicio,
)
from .services_beneficios import (
    crear_regla_beneficio,
    paciente_tiene_captacion_registrada,
    resolver_beneficio_referido,
)
from .tests_helpers import ClinicaTestDataMixin


class ResolucionBeneficioReferidoTests(ClinicaTestDataMixin, TestCase):
    fecha_base = date(2030, 1, 15)
    inicio_politica = date(2029, 1, 1)

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.captador = Captador.objects.create(
            tipo=Captador.TIPO_EXTERNO,
            nombre_externo='Organización Referente',
            tipo_organizacion=Captador.ORG_ORGANIZACION,
            creado_por=cls.staff,
        )

        cls.categoria_psicoterapia = cls._crear_categoria(
            'PSICOTERAPIA',
            'Psicoterapia',
            1,
        )
        cls.categoria_medica = cls._crear_categoria('MEDICA', 'Médica', 2)
        cls.categoria_fisioterapia = cls._crear_categoria(
            'FISIOTERAPIA',
            'Fisioterapia',
            3,
        )
        cls.categoria_nutricion = cls._crear_categoria(
            'NUTRICION',
            'Nutrición',
            4,
        )
        cls.categoria_hipnosis = cls._crear_categoria(
            'HIPNOSIS',
            'Hipnosis',
            5,
        )

        cls.servicio_psicoterapia = cls._crear_servicio(
            'PSICO-IND',
            'Terapia individual',
            cls.categoria_psicoterapia,
            '999.00',
        )
        cls.servicio_medico = cls._crear_servicio(
            'MED-CONS',
            'Consulta médica',
            cls.categoria_medica,
            '999.00',
        )
        cls.servicio_fisioterapia = cls._crear_servicio(
            'FISIO-CONS',
            'Consulta de fisioterapia',
            cls.categoria_fisioterapia,
            '999.00',
        )
        cls.servicio_nutricion = cls._crear_servicio(
            'NUTRI-CONS',
            'Consulta de nutrición',
            cls.categoria_nutricion,
            '999.00',
        )
        cls.servicio_hipnosis = cls._crear_servicio(
            'HIPNO-CONS',
            'Sesión de hipnosis',
            cls.categoria_hipnosis,
            '999.00',
        )

        cls._crear_regla(cls.categoria_psicoterapia, '25.00')
        for categoria in (
            cls.categoria_medica,
            cls.categoria_fisioterapia,
            cls.categoria_nutricion,
            cls.categoria_hipnosis,
        ):
            cls._crear_regla(categoria, '20.00')

        cls._crear_tarifa(cls.servicio_psicoterapia, '650.00')
        cls._crear_tarifa(cls.servicio_medico, '900.00')
        cls._crear_tarifa(cls.servicio_fisioterapia, '700.00')
        cls._crear_tarifa(cls.servicio_nutricion, '800.00')
        cls._crear_tarifa(cls.servicio_hipnosis, '1000.00')

    @classmethod
    def _crear_categoria(cls, codigo, nombre, orden=0):
        return CategoriaServicio.objects.create(
            codigo=codigo,
            nombre=nombre,
            orden=orden,
        )

    @classmethod
    def _crear_servicio(cls, codigo, nombre, categoria, precio_legacy='777.00'):
        return Servicio.objects.create(
            codigo=codigo,
            nombre=nombre,
            categoria=categoria,
            activo=True,
            tratamiento_iva=Servicio.IVA_EXENTO,
            precio=Decimal(precio_legacy),
        )

    @classmethod
    def _crear_regla(
        cls,
        categoria,
        porcentaje,
        desde=None,
        hasta=None,
    ):
        return crear_regla_beneficio(
            categoria=categoria,
            porcentaje_descuento=Decimal(porcentaje),
            vigente_desde=desde or cls.inicio_politica,
            vigente_hasta=hasta,
            actor=cls.staff,
        )

    @classmethod
    def _crear_tarifa(
        cls,
        servicio,
        precio,
        desde=None,
        hasta=None,
    ):
        return TarifaServicio.objects.create(
            servicio=servicio,
            precio_final=Decimal(precio),
            gratuita=False,
            vigente_desde=desde or cls.inicio_politica,
            vigente_hasta=hasta,
            estado=TarifaServicio.ESTADO_PUBLICADA,
            origen=TarifaServicio.ORIGEN_DIRECCION,
            tratamiento_iva_snapshot=Servicio.IVA_EXENTO,
            tasa_iva_snapshot=Decimal('0.00'),
            creada_por=cls.staff,
            publicada_por=cls.staff,
            publicada_en=timezone.now(),
        )

    def registrar_origen(self):
        existente = Captacion.objects.filter(paciente=self.paciente).first()
        if existente is not None:
            return existente
        return registrar_captacion(
            paciente=self.paciente,
            codigo=self.captador.codigo_activo,
            usuario=self.staff,
            canal='QR de prueba',
        )

    def resolver(self, *, servicio=None, fecha=None, registrar=True):
        if registrar:
            self.registrar_origen()
        return resolver_beneficio_referido(
            paciente=self.paciente,
            servicio=servicio or self.servicio_psicoterapia,
            fecha=fecha or self.fecha_base,
        )

    def test_paciente_sin_captacion_no_recibe_beneficio(self):
        resultado = self.resolver(registrar=False)
        self.assertFalse(paciente_tiene_captacion_registrada(self.paciente))
        self.assertFalse(resultado.aplica)
        self.assertEqual(resultado.motivo, 'paciente_no_referido')
        self.assertIsNone(resultado.captacion)

    def test_captacion_registrada_pendiente_aplica_sin_aprobacion(self):
        captacion = self.registrar_origen()
        self.assertEqual(captacion.estado, Captacion.ESTADO_PENDIENTE)
        self.assertIsNone(captacion.porcentaje_comision)
        self.assertTrue(paciente_tiene_captacion_registrada(self.paciente))

        resultado = self.resolver()

        self.assertTrue(resultado.aplica)
        self.assertEqual(resultado.captacion, captacion)

    def test_comision_pendiente_no_bloquea_beneficio(self):
        captacion = self.registrar_origen()
        captacion.porcentaje_comision = None
        captacion.save(update_fields=['porcentaje_comision'])
        self.assertTrue(self.resolver().aplica)

    def test_primera_consulta_recibe_beneficio(self):
        self.registrar_origen()
        self.crear_cita(
            fecha=self.fecha_base,
            servicio=self.servicio_psicoterapia,
            tipo_paciente=Cita.TIPO_NUEVO,
        )
        self.assertTrue(self.resolver().aplica)

    def test_segunda_consulta_recibe_beneficio(self):
        self.registrar_origen()
        self.crear_cita(
            fecha=self.fecha_base - timedelta(days=7),
            servicio=self.servicio_psicoterapia,
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )
        segunda = self.crear_cita(
            fecha=self.fecha_base,
            servicio=self.servicio_psicoterapia,
            tipo_paciente=Cita.TIPO_SEGUIMIENTO,
        )
        resultado = self.resolver(servicio=segunda.servicio, fecha=segunda.fecha)
        self.assertTrue(resultado.aplica)

    def test_tercera_y_multiples_consultas_reciben_beneficio(self):
        self.registrar_origen()
        for dias in (14, 7):
            self.crear_cita(
                fecha=self.fecha_base - timedelta(days=dias),
                servicio=self.servicio_psicoterapia,
                estatus=Cita.ESTATUS_SI_ASISTIO,
            )
        tercera = self.crear_cita(
            fecha=self.fecha_base,
            servicio=self.servicio_psicoterapia,
            tipo_paciente=Cita.TIPO_SEGUIMIENTO,
        )
        resultado = self.resolver(servicio=tercera.servicio, fecha=tercera.fecha)
        self.assertTrue(resultado.aplica)
        self.assertEqual(resultado.porcentaje_beneficio, Decimal('25.00'))

    def test_psicoterapia_usa_regla_configurada_25(self):
        resultado = self.resolver(servicio=self.servicio_psicoterapia)
        self.assertEqual(resultado.porcentaje_beneficio, Decimal('25.00'))

    def test_medica_usa_regla_configurada_20(self):
        resultado = self.resolver(servicio=self.servicio_medico)
        self.assertEqual(resultado.porcentaje_beneficio, Decimal('20.00'))

    def test_nutricion_usa_regla_configurada_20(self):
        resultado = self.resolver(servicio=self.servicio_nutricion)
        self.assertEqual(resultado.porcentaje_beneficio, Decimal('20.00'))

    def test_hipnosis_usa_regla_configurada_20(self):
        resultado = self.resolver(servicio=self.servicio_hipnosis)
        self.assertEqual(resultado.porcentaje_beneficio, Decimal('20.00'))

    def test_fisioterapia_usa_regla_configurada_20(self):
        resultado = self.resolver(servicio=self.servicio_fisioterapia)
        self.assertEqual(resultado.porcentaje_beneficio, Decimal('20.00'))

    def test_servicio_sin_categoria_no_se_infiere(self):
        servicio = Servicio.objects.create(
            nombre='Servicio sin categoría',
            precio=Decimal('650.00'),
        )
        resultado = self.resolver(servicio=servicio)
        self.assertFalse(resultado.aplica)
        self.assertEqual(resultado.motivo, 'categoria_no_determinada')

    def test_categoria_sin_regla_no_recibe_beneficio(self):
        categoria = self._crear_categoria('EVALUACION', 'Evaluación')
        servicio = self._crear_servicio('EVAL-01', 'Evaluación inicial', categoria)
        tarifa = self._crear_tarifa(servicio, '700.00')

        resultado = self.resolver(servicio=servicio)

        self.assertFalse(resultado.aplica)
        self.assertEqual(resultado.motivo, 'regla_no_disponible')
        self.assertEqual(resultado.tarifa, tarifa)

    def test_servicio_sin_tarifa_oficial_no_recibe_beneficio(self):
        servicio = self._crear_servicio(
            'PSICO-SIN-TARIFA',
            'Psicoterapia sin tarifa',
            self.categoria_psicoterapia,
            '1200.00',
        )
        resultado = self.resolver(servicio=servicio)
        self.assertFalse(resultado.aplica)
        self.assertEqual(resultado.motivo, 'tarifa_oficial_no_disponible')

    def test_regla_futura_no_aplica_antes_de_vigencia(self):
        categoria = self._crear_categoria('FUTURA', 'Categoría futura')
        servicio = self._crear_servicio('FUT-01', 'Servicio futuro', categoria)
        self._crear_tarifa(servicio, '500.00')
        self._crear_regla(
            categoria,
            '20.00',
            desde=self.fecha_base + timedelta(days=1),
        )

        resultado = self.resolver(servicio=servicio)

        self.assertFalse(resultado.aplica)
        self.assertEqual(resultado.motivo, 'regla_no_disponible')

    def test_regla_historica_aplica_en_su_fecha(self):
        categoria = self._crear_categoria('HIST-REGLA', 'Regla histórica')
        servicio = self._crear_servicio('HIST-REGLA-01', 'Servicio histórico', categoria)
        self._crear_tarifa(servicio, '600.00', desde=date(2029, 1, 1))
        regla = self._crear_regla(
            categoria,
            '25.00',
            desde=date(2029, 1, 1),
            hasta=date(2029, 12, 31),
        )

        resultado = self.resolver(servicio=servicio, fecha=date(2029, 6, 1))

        self.assertTrue(resultado.aplica)
        self.assertEqual(resultado.regla, regla)

    def test_tarifa_historica_se_resuelve_segun_fecha(self):
        categoria = self._crear_categoria('HIST-TARIFA', 'Tarifa histórica')
        servicio = self._crear_servicio('HIST-TAR-01', 'Servicio con historia', categoria)
        self._crear_regla(categoria, '25.00', desde=date(2029, 1, 1))
        self._crear_tarifa(
            servicio,
            '600.00',
            desde=date(2029, 1, 1),
            hasta=date(2029, 12, 31),
        )
        self._crear_tarifa(servicio, '650.00', desde=date(2030, 1, 1))

        diciembre = self.resolver(servicio=servicio, fecha=date(2029, 12, 20))
        enero = self.resolver(servicio=servicio, fecha=date(2030, 1, 10))

        self.assertEqual(diciembre.tarifa_oficial, Decimal('600.00'))
        self.assertEqual(enero.tarifa_oficial, Decimal('650.00'))

    def test_cambio_de_servicio_cambia_porcentaje(self):
        psicoterapia = self.resolver(servicio=self.servicio_psicoterapia)
        nutricion = self.resolver(servicio=self.servicio_nutricion)
        self.assertEqual(psicoterapia.porcentaje_beneficio, Decimal('25.00'))
        self.assertEqual(nutricion.porcentaje_beneficio, Decimal('20.00'))

    def test_cambio_de_regla_se_resuelve_segun_fecha(self):
        categoria = self._crear_categoria('CAMBIO-REGLA', 'Cambio de regla')
        servicio = self._crear_servicio('CAM-REG-01', 'Servicio con cambios', categoria)
        self._crear_tarifa(servicio, '650.00', desde=date(2029, 1, 1))
        self._crear_regla(
            categoria,
            '25.00',
            desde=date(2029, 1, 1),
            hasta=date(2029, 12, 31),
        )
        self._crear_regla(categoria, '20.00', desde=date(2030, 1, 1))

        anterior = self.resolver(servicio=servicio, fecha=date(2029, 12, 20))
        nueva = self.resolver(servicio=servicio, fecha=date(2030, 1, 10))

        self.assertEqual(anterior.porcentaje_beneficio, Decimal('25.00'))
        self.assertEqual(nueva.porcentaje_beneficio, Decimal('20.00'))

    def test_calculo_y_resultado_usan_decimal(self):
        resultado = self.resolver()
        self.assertIsInstance(resultado.tarifa_oficial, Decimal)
        self.assertIsInstance(resultado.porcentaje_beneficio, Decimal)
        self.assertIsInstance(resultado.importe_descuento, Decimal)
        self.assertIsInstance(resultado.total_despues_beneficio, Decimal)
        self.assertEqual(resultado.tarifa_oficial, Decimal('650.00'))
        self.assertEqual(resultado.importe_descuento, Decimal('162.50'))
        self.assertEqual(resultado.total_despues_beneficio, Decimal('487.50'))

    def test_redondeo_usa_round_half_up_a_dos_decimales(self):
        categoria = self._crear_categoria('REDONDEO', 'Redondeo')
        servicio = self._crear_servicio('RED-01', 'Servicio de redondeo', categoria)
        self._crear_regla(categoria, '25.00')
        self._crear_tarifa(servicio, '100.02')

        resultado = self.resolver(servicio=servicio)

        self.assertEqual(resultado.importe_descuento, Decimal('25.01'))
        self.assertEqual(resultado.total_despues_beneficio, Decimal('75.01'))

    def test_resultado_es_estructurado_e_inmutable(self):
        resultado = self.resolver()
        with self.assertRaises(FrozenInstanceError):
            resultado.aplica = False

    def test_resolver_no_modifica_cita_costo(self):
        cita = self.crear_cita(
            costo=Decimal('437.80'),
            servicio=self.servicio_psicoterapia,
        )
        self.resolver(servicio=cita.servicio, fecha=cita.fecha)
        cita.refresh_from_db()
        self.assertEqual(cita.costo, Decimal('437.80'))

    def test_resolver_no_modifica_servicio_precio(self):
        precio_legacy = self.servicio_psicoterapia.precio
        resultado = self.resolver(servicio=self.servicio_psicoterapia)
        self.servicio_psicoterapia.refresh_from_db()
        self.assertEqual(self.servicio_psicoterapia.precio, precio_legacy)
        self.assertNotEqual(resultado.tarifa_oficial, precio_legacy)

    def test_resolver_no_escribe_snapshots_antiguos(self):
        cita = self.crear_cita(servicio=self.servicio_psicoterapia)
        self.resolver(servicio=cita.servicio, fecha=cita.fecha)
        cita.refresh_from_db()
        self.assertIsNone(cita.precio_servicio_base_snapshot)
        self.assertIsNone(cita.descuento_captacion_porcentaje_snapshot)
        self.assertIsNone(cita.importe_servicio_snapshot)

    def test_resolver_no_crea_movimiento_economico(self):
        self.resolver()
        self.assertFalse(MovimientoEconomicoCita.objects.exists())

    def test_resolver_no_crea_comision_captacion(self):
        self.resolver()
        self.assertFalse(ComisionCaptacion.objects.exists())

    def test_resolver_no_modifica_liquidaciones(self):
        cantidad_anterior = LiquidacionComisiones.objects.count()
        self.resolver()
        self.assertEqual(LiquidacionComisiones.objects.count(), cantidad_anterior)

    def test_resolver_no_modifica_nomina(self):
        conteos_anteriores = (
            CorteSemanal.objects.count(),
            LineaNomina.objects.count(),
            BonoExtra.objects.count(),
        )
        self.resolver()
        self.assertEqual(
            (
                CorteSemanal.objects.count(),
                LineaNomina.objects.count(),
                BonoExtra.objects.count(),
            ),
            conteos_anteriores,
        )

    def test_resolver_no_depende_de_cita_tipo_paciente_referido(self):
        self.registrar_origen()
        cita = self.crear_cita(
            servicio=self.servicio_psicoterapia,
            tipo_paciente=Cita.TIPO_NUEVO,
        )
        resultado = self.resolver(servicio=cita.servicio, fecha=cita.fecha)
        self.assertTrue(resultado.aplica)

    def test_resolver_no_depende_del_nombre_del_servicio(self):
        servicio = self._crear_servicio(
            'NOMBRE-IRRELEVANTE',
            'OTROS sin palabras de psicoterapia',
            self.categoria_psicoterapia,
        )
        self._crear_tarifa(servicio, '650.00')
        resultado = self.resolver(servicio=servicio)
        self.assertEqual(resultado.porcentaje_beneficio, Decimal('25.00'))

    def test_rechazo_de_comision_por_direccion_no_bloquea_beneficio(self):
        captacion = self.registrar_origen()
        rechazar_captacion(
            captacion=captacion,
            motivo='No se autoriza comisión en esta prueba.',
            usuario=self.staff,
        )
        captacion.refresh_from_db()
        self.assertEqual(captacion.estado, Captacion.ESTADO_RECHAZADA)
        self.assertIsNone(captacion.porcentaje_comision)

        resultado = self.resolver()

        self.assertTrue(resultado.aplica)
        self.assertEqual(resultado.captacion, captacion)

    def test_resolver_no_modifica_captacion(self):
        captacion = self.registrar_origen()
        estado_anterior = captacion.estado
        porcentaje_anterior = captacion.porcentaje_comision
        self.resolver()
        captacion.refresh_from_db()
        self.assertEqual(captacion.estado, estado_anterior)
        self.assertEqual(captacion.porcentaje_comision, porcentaje_anterior)
