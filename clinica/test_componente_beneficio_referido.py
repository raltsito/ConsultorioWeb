from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ventas.models import Captacion, Captador, ComisionCaptacion
from ventas.services import registrar_captacion

from .models import (
    BonoExtra,
    CategoriaServicio,
    CorteSemanal,
    LineaNomina,
    MovimientoEconomicoCita,
    ReglaBeneficioReferido,
    Servicio,
    TarifaServicio,
)
from .services_beneficios import crear_regla_beneficio
from .tests_helpers import ClinicaTestDataMixin


class ComponenteBeneficioReferidoTests(ClinicaTestDataMixin, TestCase):
    fecha_base = date(2030, 1, 15)

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.recepcion = User.objects.create_user(
            username='recepcion_beneficios',
            password='pruebas',
        )
        cls.recepcion.user_permissions.add(
            Permission.objects.get(
                content_type__app_label='ventas',
                codename='view_captaciones',
            )
        )

        cls.categoria_psicoterapia = cls._crear_categoria(
            'PSICO-UI',
            'Psicoterapia UI',
            1,
        )
        cls.categoria_medica = cls._crear_categoria(
            'MEDICA-UI',
            'Médica UI',
            2,
        )
        cls.servicio_psicoterapia = cls._crear_servicio(
            'PSICO-UI-IND',
            'Terapia individual UI',
            cls.categoria_psicoterapia,
            '999.00',
        )
        cls.servicio_medico = cls._crear_servicio(
            'MEDICA-UI-CONS',
            'Consulta médica UI',
            cls.categoria_medica,
            '1200.00',
        )
        cls._crear_regla(cls.categoria_psicoterapia, '25.00')
        cls._crear_regla(cls.categoria_medica, '20.00')
        cls._crear_tarifa(cls.servicio_psicoterapia, '650.00')
        cls._crear_tarifa(cls.servicio_medico, '900.00')

        cls.categoria_cambio_tarifa = cls._crear_categoria(
            'CAMBIO-TARIFA-UI',
            'Cambio tarifa UI',
            3,
        )
        cls.servicio_cambio_tarifa = cls._crear_servicio(
            'CAMBIO-TARIFA-UI-SERV',
            'Servicio con tarifas por fecha',
            cls.categoria_cambio_tarifa,
            '777.00',
        )
        cls._crear_regla(cls.categoria_cambio_tarifa, '25.00')
        cls._crear_tarifa(
            cls.servicio_cambio_tarifa,
            '600.00',
            desde=date(2029, 1, 1),
            hasta=date(2029, 12, 31),
        )
        cls._crear_tarifa(
            cls.servicio_cambio_tarifa,
            '700.00',
            desde=date(2030, 1, 1),
        )

        cls.categoria_cambio_regla = cls._crear_categoria(
            'CAMBIO-REGLA-UI',
            'Cambio regla UI',
            4,
        )
        cls.servicio_cambio_regla = cls._crear_servicio(
            'CAMBIO-REGLA-UI-SERV',
            'Servicio con reglas por fecha',
            cls.categoria_cambio_regla,
            '777.00',
        )
        cls._crear_tarifa(cls.servicio_cambio_regla, '800.00')
        cls._crear_regla(
            cls.categoria_cambio_regla,
            '10.00',
            desde=date(2029, 1, 1),
            hasta=date(2029, 12, 31),
        )
        cls._crear_regla(
            cls.categoria_cambio_regla,
            '20.00',
            desde=date(2030, 1, 1),
        )

        cls.servicio_sin_categoria = cls._crear_servicio(
            'SIN-CATEGORIA-UI',
            'Servicio sin categoría UI',
            None,
            '500.00',
        )
        cls.servicio_sin_tarifa = cls._crear_servicio(
            'SIN-TARIFA-UI',
            'Servicio sin tarifa UI',
            cls.categoria_psicoterapia,
            '500.00',
        )
        cls.categoria_sin_regla = cls._crear_categoria(
            'SIN-REGLA-UI',
            'Sin regla UI',
            5,
        )
        cls.servicio_sin_regla = cls._crear_servicio(
            'SIN-REGLA-UI-SERV',
            'Servicio sin regla UI',
            cls.categoria_sin_regla,
            '500.00',
        )
        cls._crear_tarifa(cls.servicio_sin_regla, '500.00')

        cls.servicio_historico = Servicio.objects.create(
            codigo='HISTORICO-UI',
            nombre='Servicio histórico no seleccionable',
            categoria=cls.categoria_psicoterapia,
            activo=False,
            reemplazado_por=cls.servicio_psicoterapia,
            tratamiento_iva=Servicio.IVA_EXENTO,
            precio=Decimal('400.00'),
        )

        cls.paciente.servicio_inicial = cls.servicio_psicoterapia
        cls.paciente.save(update_fields=['servicio_inicial'])
        cls.otro_paciente.servicio_inicial = cls.servicio_psicoterapia
        cls.otro_paciente.save(update_fields=['servicio_inicial'])

        cls.captador = Captador.objects.create(
            tipo=Captador.TIPO_EXTERNO,
            nombre_externo='Organización Referente UI',
            tipo_organizacion=Captador.ORG_ORGANIZACION,
            creado_por=cls.staff,
        )
        cls.captacion = registrar_captacion(
            paciente=cls.paciente,
            codigo=cls.captador.codigo_activo,
            usuario=cls.staff,
            canal='Prueba de interfaz',
        )

    def setUp(self):
        self.client.force_login(self.recepcion)

    @classmethod
    def _crear_categoria(cls, codigo, nombre, orden):
        return CategoriaServicio.objects.create(
            codigo=codigo,
            nombre=nombre,
            orden=orden,
        )

    @classmethod
    def _crear_servicio(cls, codigo, nombre, categoria, precio):
        return Servicio.objects.create(
            codigo=codigo,
            nombre=nombre,
            categoria=categoria,
            activo=True,
            tratamiento_iva=Servicio.IVA_EXENTO,
            precio=Decimal(precio),
        )

    @classmethod
    def _crear_regla(
        cls,
        categoria,
        porcentaje,
        desde=date(2029, 1, 1),
        hasta=None,
    ):
        return crear_regla_beneficio(
            categoria=categoria,
            porcentaje_descuento=Decimal(porcentaje),
            vigente_desde=desde,
            vigente_hasta=hasta,
            actor=cls.staff,
        )

    @classmethod
    def _crear_tarifa(
        cls,
        servicio,
        precio,
        desde=date(2029, 1, 1),
        hasta=None,
    ):
        return TarifaServicio.objects.create(
            servicio=servicio,
            precio_final=Decimal(precio),
            gratuita=False,
            vigente_desde=desde,
            vigente_hasta=hasta,
            estado=TarifaServicio.ESTADO_PUBLICADA,
            origen=TarifaServicio.ORIGEN_DIRECCION,
            tratamiento_iva_snapshot=Servicio.IVA_EXENTO,
            tasa_iva_snapshot=Decimal('0.00'),
            creada_por=cls.staff,
            publicada_por=cls.staff,
            publicada_en=timezone.now(),
        )

    def consultar(self, *, paciente=None, servicio=None, fecha=None):
        paciente = paciente or self.paciente
        servicio = servicio or self.servicio_psicoterapia
        fecha = fecha or self.fecha_base
        return self.client.get(
            reverse('detalle_paciente', args=[paciente.pk]),
            {
                'beneficio_servicio': servicio.pk,
                'beneficio_fecha': fecha.isoformat(),
            },
        )

    def test_01_paciente_referido_muestra_beneficio(self):
        respuesta = self.consultar()
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Beneficio por captación')
        self.assertContains(respuesta, 'Paciente con captación registrada')
        self.assertContains(respuesta, 'Organización Referente UI')

    def test_02_muestra_tarifa_oficial_correcta(self):
        self.assertContains(self.consultar(), '$650.00')

    def test_03_muestra_porcentaje_correcto(self):
        self.assertContains(self.consultar(), '25%')

    def test_04_muestra_descuento_correcto(self):
        self.assertContains(self.consultar(), '-$162.50')

    def test_05_muestra_total_correcto(self):
        self.assertContains(self.consultar(), '$487.50')

    def test_06_segunda_consulta_sigue_mostrando_beneficio(self):
        self.consultar()
        self.assertContains(self.consultar(), '$487.50')

    def test_07_cambio_de_servicio_cambia_beneficio(self):
        psicoterapia = self.consultar()
        medica = self.consultar(servicio=self.servicio_medico)
        self.assertContains(psicoterapia, '25%')
        self.assertContains(medica, '20%')
        self.assertContains(medica, '$720.00')

    def test_08_cambio_de_fecha_cambia_tarifa(self):
        anterior = self.consultar(
            servicio=self.servicio_cambio_tarifa,
            fecha=date(2029, 12, 20),
        )
        actual = self.consultar(
            servicio=self.servicio_cambio_tarifa,
            fecha=date(2030, 1, 20),
        )
        self.assertContains(anterior, '$600.00')
        self.assertContains(actual, '$700.00')

    def test_09_cambio_de_fecha_cambia_regla(self):
        anterior = self.consultar(
            servicio=self.servicio_cambio_regla,
            fecha=date(2029, 12, 20),
        )
        actual = self.consultar(
            servicio=self.servicio_cambio_regla,
            fecha=date(2030, 1, 20),
        )
        self.assertContains(anterior, '10%')
        self.assertContains(actual, '20%')

    def test_10_paciente_sin_captacion_muestra_mensaje_claro(self):
        respuesta = self.consultar(paciente=self.otro_paciente)
        self.assertContains(
            respuesta,
            'Este paciente no tiene una captación registrada.',
        )
        self.assertNotContains(respuesta, 'paciente_no_referido')

    def test_11_servicio_sin_categoria_muestra_mensaje_claro(self):
        respuesta = self.consultar(servicio=self.servicio_sin_categoria)
        self.assertContains(
            respuesta,
            'El servicio aún no tiene una categoría definida.',
        )
        self.assertNotContains(respuesta, 'categoria_no_determinada')

    def test_12_servicio_sin_tarifa_muestra_mensaje_claro(self):
        respuesta = self.consultar(servicio=self.servicio_sin_tarifa)
        self.assertContains(
            respuesta,
            'No existe una tarifa oficial vigente para este servicio.',
        )
        self.assertNotContains(respuesta, 'tarifa_oficial_no_disponible')

    def test_13_categoria_sin_regla_muestra_mensaje_claro(self):
        respuesta = self.consultar(servicio=self.servicio_sin_regla)
        self.assertContains(
            respuesta,
            'No hay un beneficio por captación vigente para esta categoría.',
        )
        self.assertNotContains(respuesta, 'regla_no_disponible')

    def test_14_no_muestra_porcentaje_de_comision(self):
        self.captacion.estado = Captacion.ESTADO_APROBADA
        self.captacion.porcentaje_comision = 7
        self.captacion.save(update_fields=['estado', 'porcentaje_comision'])
        respuesta = self.consultar()
        self.assertNotContains(respuesta, 'Comisión')
        self.assertNotContains(respuesta, '7%')

    def test_15_no_depende_del_estado_aprobado_de_captacion(self):
        self.captacion.estado = Captacion.ESTADO_APROBADA
        self.captacion.save(update_fields=['estado'])
        self.assertContains(self.consultar(), '$487.50')

    def test_16_captacion_pendiente_no_bloquea(self):
        self.assertEqual(self.captacion.estado, Captacion.ESTADO_PENDIENTE)
        self.assertContains(self.consultar(), '$487.50')

    def test_17_captacion_rechazada_no_bloquea(self):
        self.captacion.estado = Captacion.ESTADO_RECHAZADA
        self.captacion.motivo_rechazo = 'Sin comisión para esta captación.'
        self.captacion.save(update_fields=['estado', 'motivo_rechazo'])
        self.assertContains(self.consultar(), '$487.50')

    def test_18_no_modifica_cita_costo(self):
        cita = self.crear_cita(
            servicio=self.servicio_psicoterapia,
            costo=Decimal('437.80'),
        )
        self.consultar(servicio=cita.servicio, fecha=cita.fecha)
        cita.refresh_from_db()
        self.assertEqual(cita.costo, Decimal('437.80'))

    def test_19_no_modifica_servicio_precio(self):
        precio_anterior = self.servicio_psicoterapia.precio
        self.consultar()
        self.servicio_psicoterapia.refresh_from_db()
        self.assertEqual(self.servicio_psicoterapia.precio, precio_anterior)

    def test_20_no_escribe_snapshots(self):
        cita = self.crear_cita(servicio=self.servicio_psicoterapia)
        self.consultar(servicio=cita.servicio, fecha=cita.fecha)
        cita.refresh_from_db()
        self.assertIsNone(cita.precio_servicio_base_snapshot)
        self.assertIsNone(cita.descuento_captacion_porcentaje_snapshot)
        self.assertIsNone(cita.importe_servicio_snapshot)

    def test_21_no_crea_movimiento_economico(self):
        cantidad_anterior = MovimientoEconomicoCita.objects.count()
        self.consultar()
        self.assertEqual(
            MovimientoEconomicoCita.objects.count(),
            cantidad_anterior,
        )

    def test_22_no_crea_comision_captacion(self):
        cantidad_anterior = ComisionCaptacion.objects.count()
        self.consultar()
        self.assertEqual(ComisionCaptacion.objects.count(), cantidad_anterior)

    def test_23_no_modifica_nomina(self):
        cantidades_anteriores = (
            CorteSemanal.objects.count(),
            LineaNomina.objects.count(),
            BonoExtra.objects.count(),
        )
        self.consultar()
        self.assertEqual(
            (
                CorteSemanal.objects.count(),
                LineaNomina.objects.count(),
                BonoExtra.objects.count(),
            ),
            cantidades_anteriores,
        )

    def test_24_no_persiste_resultado_del_simulador(self):
        cantidades_anteriores = (
            Captacion.objects.count(),
            ReglaBeneficioReferido.objects.count(),
            TarifaServicio.objects.count(),
        )
        captacion_anterior = (
            self.captacion.estado,
            self.captacion.porcentaje_comision,
            self.captacion.actualizado_en,
        )
        self.consultar()
        self.consultar()
        self.captacion.refresh_from_db()
        self.assertEqual(
            (
                Captacion.objects.count(),
                ReglaBeneficioReferido.objects.count(),
                TarifaServicio.objects.count(),
            ),
            cantidades_anteriores,
        )
        self.assertEqual(
            (
                self.captacion.estado,
                self.captacion.porcentaje_comision,
                self.captacion.actualizado_en,
            ),
            captacion_anterior,
        )

    def test_25_importes_se_presentan_con_dos_decimales_y_punto(self):
        respuesta = self.consultar()
        self.assertContains(respuesta, '$650.00')
        self.assertContains(respuesta, '-$162.50')
        self.assertContains(respuesta, '$487.50')
        self.assertNotContains(respuesta, '$650,00')

    def test_usuario_sin_permiso_no_ve_el_componente(self):
        usuario = User.objects.create_user(
            username='sin_permiso_beneficios',
            password='pruebas',
        )
        self.client.force_login(usuario)
        respuesta = self.consultar()
        self.assertNotContains(respuesta, 'id="beneficio-referido"')

    def test_selector_excluye_servicios_historicos(self):
        respuesta = self.consultar()
        self.assertNotContains(respuesta, self.servicio_historico.nombre)

    def test_recepcion_no_necesita_permiso_para_administrar_reglas(self):
        self.assertFalse(
            self.recepcion.has_perm('clinica.manage_referral_benefit_rule')
        )
        self.assertContains(self.consultar(), 'Beneficio de referido')
