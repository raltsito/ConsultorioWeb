from datetime import date, time
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .forms import CitaForm
from .models import CategoriaServicio, Cita, Paciente, Servicio, SolicitudCita
from .services_catalogo_backfill import (
    InventarioCatalogoIncompatible,
    SERVICIOS_ESPERADOS,
    aplicar_backfill_catalogo,
    construir_plan_backfill,
)


INVENTARIO_PRODUCCION = (
    (1, 'Terapia individual', '450.00'),
    (2, 'Terapia infantil', '500.00'),
    (3, 'Terapia de parejas', '600.00'),
    (4, 'Terapia Familiar', '600.00'),
    (5, 'Evaluacin neuropsicolgica', None),
    (6, 'Consulta psiquitrica', None),
    (7, 'Consulta en salud mental', '900.00'),
    (8, 'Consulta nutricional', '780.00'),
    (9, 'Hipnosis', '600.00'),
    (10, 'Psicotanatologa', None),
    (11, 'Consulta Mdica', None),
    (12, 'Terapia de Pareja', '600.00'),
    (13, 'Terapia Infantil', '500.00'),
    (14, 'Evaluación psicológica infantil', None),
    (15, 'Evaluación psicológica', '400.00'),
    (16, 'Evaluación neuropsicológica', '600.00'),
    (17, 'Consulta psiquiátrica', '900.00'),
    (18, 'Psicotanatología', '500.00'),
    (19, 'Consulta Médica', '600.00'),
)


class BackfillCatalogoBase(TestCase):
    def setUp(self):
        Servicio.objects.bulk_create(
            [
                Servicio(
                    id=servicio_id,
                    nombre=nombre,
                    precio=Decimal(precio) if precio is not None else None,
                )
                for servicio_id, nombre, precio in INVENTARIO_PRODUCCION
            ]
        )

    def snapshot_servicios(self):
        return list(
            Servicio.objects.order_by('id').values(
                'id', 'nombre', 'precio', 'codigo', 'categoria_id', 'activo',
                'reemplazado_por_id', 'modalidad', 'duracion_minutos', 'orden',
                'tratamiento_iva',
            )
        )


class BackfillCatalogoPlanTests(BackfillCatalogoBase):
    def test_dry_run_no_modifica_registros(self):
        antes = self.snapshot_servicios()

        plan = construir_plan_backfill()

        self.assertTrue(plan.es_aplicable)
        self.assertTrue(plan.cambios)
        self.assertEqual(self.snapshot_servicios(), antes)
        self.assertEqual(CategoriaServicio.objects.count(), 0)

    def test_comando_por_defecto_es_dry_run(self):
        salida = StringIO()

        call_command('backfill_catalogo_servicios', stdout=salida)

        self.assertIn('BACKFILL CATÁLOGO — DRY RUN', salida.getvalue())
        self.assertIn('NO SE MODIFICÓ NINGÚN DATO', salida.getvalue())
        self.assertEqual(CategoriaServicio.objects.count(), 0)
        self.assertFalse(Servicio.objects.exclude(codigo__isnull=True).exists())

    def test_nombre_incorrecto_aborta(self):
        Servicio.objects.filter(pk=17).update(nombre='Nombre cambiado')
        plan = construir_plan_backfill()
        self.assertFalse(plan.es_aplicable)
        self.assertTrue(any('nombre actual' in item for item in plan.conflictos))

    def test_id_inesperado_aborta(self):
        Servicio.objects.create(id=20, nombre='Servicio inesperado')
        plan = construir_plan_backfill()
        self.assertFalse(plan.es_aplicable)
        self.assertTrue(any('IDs inesperados: [20]' in item for item in plan.conflictos))

    def test_servicio_faltante_aborta(self):
        Servicio.objects.filter(pk=19).delete()
        plan = construir_plan_backfill()
        self.assertFalse(plan.es_aplicable)
        self.assertTrue(any('IDs faltantes: [19]' in item for item in plan.conflictos))

    def test_codigo_preexistente_distinto_aborta(self):
        Servicio.objects.filter(pk=17).update(codigo='MED-PSIQUIATRIA')
        plan = construir_plan_backfill()
        self.assertFalse(plan.es_aplicable)
        self.assertTrue(any('codigo actual' in item for item in plan.conflictos))

    def test_categoria_preexistente_distinta_aborta(self):
        categoria = CategoriaServicio.objects.create(
            codigo='MANUAL', nombre='Captura manual'
        )
        Servicio.objects.filter(pk=17).update(categoria=categoria)
        plan = construir_plan_backfill()
        self.assertFalse(plan.es_aplicable)
        self.assertTrue(any('categoria actual' in item for item in plan.conflictos))

    def test_definicion_preexistente_de_categoria_en_conflicto_aborta(self):
        CategoriaServicio.objects.create(
            codigo='PSICOTERAPIA',
            nombre='Nombre no autorizado',
            orden=10,
        )

        plan = construir_plan_backfill()

        self.assertFalse(plan.es_aplicable)
        self.assertTrue(any('Categoría PSICOTERAPIA' in item for item in plan.conflictos))

    def test_precio_distinto_es_contextual_y_no_aborta(self):
        Servicio.objects.filter(pk=1).update(precio=Decimal('999.00'))

        plan = construir_plan_backfill()

        self.assertTrue(plan.es_aplicable)

    def test_duracion_y_orden_preexistentes_abortan(self):
        Servicio.objects.filter(pk=1).update(duracion_minutos=60, orden=1)
        plan = construir_plan_backfill()
        self.assertFalse(plan.es_aplicable)
        self.assertTrue(any('duracion_minutos' in item for item in plan.conflictos))
        self.assertTrue(any('orden contiene' in item for item in plan.conflictos))

    def test_comando_aborta_inventario_incompatible_sin_escribir(self):
        Servicio.objects.filter(pk=19).delete()
        antes = self.snapshot_servicios()
        salida = StringIO()

        with self.assertRaises(CommandError):
            call_command('backfill_catalogo_servicios', stdout=salida)

        self.assertIn('NO SE MODIFICÓ NINGÚN DATO', salida.getvalue())
        self.assertEqual(self.snapshot_servicios(), antes)
        self.assertEqual(CategoriaServicio.objects.count(), 0)


class BackfillCatalogoApplyTests(BackfillCatalogoBase):
    def test_comando_apply_ejecuta_backfill(self):
        salida = StringIO()

        call_command('backfill_catalogo_servicios', apply=True, stdout=salida)

        self.assertIn('BACKFILL APLICADO CORRECTAMENTE', salida.getvalue())
        self.assertEqual(CategoriaServicio.objects.count(), 7)
        self.assertEqual(
            Servicio.objects.exclude(codigo__isnull=True).count(),
            19,
        )

    def test_apply_crea_categorias_y_clasifica_matriz_completa(self):
        precios_antes = dict(Servicio.objects.values_list('id', 'precio'))
        aplicar_backfill_catalogo()

        self.assertEqual(CategoriaServicio.objects.count(), 7)
        self.assertEqual(
            set(CategoriaServicio.objects.values_list('codigo', flat=True)),
            {'PSICOTERAPIA', 'MEDICA', 'FISIOTERAPIA', 'NUTRICION',
             'HIPNOSIS', 'EVALUACION', 'OTROS'},
        )
        esperados_por_id = {item.id: item for item in SERVICIOS_ESPERADOS}
        for servicio in Servicio.objects.select_related('categoria').order_by('id'):
            esperado = esperados_por_id[servicio.id]
            self.assertEqual(servicio.codigo, esperado.codigo)
            self.assertEqual(servicio.activo, esperado.activo)
            self.assertEqual(servicio.reemplazado_por_id, esperado.reemplazado_por_id)
            self.assertEqual(servicio.modalidad, esperado.modalidad)
            self.assertEqual(servicio.tratamiento_iva, esperado.tratamiento_iva)
            self.assertEqual(
                servicio.categoria.codigo if servicio.categoria else None,
                esperado.categoria_codigo,
            )
            self.assertIsNone(servicio.duracion_minutos)
            self.assertEqual(servicio.orden, 0)
            self.assertEqual(servicio.precio, precios_antes[servicio.id])
        self.assertEqual(Servicio.objects.values('codigo').distinct().count(), 19)

    def test_reemplazos_y_campos_intencionalmente_pendientes(self):
        aplicar_backfill_catalogo()
        self.assertEqual(
            dict(Servicio.objects.filter(activo=False).values_list(
                'id', 'reemplazado_por_id'
            )),
            {5: 16, 6: 17, 10: 18, 11: 19, 12: 3, 13: 2},
        )
        self.assertIsNone(Servicio.objects.get(pk=18).categoria_id)
        self.assertIsNone(Servicio.objects.get(pk=10).categoria_id)
        self.assertIsNone(Servicio.objects.get(pk=2).modalidad)
        self.assertIsNone(Servicio.objects.get(pk=13).modalidad)

    def test_iva_exento_es_exclusivo_de_psiquiatria(self):
        aplicar_backfill_catalogo()
        self.assertEqual(
            set(Servicio.objects.filter(
                tratamiento_iva=Servicio.IVA_EXENTO
            ).values_list('id', flat=True)),
            {6, 17},
        )
        self.assertEqual(
            Servicio.objects.filter(
                tratamiento_iva=Servicio.IVA_INCLUIDO_16
            ).count(),
            17,
        )

    def test_segunda_ejecucion_es_idempotente(self):
        aplicar_backfill_catalogo()
        primera_ejecucion = self.snapshot_servicios()
        plan = aplicar_backfill_catalogo()
        self.assertFalse(plan.cambios)
        self.assertFalse(plan.categorias_a_crear)
        self.assertEqual(self.snapshot_servicios(), primera_ejecucion)
        self.assertEqual(CategoriaServicio.objects.count(), 7)

    def test_fks_historicas_y_costo_de_cita_no_cambian(self):
        historico = Servicio.objects.get(pk=12)
        paciente = Paciente.objects.create(
            nombre='Paciente histórico', fecha_nacimiento=date(1990, 1, 1),
            sexo='Femenino', telefono='5550000000', servicio_inicial=historico,
        )
        cita = Cita.objects.create(
            paciente=paciente, fecha=date(2030, 1, 7), hora=time(10, 0),
            servicio=historico, costo=Decimal('337.50'),
        )
        solicitud = SolicitudCita.objects.create(
            paciente_nombre='Paciente histórico', telefono='5550000000',
            fecha_deseada=date(2030, 1, 8), paciente=paciente,
            servicio=historico,
        )

        aplicar_backfill_catalogo()
        paciente.refresh_from_db()
        cita.refresh_from_db()
        solicitud.refresh_from_db()
        self.assertEqual(paciente.servicio_inicial_id, 12)
        self.assertEqual(cita.servicio_id, 12)
        self.assertEqual(cita.costo, Decimal('337.50'))
        self.assertEqual(solicitud.servicio_id, 12)

    def test_cita_form_conserva_servicios_inactivos(self):
        aplicar_backfill_catalogo()
        ids_formulario = set(
            CitaForm().fields['servicio'].queryset.values_list('id', flat=True)
        )
        self.assertEqual(ids_formulario, set(range(1, 20)))

    def test_error_durante_apply_revierte_todo(self):
        antes = self.snapshot_servicios()
        guardar_original = Servicio.save

        def guardar_con_error(instancia, *args, **kwargs):
            if instancia.pk == 19:
                raise RuntimeError('Error controlado en una línea')
            return guardar_original(instancia, *args, **kwargs)

        with patch.object(
            Servicio, 'save', autospec=True, side_effect=guardar_con_error
        ):
            with self.assertRaises(RuntimeError):
                aplicar_backfill_catalogo()

        self.assertEqual(self.snapshot_servicios(), antes)
        self.assertEqual(CategoriaServicio.objects.count(), 0)

    def test_apply_con_conflicto_aborta_sin_cambios(self):
        Servicio.objects.filter(pk=17).update(codigo='CONFLICTO')
        antes = self.snapshot_servicios()
        with self.assertRaises(InventarioCatalogoIncompatible):
            aplicar_backfill_catalogo()
        self.assertEqual(self.snapshot_servicios(), antes)
        self.assertEqual(CategoriaServicio.objects.count(), 0)
