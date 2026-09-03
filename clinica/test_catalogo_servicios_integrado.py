from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    CategoriaServicio,
    PropuestaTarifaDetalle,
    PropuestaTarifas,
    Servicio,
    TarifaServicio,
)
from .services_tarifas import publicar_tarifa_servicio


PERMISOS_RECEPCION = (
    'view_service_catalog',
    'propose_service_tariff',
    'submit_service_tariff_proposal',
)
PERMISOS_DIRECCION = (
    'view_service_catalog',
    'review_service_tariff_proposal',
    'publish_service_tariff',
    'cancel_future_service_tariff',
)


class CatalogoServiciosIntegradoBase(TestCase):
    def setUp(self):
        self.recepcion = User.objects.create_user(username='recepcion_catalogo')
        self.direccion = User.objects.create_user(username='direccion_catalogo')
        self.sin_permiso = User.objects.create_user(username='sin_catalogo')
        self._asignar(self.recepcion, PERMISOS_RECEPCION)
        self._asignar(self.direccion, PERMISOS_DIRECCION)
        self.categoria = CategoriaServicio.objects.create(
            codigo='PSICO',
            nombre='Psicoterapia',
        )
        self.servicio = Servicio.objects.create(
            nombre='Terapia individual',
            codigo='PSICO-IND',
            categoria=self.categoria,
            modalidad=Servicio.MODALIDAD_INDIVIDUAL,
            activo=True,
            tratamiento_iva=Servicio.IVA_INCLUIDO_16,
            precio=Decimal('600.00'),
        )

    def _asignar(self, usuario, codenames):
        usuario.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label='clinica',
                codename__in=codenames,
            )
        )

    def publicar(self, precio, desde, servicio=None):
        return publicar_tarifa_servicio(
            servicio=servicio or self.servicio,
            precio_final=Decimal(precio),
            gratuita=False,
            vigente_desde=desde,
            actor=self.direccion,
            origen=TarifaServicio.ORIGEN_DIRECCION,
        )


class NavegacionCatalogoTests(CatalogoServiciosIntegradoBase):
    def test_home_muestra_un_solo_catalogo_con_permiso_granular(self):
        self.client.force_login(self.recepcion)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<span class="dock-label">Precios</span>', html=True)
        self.assertContains(response, 'Tarifas de servicios')
        self.assertContains(response, reverse('precios_servicios'))
        self.assertContains(response, 'Catálogo de terapeutas')
        self.assertContains(response, 'Directorio de terapeutas')
        self.assertNotContains(
            response,
            '<span class="dock-label">Catálogo</span>',
            html=True,
        )

    def test_home_oculta_catalogo_sin_permiso_aunque_directorio_permanece(self):
        self.client.force_login(self.sin_permiso)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            '<span class="dock-label">Precios</span>',
            html=True,
        )
        self.assertContains(response, 'Catálogo de terapeutas')

    def test_catalogo_canonico_exige_permiso_backend(self):
        self.client.force_login(self.sin_permiso)
        self.assertEqual(
            self.client.get(reverse('precios_servicios')).status_code,
            403,
        )
        self.client.force_login(self.recepcion)
        self.assertEqual(
            self.client.get(reverse('precios_servicios')).status_code,
            200,
        )

    def test_catalogo_temporal_redirige_al_canonico(self):
        self.client.force_login(self.recepcion)

        response = self.client.get(reverse('catalogo_servicios_tarifas'))

        self.assertRedirects(response, reverse('precios_servicios'))


class PantallaCatalogoTests(CatalogoServiciosIntegradoBase):
    def test_mis_propuestas_permanece_cerrado_y_limita_resultados_recientes(self):
        for indice in range(5):
            PropuestaTarifas.objects.create(
                vigencia_propuesta=timezone.localdate() + timedelta(days=indice),
                observaciones=f'Propuesta {indice}',
                creada_por=self.recepcion,
            )
        self.client.force_login(self.recepcion)

        response = self.client.get(reverse('precios_servicios'))

        self.assertContains(response, 'Mis propuestas')
        self.assertContains(response, 'Ver propuestas')
        self.assertContains(response, 'Ver todas')
        self.assertContains(response, 'id="mis-propuestas-panel"')
        self.assertNotContains(response, 'collapse show')
        self.assertEqual(response.context['total_mis_propuestas_catalogo'], 5)
        self.assertEqual(len(response.context['mis_propuestas_catalogo']), 3)

    def test_tabla_principal_muestra_solo_tarifa_oficial_actual_y_penalizacion(self):
        hoy = timezone.localdate()
        self.publicar('650.00', hoy)
        self.publicar('700.00', hoy + timedelta(days=30))
        exento = Servicio.objects.create(
            nombre='Consulta psiquiátrica',
            codigo='MED-PSIQ',
            activo=True,
            tratamiento_iva=Servicio.IVA_EXENTO,
            precio=Decimal('900.00'),
        )
        self.publicar('900.00', hoy, servicio=exento)
        Servicio.objects.create(nombre='Servicio por clasificar', activo=True)
        self.client.force_login(self.recepcion)

        response = self.client.get(reverse('precios_servicios'))

        self.assertContains(response, 'Precios de Servicios')
        self.assertNotContains(response, 'Catálogo de Servicios')
        self.assertContains(response, 'Terapia individual')
        self.assertContains(response, '650')
        self.assertContains(response, '560.34')
        self.assertContains(response, '89.66')
        self.assertContains(response, '325.00')
        self.assertContains(response, 'Exento')
        self.assertContains(response, '900')
        self.assertContains(response, '450.00')
        self.assertContains(response, 'Tarifa pendiente')
        self.assertContains(response, 'Pendiente')
        self.assertNotContains(response, '$700.00')
        self.assertNotContains(response, 'Referencia legacy')
        self.assertNotContains(response, 'Sin programación')
        self.assertNotContains(response, 'Sin código')
        self.assertNotContains(response, '<th>Estado</th>', html=True)
        self.assertNotContains(response, '<th>Próxima tarifa</th>', html=True)
        self.assertNotContains(response, '>Administrar<')
        self.assertNotContains(response, 'Tratamiento fiscal pendiente')

    def test_historicos_no_saturan_vista_normal_y_son_consultables(self):
        historico = Servicio.objects.create(
            nombre='Terapia individual anterior',
            codigo='PSICO-IND-OLD',
            activo=False,
            reemplazado_por=self.servicio,
            tratamiento_iva=Servicio.IVA_INCLUIDO_16,
        )
        self.client.force_login(self.recepcion)

        normal = self.client.get(reverse('precios_servicios'))
        historicos = self.client.get(
            reverse('precios_servicios'),
            {'estado': 'historicos'},
        )

        self.assertNotContains(normal, historico.nombre)
        self.assertContains(historicos, historico.nombre)
        self.assertContains(historicos, 'Histórico')
        self.assertNotContains(historicos, 'Reemplazado por Terapia individual')

    def test_filtros_de_busqueda_categoria_y_estado(self):
        otro = Servicio.objects.create(
            nombre='Consulta nutricional',
            codigo='NUT-CONS',
            activo=True,
            tratamiento_iva=Servicio.IVA_INCLUIDO_16,
        )
        self.publicar('650.00', timezone.localdate())
        self.client.force_login(self.recepcion)

        por_busqueda = self.client.get(
            reverse('precios_servicios'),
            {'q': 'PSICO-IND'},
        )
        por_categoria = self.client.get(
            reverse('precios_servicios'),
            {'categoria': self.categoria.pk},
        )

        self.assertContains(por_busqueda, self.servicio.nombre)
        self.assertNotContains(por_busqueda, otro.nombre)
        self.assertContains(por_categoria, self.servicio.nombre)
        self.assertNotContains(por_categoria, otro.nombre)

    def test_categoria_invalida_no_rompe_catalogo(self):
        self.client.force_login(self.recepcion)

        response = self.client.get(
            reverse('precios_servicios'),
            {'categoria': 'valor-manipulado'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.servicio.nombre)

    def test_ficha_muestra_general_historial_propuestas_y_empresas_bloqueadas(self):
        hoy = timezone.localdate()
        tarifa = self.publicar('650.00', hoy)
        propuesta = PropuestaTarifas.objects.create(
            vigencia_propuesta=hoy + timedelta(days=60),
            creada_por=self.recepcion,
        )
        PropuestaTarifaDetalle.objects.create(
            propuesta=propuesta,
            servicio=self.servicio,
            tarifa_actual=tarifa,
            precio_actual_snapshot=tarifa.precio_final,
            gratuita_actual_snapshot=False,
            precio_propuesto=Decimal('725.00'),
        )
        self.client.force_login(self.recepcion)

        response = self.client.get(
            reverse('servicio_catalogo_detalle', args=[self.servicio.pk])
        )

        self.assertContains(response, 'General')
        self.assertContains(response, 'Tarifas')
        self.assertContains(response, 'Empresas')
        self.assertContains(response, 'Próximamente')
        self.assertContains(response, 'Histórico de tarifas')
        self.assertContains(response, 'Propuestas relacionadas')
        self.assertContains(response, 'Compatibilidad temporal')
        self.assertContains(response, 'Precio anterior del sistema')
        self.assertContains(response, 'Penalización (50%)')


class FlujosDesdeCatalogoTests(CatalogoServiciosIntegradoBase):
    def test_recepcion_ve_propuesta_pero_no_acciones_de_direccion(self):
        self.client.force_login(self.recepcion)

        response = self.client.get(reverse('precios_servicios'))

        self.assertContains(response, 'Proponer tarifas')
        self.assertNotContains(response, 'Registrar tarifa')
        self.assertNotContains(response, '>Pendientes<')
        self.assertEqual(
            self.client.get(reverse('tarifa_servicio_directa')).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse('propuestas_tarifas_pendientes')).status_code,
            403,
        )

    def test_ficha_de_recepcion_no_expone_propuestas_ajenas(self):
        otra_recepcion = User.objects.create_user(username='otra_recepcion')
        self._asignar(otra_recepcion, PERMISOS_RECEPCION)
        propuesta_ajena = PropuestaTarifas.objects.create(
            vigencia_propuesta=timezone.localdate(),
            creada_por=otra_recepcion,
        )
        PropuestaTarifaDetalle.objects.create(
            propuesta=propuesta_ajena,
            servicio=self.servicio,
            precio_propuesto=Decimal('777.00'),
        )
        self.client.force_login(self.recepcion)

        response = self.client.get(
            reverse('servicio_catalogo_detalle', args=[self.servicio.pk])
        )

        self.assertNotContains(response, '777')

    def test_registro_directo_desde_ficha_preselecciona_servicio(self):
        self.client.force_login(self.direccion)

        response = self.client.get(
            reverse('tarifa_servicio_directa'),
            {'servicio': self.servicio.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['form'].fields['servicio'].initial,
            self.servicio,
        )

    def test_direccion_ve_pendientes_y_publicacion_directa(self):
        propuesta = PropuestaTarifas.objects.create(
            vigencia_propuesta=timezone.localdate(),
            estado=PropuestaTarifas.ESTADO_PENDIENTE,
            creada_por=self.recepcion,
            enviada_por=self.recepcion,
            enviada_en=timezone.now(),
        )
        PropuestaTarifaDetalle.objects.create(
            propuesta=propuesta,
            servicio=self.servicio,
            precio_propuesto=Decimal('650.00'),
        )
        self.client.force_login(self.direccion)

        response = self.client.get(reverse('precios_servicios'))

        self.assertEqual(response.context['total_propuestas_pendientes'], 1)
        self.assertContains(response, 'Pendientes')
        self.assertContains(response, 'Registrar tarifa')
        self.assertNotContains(response, 'Proponer tarifas')

    def test_flujo_multiservicio_aprueba_sin_modificar_precio_legacy(self):
        segundo = Servicio.objects.create(
            nombre='Consulta médica',
            codigo='MED-CONS',
            activo=True,
            tratamiento_iva=Servicio.IVA_INCLUIDO_16,
            precio=Decimal('800.00'),
        )
        hoy = timezone.localdate()
        self.client.force_login(self.recepcion)
        response = self.client.post(reverse('propuesta_tarifas_nueva'), {
            'vigencia_propuesta': hoy.isoformat(),
            'observaciones': 'Actualización desde Catálogo',
            'accion': 'enviar',
            'detalles-TOTAL_FORMS': '2',
            'detalles-INITIAL_FORMS': '0',
            'detalles-MIN_NUM_FORMS': '0',
            'detalles-MAX_NUM_FORMS': '1000',
            'detalles-0-id': '',
            'detalles-0-propuesta': '',
            'detalles-0-servicio': str(self.servicio.pk),
            'detalles-0-precio_propuesto': '650.00',
            'detalles-0-gratuita_propuesta': 'False',
            'detalles-1-id': '',
            'detalles-1-propuesta': '',
            'detalles-1-servicio': str(segundo.pk),
            'detalles-1-precio_propuesto': '850.00',
            'detalles-1-gratuita_propuesta': 'False',
        })
        propuesta = PropuestaTarifas.objects.get()
        self.assertRedirects(
            response,
            reverse('propuesta_tarifas_detalle', args=[propuesta.pk]),
        )
        propuesta.refresh_from_db()
        self.assertEqual(propuesta.estado, PropuestaTarifas.ESTADO_PENDIENTE)
        self.assertEqual(propuesta.detalles.count(), 2)

        self.client.force_login(self.direccion)
        self.client.post(
            reverse('propuesta_tarifas_aprobar', args=[propuesta.pk])
        )
        propuesta.refresh_from_db()
        self.servicio.refresh_from_db()
        segundo.refresh_from_db()
        self.assertEqual(propuesta.estado, PropuestaTarifas.ESTADO_APROBADA)
        self.assertEqual(self.servicio.precio, Decimal('600.00'))
        self.assertEqual(segundo.precio, Decimal('800.00'))
        self.assertEqual(TarifaServicio.objects.count(), 2)

        response = self.client.get(reverse('precios_servicios'))
        self.assertContains(response, '650')
        self.assertContains(response, '560.34')
        self.assertContains(response, '89.66')
        self.assertContains(response, '325.00')
        self.assertNotContains(response, 'Referencia legacy')

    def test_rechazo_visible_y_duplicable_desde_el_ecosistema(self):
        propuesta = PropuestaTarifas.objects.create(
            vigencia_propuesta=timezone.localdate(),
            estado=PropuestaTarifas.ESTADO_PENDIENTE,
            creada_por=self.recepcion,
            enviada_por=self.recepcion,
            enviada_en=timezone.now(),
        )
        PropuestaTarifaDetalle.objects.create(
            propuesta=propuesta,
            servicio=self.servicio,
            precio_propuesto=Decimal('700.00'),
        )
        self.client.force_login(self.direccion)
        self.client.post(
            reverse('propuesta_tarifas_rechazar', args=[propuesta.pk]),
            {'motivo': 'Precio no autorizado.'},
        )
        propuesta.refresh_from_db()
        self.assertEqual(propuesta.estado, PropuestaTarifas.ESTADO_RECHAZADA)

        self.client.force_login(self.recepcion)
        catalogo = self.client.get(reverse('precios_servicios'))
        detalle = self.client.get(
            reverse('propuesta_tarifas_detalle', args=[propuesta.pk])
        )
        self.assertContains(catalogo, 'Rechazada')
        self.assertNotContains(catalogo, 'Precio no autorizado.')
        self.assertContains(detalle, 'Precio no autorizado.')
        self.assertContains(detalle, 'Duplicar como nuevo borrador')

    def test_tarifa_futura_solo_se_muestra_en_ficha_y_direccion_puede_cancelarla(self):
        hoy = timezone.localdate()
        self.publicar('650.00', hoy)
        futura = self.publicar('700.00', hoy + timedelta(days=30))
        self.client.force_login(self.direccion)

        catalogo = self.client.get(reverse('precios_servicios'))
        self.assertNotContains(catalogo, '$700.00')
        ficha = self.client.get(
            reverse('servicio_catalogo_detalle', args=[self.servicio.pk])
        )
        self.assertContains(ficha, '700')
        self.assertContains(ficha, 'Cancelar tarifa programada')

        self.client.post(
            reverse('tarifa_servicio_cancelar_futura', args=[futura.pk]),
            {'motivo': 'Programación sustituida'},
        )
        futura.refresh_from_db()
        self.servicio.refresh_from_db()
        self.assertEqual(futura.estado, TarifaServicio.ESTADO_CANCELADA)
        self.assertEqual(self.servicio.precio, Decimal('600.00'))
        catalogo = self.client.get(reverse('precios_servicios'))
        self.assertNotContains(catalogo, 'desde ' + futura.vigente_desde.strftime('%d/%m/%Y'))

    def test_post_legacy_no_modifica_servicio_precio(self):
        self.client.force_login(self.direccion)

        response = self.client.post(
            reverse('precios_servicios'),
            {f'precio_{self.servicio.pk}': '999.00'},
        )

        self.servicio.refresh_from_db()
        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.servicio.precio, Decimal('600.00'))
