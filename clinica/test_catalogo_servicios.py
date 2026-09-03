from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from .forms import CitaForm
from .models import CategoriaServicio, Servicio
from .tests_helpers import ClinicaTestDataMixin
from .views import es_servicio_grupal


class CategoriaServicioTests(TestCase):
    def test_codigo_y_nombre_son_unicos(self):
        CategoriaServicio.objects.create(
            codigo='PSICOTERAPIA',
            nombre='Psicoterapia',
        )

        categoria_codigo_repetido = CategoriaServicio(
            codigo='PSICOTERAPIA',
            nombre='Otra categoría',
        )
        with self.assertRaises(ValidationError):
            categoria_codigo_repetido.full_clean()

        categoria_nombre_repetido = CategoriaServicio(
            codigo='OTRA',
            nombre='Psicoterapia',
        )
        with self.assertRaises(ValidationError):
            categoria_nombre_repetido.full_clean()

    def test_ordering_usa_orden_y_nombre(self):
        segunda = CategoriaServicio.objects.create(
            codigo='SEGUNDA',
            nombre='Segunda',
            orden=2,
        )
        primera = CategoriaServicio.objects.create(
            codigo='PRIMERA',
            nombre='Primera',
            orden=1,
        )

        self.assertEqual(list(CategoriaServicio.objects.all()), [primera, segunda])


class ServicioCatalogoEstructuraTests(ClinicaTestDataMixin, TestCase):
    def test_campos_estructurales_permiten_transicion_sin_clasificar(self):
        servicio = Servicio.objects.create(
            nombre='Servicio sin clasificar',
            precio=Decimal('725.00'),
        )

        self.assertIsNone(servicio.codigo)
        self.assertIsNone(servicio.categoria)
        self.assertIsNone(servicio.modalidad)
        self.assertIsNone(servicio.tratamiento_iva)
        self.assertIsNone(servicio.reemplazado_por)
        self.assertTrue(servicio.activo)
        self.assertEqual(servicio.orden, 0)
        self.assertEqual(servicio.precio, Decimal('725.00'))

    def test_codigo_es_unico_cuando_existe(self):
        Servicio.objects.create(nombre='Primero', codigo='TER-IND')
        repetido = Servicio(nombre='Segundo', codigo='TER-IND')

        with self.assertRaises(ValidationError):
            repetido.full_clean()

    def test_reemplazo_no_permite_autorreferencia(self):
        servicio = Servicio.objects.create(nombre='Autorreferencia')
        servicio.activo = False
        servicio.reemplazado_por = servicio

        with self.assertRaises(ValidationError):
            servicio.full_clean()

    def test_reemplazo_no_permite_circularidad(self):
        servicio_a = Servicio.objects.create(nombre='Servicio A')
        servicio_b = Servicio.objects.create(
            nombre='Servicio B',
            activo=False,
            reemplazado_por=servicio_a,
        )
        servicio_a.activo = False
        servicio_a.reemplazado_por = servicio_b

        with self.assertRaises(ValidationError):
            servicio_a.full_clean()

    def test_reemplazo_debe_apuntar_directamente_al_canonico(self):
        canonico = Servicio.objects.create(nombre='Canónico')
        variante = Servicio.objects.create(
            nombre='Variante',
            activo=False,
            reemplazado_por=canonico,
        )
        otra_variante = Servicio(
            nombre='Otra variante',
            activo=False,
            reemplazado_por=variante,
        )

        with self.assertRaises(ValidationError):
            otra_variante.full_clean()

    def test_servicio_reemplazado_debe_ser_inactivo(self):
        canonico = Servicio.objects.create(nombre='Canónico activo')
        variante_activa = Servicio(
            nombre='Variante activa',
            activo=True,
            reemplazado_por=canonico,
        )

        with self.assertRaises(ValidationError):
            variante_activa.full_clean()

    def test_duracion_debe_ser_mayor_que_cero(self):
        servicio = Servicio(nombre='Duración inválida', duracion_minutos=0)

        with self.assertRaises(ValidationError):
            servicio.full_clean()

    def test_nuevos_campos_no_modifican_costo_de_cita(self):
        cita = self.crear_cita(costo=Decimal('450.00'))
        cita.servicio.modalidad = Servicio.MODALIDAD_PAREJA
        cita.servicio.tratamiento_iva = Servicio.IVA_INCLUIDO_16
        cita.servicio.save(update_fields=['modalidad', 'tratamiento_iva'])
        cita.refresh_from_db()

        self.assertEqual(cita.costo, Decimal('450.00'))

    def test_cita_form_conserva_servicios_activos_e_inactivos(self):
        canonico = Servicio.objects.create(nombre='Servicio canónico')
        inactivo = Servicio.objects.create(nombre='Servicio inactivo', activo=False)
        variante = Servicio.objects.create(
            nombre='Variante histórica',
            activo=False,
            reemplazado_por=canonico,
        )

        ids_disponibles = set(
            CitaForm().fields['servicio'].queryset.values_list('id', flat=True)
        )

        self.assertIn(canonico.id, ids_disponibles)
        self.assertIn(inactivo.id, ids_disponibles)
        self.assertIn(variante.id, ids_disponibles)

    def test_regla_legacy_de_servicio_grupal_permanece_por_nombre(self):
        pareja = Servicio(nombre='Terapia de Pareja')
        familiar = Servicio(nombre='Terapia Familiar')
        infantil = Servicio(nombre='Terapia Infantil')
        individual = Servicio(
            nombre='Psicoterapia individual',
            modalidad=Servicio.MODALIDAD_GRUPAL,
        )

        self.assertTrue(es_servicio_grupal(pareja))
        self.assertTrue(es_servicio_grupal(familiar))
        self.assertTrue(es_servicio_grupal(infantil))
        self.assertFalse(es_servicio_grupal(individual))
