import inspect
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import resolve, reverse
from django.utils import timezone

from ventas.models import Captacion, Captador

from . import views
from .forms import CitaForm
from .models import (
    CategoriaServicio,
    Cita,
    MovimientoEconomicoCita,
    ReglaBeneficioReferido,
    Servicio,
)
from .services_beneficios import (
    crear_regla_beneficio,
    obtener_regla_beneficio_vigente,
    programar_regla_beneficio,
)
from .tests_helpers import ClinicaTestDataMixin


class ProteccionFlujoAgendaReferidosTests(ClinicaTestDataMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.captador = Captador.objects.create(
            tipo=Captador.TIPO_EXTERNO,
            nombre_externo='Organización Referente',
            tipo_organizacion=Captador.ORG_ORGANIZACION,
            creado_por=cls.staff,
        )
        cls.captacion = Captacion.objects.create(
            paciente=cls.paciente,
            captador=cls.captador,
            codigo=cls.captador.codigo_activo,
            registrado_por=cls.staff,
            estado=Captacion.ESTADO_APROBADA,
            captador_nombre_snapshot=cls.captador.nombre_display,
            captador_tipo_snapshot=cls.captador.clasificacion_display,
            porcentaje_comision=5,
            decidido_por=cls.staff,
            decidido_en=timezone.now(),
        )

    def datos_cita(self, *, costo='512.34', estatus=Cita.ESTATUS_CONFIRMADA):
        return {
            'paciente': str(self.paciente.pk),
            'fecha': self.fecha.isoformat(),
            'hora': self.hora.strftime('%H:%M'),
            'tipo_paciente': Cita.TIPO_REFERIDO,
            'division': str(self.division.pk),
            'consultorio': str(self.consultorio.pk),
            'servicio': str(self.servicio.pk),
            'terapeuta': str(self.terapeuta.pk),
            'costo': costo,
            'metodo_pago': 'Efectivo',
            'estatus': estatus,
            'folio_fiscal': '',
            'notas': '',
            'tiene_descuento': 'false',
        }

    def assert_sin_datos_financieros_automaticos(self, cita):
        self.assertIsNone(cita.precio_servicio_base_snapshot)
        self.assertIsNone(cita.descuento_captacion_porcentaje_snapshot)
        self.assertIsNone(cita.importe_servicio_snapshot)
        self.assertFalse(MovimientoEconomicoCita.objects.exists())

    def test_definicion_efectiva_de_agendar_no_invoca_pricing_antiguo(self):
        funcion_resuelta = resolve(
            reverse('agendar_cita', args=[self.paciente.pk])
        ).func

        self.assertIs(funcion_resuelta, views.agendar_cita)
        self.assertNotIn(
            'aplicar_costo_captacion_a_cita',
            inspect.getsource(funcion_resuelta),
        )

    def test_crear_cita_referida_conserva_costo_manual_y_no_aplica_25(self):
        self.client.force_login(self.staff)
        with (
            patch('clinica.views.sincronizar_google_sheet'),
            patch('builtins.print'),
        ):
            response = self.client.post(
                reverse('agendar_cita', args=[self.paciente.pk]),
                self.datos_cita(),
            )

        self.assertEqual(response.status_code, 302)
        cita = Cita.objects.get()
        self.assertEqual(cita.costo, Decimal('512.34'))
        self.assert_sin_datos_financieros_automaticos(cita)

    def test_editar_cita_referida_conserva_el_nuevo_costo_manual(self):
        cita = self.crear_cita(costo=Decimal('410.00'))
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('editar_cita', args=[cita.pk]),
            self.datos_cita(costo='438.75'),
        )

        self.assertEqual(response.status_code, 302)
        cita.refresh_from_db()
        self.assertEqual(cita.costo, Decimal('438.75'))
        self.assert_sin_datos_financieros_automaticos(cita)

    def test_checkout_referido_conserva_el_costo_capturado(self):
        cita = self.crear_cita(costo=Decimal('500.00'))
        self.client.force_login(self.usuario_terapeuta)
        response = self.client.post(
            reverse('checkout_cita', args=[cita.pk]),
            {
                'estatus': Cita.ESTATUS_SI_ASISTIO,
                'metodo_pago': 'Efectivo',
                'costo': '421.80',
            },
        )

        self.assertEqual(response.status_code, 302)
        cita.refresh_from_db()
        self.assertEqual(cita.costo, Decimal('421.80'))
        self.assertEqual(cita.estatus, Cita.ESTATUS_SI_ASISTIO)
        self.assert_sin_datos_financieros_automaticos(cita)

    def test_cita_form_clean_no_recalcula_el_costo(self):
        form = CitaForm(data=self.datos_cita(costo='487.65'))

        self.assertTrue(form.is_valid(), form.errors)
        cita = form.save(commit=False)
        self.assertEqual(cita.costo, Decimal('487.65'))
        self.assertIsNone(cita.precio_servicio_base_snapshot)
        self.assertIsNone(cita.descuento_captacion_porcentaje_snapshot)
        self.assertIsNone(cita.importe_servicio_snapshot)

    def test_bitacora_lee_directamente_cita_costo(self):
        self.crear_cita(
            costo=Decimal('333.25'),
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse('bitacora_diaria'),
            {'fecha': self.fecha.isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['monto_dia'], Decimal('333.25'))
        self.assertEqual(response.context['citas'][0].costo, Decimal('333.25'))

    def test_reporte_general_lee_directamente_cita_costo(self):
        self.crear_cita(
            costo=Decimal('376.40'),
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse('reporte_general'),
            {
                'fecha_inicio': self.fecha.isoformat(),
                'fecha_fin': self.fecha.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['monto_total'], Decimal('376.40'))
        self.assertEqual(response.context['citas'][0].costo, Decimal('376.40'))


class ReglaBeneficioReferidoModeloServicioTests(
    ClinicaTestDataMixin,
    TestCase,
):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.categoria_psicoterapia = CategoriaServicio.objects.create(
            codigo='PSICOTERAPIA',
            nombre='Psicoterapia',
            orden=1,
        )
        cls.categoria_medica = CategoriaServicio.objects.create(
            codigo='MEDICA',
            nombre='Médica',
            orden=2,
        )
        cls.servicio_categorizado = Servicio.objects.create(
            nombre='Consulta categorizada',
            codigo='MED-CONS',
            categoria=cls.categoria_medica,
            precio=Decimal('850.00'),
        )

    def crear_regla(
        self,
        *,
        categoria=None,
        porcentaje='25.00',
        desde=None,
        hasta=None,
        activo=True,
    ):
        return crear_regla_beneficio(
            categoria=categoria or self.categoria_psicoterapia,
            porcentaje_descuento=Decimal(porcentaje),
            vigente_desde=desde or timezone.localdate(),
            vigente_hasta=hasta,
            activo=activo,
            actor=self.staff,
        )

    def test_porcentaje_25_es_valido(self):
        regla = self.crear_regla(porcentaje='25.00')
        self.assertEqual(regla.porcentaje_descuento, Decimal('25.00'))

    def test_porcentaje_20_es_valido(self):
        regla = self.crear_regla(
            categoria=self.categoria_medica,
            porcentaje='20.00',
        )
        self.assertEqual(regla.porcentaje_descuento, Decimal('20.00'))

    def test_porcentaje_negativo_es_rechazado(self):
        with self.assertRaises(ValidationError):
            self.crear_regla(porcentaje='-0.01')

    def test_porcentaje_mayor_a_100_es_rechazado(self):
        with self.assertRaises(ValidationError):
            self.crear_regla(porcentaje='100.01')

    def test_fecha_final_anterior_a_inicial_es_rechazada(self):
        hoy = timezone.localdate()
        with self.assertRaises(ValidationError):
            self.crear_regla(desde=hoy, hasta=hoy - timedelta(days=1))

    def test_regla_vigente_se_obtiene_por_categoria_y_fecha(self):
        hoy = timezone.localdate()
        regla = self.crear_regla(
            desde=hoy - timedelta(days=2),
            hasta=hoy + timedelta(days=2),
        )
        encontrada = obtener_regla_beneficio_vigente(
            categoria=self.categoria_psicoterapia,
            fecha=hoy,
        )
        self.assertEqual(encontrada, regla)

    def test_regla_futura_no_aplica_antes_de_su_fecha(self):
        hoy = timezone.localdate()
        self.crear_regla(desde=hoy + timedelta(days=1))
        self.assertIsNone(
            obtener_regla_beneficio_vigente(
                categoria=self.categoria_psicoterapia,
                fecha=hoy,
            )
        )

    def test_regla_historica_deja_de_aplicar_al_terminar(self):
        hoy = timezone.localdate()
        self.crear_regla(
            desde=hoy - timedelta(days=10),
            hasta=hoy - timedelta(days=1),
        )
        self.assertIsNone(
            obtener_regla_beneficio_vigente(
                categoria=self.categoria_psicoterapia,
                fecha=hoy,
            )
        )

    def test_reglas_activas_superpuestas_son_rechazadas(self):
        hoy = timezone.localdate()
        self.crear_regla(desde=hoy, hasta=hoy + timedelta(days=10))
        with self.assertRaises(ValidationError):
            self.crear_regla(
                desde=hoy + timedelta(days=5),
                hasta=hoy + timedelta(days=15),
            )

    def test_reglas_consecutivas_sin_solapamiento_son_validas(self):
        hoy = timezone.localdate()
        primera = self.crear_regla(desde=hoy, hasta=hoy + timedelta(days=9))
        segunda = self.crear_regla(
            porcentaje='20.00',
            desde=hoy + timedelta(days=10),
        )
        self.assertEqual(primera.vigente_hasta + timedelta(days=1), segunda.vigente_desde)

    def test_categorias_distintas_pueden_tener_vigencias_simultaneas(self):
        hoy = timezone.localdate()
        psicoterapia = self.crear_regla(desde=hoy)
        medica = self.crear_regla(
            categoria=self.categoria_medica,
            porcentaje='20.00',
            desde=hoy,
        )
        self.assertNotEqual(psicoterapia.categoria_servicio, medica.categoria_servicio)

    def test_categoria_sin_regla_devuelve_none(self):
        self.assertIsNone(
            obtener_regla_beneficio_vigente(
                categoria=self.categoria_medica,
                fecha=timezone.localdate(),
            )
        )

    def test_resolucion_no_busca_por_nombre_del_servicio(self):
        categoria_sin_regla = CategoriaServicio.objects.create(
            codigo='SIN-REGLA',
            nombre='Sin regla',
        )
        Servicio.objects.create(
            nombre='PSICOTERAPIA promocional',
            categoria=categoria_sin_regla,
        )
        self.crear_regla(categoria=self.categoria_psicoterapia)
        self.assertIsNone(
            obtener_regla_beneficio_vigente(
                categoria=categoria_sin_regla,
                fecha=timezone.localdate(),
            )
        )

    def test_crear_regla_no_modifica_categoria_servicio(self):
        valores_anteriores = {
            'codigo': self.categoria_psicoterapia.codigo,
            'nombre': self.categoria_psicoterapia.nombre,
            'activo': self.categoria_psicoterapia.activo,
            'orden': self.categoria_psicoterapia.orden,
        }
        self.crear_regla()
        self.categoria_psicoterapia.refresh_from_db()
        self.assertEqual(
            valores_anteriores,
            {
                'codigo': self.categoria_psicoterapia.codigo,
                'nombre': self.categoria_psicoterapia.nombre,
                'activo': self.categoria_psicoterapia.activo,
                'orden': self.categoria_psicoterapia.orden,
            },
        )

    def test_crear_regla_no_modifica_servicio_precio(self):
        self.crear_regla(categoria=self.categoria_medica, porcentaje='20.00')
        self.servicio_categorizado.refresh_from_db()
        self.assertEqual(self.servicio_categorizado.precio, Decimal('850.00'))

    def test_crear_regla_no_modifica_cita_costo(self):
        cita = self.crear_cita(costo=Decimal('437.00'))
        self.crear_regla()
        cita.refresh_from_db()
        self.assertEqual(cita.costo, Decimal('437.00'))

    def test_programar_cambio_cierra_regla_anterior_y_conserva_historico(self):
        hoy = timezone.localdate()
        anterior = self.crear_regla(desde=hoy - timedelta(days=10))
        inicio_nuevo = hoy + timedelta(days=5)

        nueva = programar_regla_beneficio(
            categoria=self.categoria_psicoterapia,
            porcentaje_descuento=Decimal('20.00'),
            vigente_desde=inicio_nuevo,
            actor=self.staff,
        )

        anterior.refresh_from_db()
        self.assertEqual(anterior.vigente_hasta, inicio_nuevo - timedelta(days=1))
        self.assertEqual(nueva.vigente_desde, inicio_nuevo)
        self.assertEqual(ReglaBeneficioReferido.objects.count(), 2)


class BeneficiosReferidosUITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.visor = User.objects.create_user(username='visor_beneficios')
        cls.gestor = User.objects.create_user(username='gestor_beneficios')
        cls.recepcion = User.objects.create_user(username='recepcion_beneficios')
        cls.catalogo_sin_beneficios = User.objects.create_user(
            username='catalogo_sin_beneficios'
        )
        cls.sin_permiso = User.objects.create_user(username='sin_beneficios')
        cls.categoria = CategoriaServicio.objects.create(
            codigo='PSICOTERAPIA',
            nombre='Psicoterapia',
        )

        cls._asignar(cls.visor, 'view_referral_benefit_rule')
        cls._asignar(
            cls.gestor,
            'view_referral_benefit_rule',
            'manage_referral_benefit_rule',
            'view_service_catalog',
        )
        cls._asignar(cls.recepcion, 'view_service_catalog')
        cls._asignar(cls.catalogo_sin_beneficios, 'view_service_catalog')

    @classmethod
    def _asignar(cls, usuario, *codenames):
        usuario.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label='clinica',
                codename__in=codenames,
            )
        )

    def datos_regla(self, *, accion='registrar', desde=None, porcentaje='25.00'):
        return {
            'categoria_servicio': str(self.categoria.pk),
            'porcentaje_descuento': porcentaje,
            'vigente_desde': (desde or timezone.localdate()).isoformat(),
            'vigente_hasta': '',
            'activo': 'on',
            'accion': accion,
        }

    def test_usuario_con_permiso_puede_ver_administracion(self):
        self.client.force_login(self.visor)
        response = self.client.get(reverse('beneficios_referidos'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Beneficios de referidos')
        self.assertNotContains(response, 'Registrar o programar una regla')

    def test_usuario_sin_permiso_recibe_403(self):
        self.client.force_login(self.sin_permiso)
        response = self.client.get(reverse('beneficios_referidos'))
        self.assertEqual(response.status_code, 403)

    def test_gestor_no_staff_puede_registrar_regla(self):
        self.assertFalse(self.gestor.is_staff)
        self.client.force_login(self.gestor)
        response = self.client.post(
            reverse('beneficios_referidos'),
            self.datos_regla(),
        )
        self.assertRedirects(response, reverse('beneficios_referidos'))
        regla = ReglaBeneficioReferido.objects.get()
        self.assertEqual(regla.creado_por, self.gestor)
        self.assertEqual(regla.aprobado_por, self.gestor)

    def test_gestor_puede_programar_cambio_futuro(self):
        hoy = timezone.localdate()
        crear_regla_beneficio(
            categoria=self.categoria,
            porcentaje_descuento=Decimal('25.00'),
            vigente_desde=hoy - timedelta(days=10),
            actor=self.gestor,
        )
        inicio_nuevo = hoy + timedelta(days=5)
        self.client.force_login(self.gestor)

        response = self.client.post(
            reverse('beneficios_referidos'),
            self.datos_regla(
                accion='programar',
                desde=inicio_nuevo,
                porcentaje='20.00',
            ),
        )

        self.assertRedirects(response, reverse('beneficios_referidos'))
        self.assertEqual(ReglaBeneficioReferido.objects.count(), 2)
        anterior = ReglaBeneficioReferido.objects.order_by('vigente_desde').first()
        self.assertEqual(anterior.vigente_hasta, inicio_nuevo - timedelta(days=1))

    def test_recepcion_sin_permiso_gestion_no_puede_modificar(self):
        self.client.force_login(self.recepcion)
        response = self.client.post(
            reverse('beneficios_referidos'),
            self.datos_regla(),
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ReglaBeneficioReferido.objects.exists())

    def test_pantalla_separa_reglas_actuales_proximas_e_historicas(self):
        hoy = timezone.localdate()
        actual = crear_regla_beneficio(
            categoria=self.categoria,
            porcentaje_descuento=Decimal('25.00'),
            vigente_desde=hoy - timedelta(days=10),
            actor=self.gestor,
        )
        futura = programar_regla_beneficio(
            categoria=self.categoria,
            porcentaje_descuento=Decimal('20.00'),
            vigente_desde=hoy + timedelta(days=10),
            actor=self.gestor,
        )
        historica = crear_regla_beneficio(
            categoria=self.categoria,
            porcentaje_descuento=Decimal('15.00'),
            vigente_desde=hoy - timedelta(days=30),
            vigente_hasta=hoy - timedelta(days=20),
            activo=False,
            actor=self.gestor,
        )
        self.client.force_login(self.visor)

        response = self.client.get(reverse('beneficios_referidos'))

        self.assertIn(actual, response.context['reglas_actuales'])
        self.assertIn(futura, response.context['reglas_proximas'])
        self.assertIn(historica, response.context['reglas_historicas'])

    def test_catalogo_muestra_acceso_solo_con_permiso_de_beneficios(self):
        self.client.force_login(self.gestor)
        con_permiso = self.client.get(reverse('precios_servicios'))
        self.assertContains(con_permiso, reverse('beneficios_referidos'))

        self.client.force_login(self.catalogo_sin_beneficios)
        sin_permiso = self.client.get(reverse('precios_servicios'))
        self.assertNotContains(sin_permiso, reverse('beneficios_referidos'))
