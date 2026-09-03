from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from ventas.models import (
    Captacion,
    Captador,
    ComisionCaptacion,
    LiquidacionComisiones,
)
from ventas.services import normalizar_token_captacion

from .forms import PacienteForm
from .models import (
    Cita,
    CodigoInstitucionalPaciente,
    MovimientoEconomicoCita,
    Paciente,
    ReglaBeneficioReferido,
    TarifaServicio,
)
from .services_beneficios import paciente_tiene_captacion_registrada
from .tests_helpers import ClinicaTestDataMixin


class RegistroCaptacionNuevoExpedienteTests(ClinicaTestDataMixin, TestCase):
    nombre_nuevo = 'Paciente nuevo con captación'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.captador = Captador.objects.create(
            tipo=Captador.TIPO_EXTERNO,
            nombre_externo='Organización Captadora',
            tipo_organizacion=Captador.ORG_ORGANIZACION,
            creado_por=cls.staff,
        )
        cls.codigo = cls.captador.codigo_activo

    def setUp(self):
        self.client.force_login(self.staff)

    def _datos_paciente(self, codigo='', **extra):
        datos = {
            'nombre': self.nombre_nuevo,
            'fecha_nacimiento': '1995-05-10',
            'sexo': 'Femenino',
            'telefono': '5551112299',
            'identidad_contacto': 'propio',
            'servicio_inicial': str(self.servicio.pk),
            'codigo_captacion': codigo,
        }
        datos.update(extra)
        return datos

    def _registrar(self, codigo=None, **extra):
        if codigo is None:
            codigo = self.codigo.token
        return self.client.post(
            reverse('registrar_paciente'),
            self._datos_paciente(codigo, **extra),
        )

    def _captacion_creada(self):
        return Captacion.objects.select_related(
            'paciente', 'captador', 'codigo', 'registrado_por'
        ).get(paciente__nombre=self.nombre_nuevo)

    def test_01_campo_captacion_es_opcional(self):
        form = PacienteForm(incluir_captacion=True)
        self.assertFalse(form.fields['codigo_captacion'].required)

    def test_02_paciente_sin_codigo_se_crea_normalmente(self):
        response = self._registrar(codigo='')
        self.assertRedirects(response, reverse('lista_pacientes'))
        self.assertTrue(Paciente.objects.filter(nombre=self.nombre_nuevo).exists())
        self.assertFalse(
            Captacion.objects.filter(paciente__nombre=self.nombre_nuevo).exists()
        )

    def test_03_codigo_valido_crea_paciente_y_captacion(self):
        response = self._registrar()
        self.assertRedirects(response, reverse('lista_pacientes'))
        captacion = self._captacion_creada()
        self.assertEqual(captacion.paciente.nombre, self.nombre_nuevo)

    def test_codigo_publico_crea_captacion_con_el_codigo_correcto(self):
        self.codigo.porcentaje_comision = 5
        self.codigo.save(update_fields=['porcentaje_comision'])
        response = self._registrar(codigo=self.codigo.codigo_publico)
        self.assertRedirects(response, reverse('lista_pacientes'))
        self.assertEqual(self._captacion_creada().codigo, self.codigo)

    def test_04_url_qr_completa_crea_paciente_y_captacion(self):
        url_qr = 'http://testserver' + reverse(
            'ventas:validar_token',
            args=[self.codigo.token],
        )
        response = self._registrar(codigo=url_qr)
        self.assertRedirects(response, reverse('lista_pacientes'))
        self.assertTrue(
            Captacion.objects.filter(codigo=self.codigo).exists()
        )

    def test_05_token_se_normaliza_con_servicio_existente(self):
        url_qr = 'https://intra.example/ventas/validar/' + self.codigo.token + '/'
        self.assertEqual(
            normalizar_token_captacion(url_qr),
            self.codigo.token,
        )

    def test_06_captacion_se_asocia_al_paciente_correcto(self):
        self._registrar()
        captacion = self._captacion_creada()
        self.assertEqual(captacion.paciente, Paciente.objects.get(
            nombre=self.nombre_nuevo
        ))

    def test_07_captacion_se_asocia_al_captador_correcto(self):
        self._registrar()
        self.assertEqual(self._captacion_creada().captador, self.captador)

    def test_08_captacion_conserva_codigo_origen(self):
        self._registrar()
        self.assertEqual(self._captacion_creada().codigo, self.codigo)

    def test_09_captacion_conserva_snapshots_de_identidad(self):
        self._registrar()
        captacion = self._captacion_creada()
        self.assertEqual(
            captacion.captador_nombre_snapshot,
            self.captador.nombre_display,
        )
        self.assertEqual(
            captacion.captador_tipo_snapshot,
            self.captador.clasificacion_display,
        )

    def test_10_captacion_registra_usuario_de_recepcion(self):
        self._registrar()
        self.assertEqual(self._captacion_creada().registrado_por, self.staff)

    def test_11_codigo_invalido_no_crea_paciente_ni_captacion(self):
        response = self._registrar(codigo='CODIGO-INEXISTENTE')
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'No se encontró un código de captación válido.',
        )
        self.assertFalse(Paciente.objects.filter(nombre=self.nombre_nuevo).exists())
        self.assertFalse(Captacion.objects.exists())

    def test_12_codigo_inactivo_no_crea_paciente_ni_captacion(self):
        self.codigo.activo = False
        self.codigo.save(update_fields=['activo'])
        response = self._registrar()
        self.assertContains(response, 'Este código de captación ya no está activo.')
        self.assertFalse(Paciente.objects.filter(nombre=self.nombre_nuevo).exists())
        self.assertFalse(Captacion.objects.exists())

    def test_13_captador_inactivo_no_crea_paciente_ni_captacion(self):
        self.captador.activo = False
        self.captador.save(update_fields=['activo'])
        response = self._registrar()
        self.assertContains(
            response,
            'El captador asociado a este código no está activo.',
        )
        self.assertFalse(Paciente.objects.filter(nombre=self.nombre_nuevo).exists())
        self.assertFalse(Captacion.objects.exists())

    def test_14_validacion_previa_no_crea_captacion(self):
        response = self.client.get(
            reverse('ventas:validar_codigo'),
            {
                'formato': 'json',
                'codigo': self.codigo.token,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['valido'])
        self.assertEqual(response.json()['mensaje'], 'Captación identificada')
        self.assertFalse(Captacion.objects.exists())

    def test_15_fallo_de_captacion_revierte_alta_y_no_deja_huerfana(self):
        with patch(
            'clinica.views.registrar_captacion',
            side_effect=ValueError('No fue posible registrar la captación.'),
        ):
            response = self._registrar()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No fue posible registrar la captación.')
        self.assertFalse(Paciente.objects.filter(nombre=self.nombre_nuevo).exists())
        self.assertFalse(Captacion.objects.exists())

    def test_16_captacion_pendiente_acredita_origen_sin_aprobacion(self):
        self._registrar()
        captacion = self._captacion_creada()
        self.assertEqual(captacion.estado, Captacion.ESTADO_PENDIENTE)
        self.assertTrue(
            paciente_tiene_captacion_registrada(captacion.paciente)
        )

    def test_17_no_asigna_porcentaje_de_comision(self):
        self._registrar()
        self.assertIsNone(self._captacion_creada().porcentaje_comision)

    def test_18_no_crea_comision_captacion(self):
        self._registrar()
        self.assertFalse(ComisionCaptacion.objects.exists())

    def test_19_no_crea_liquidacion_comisiones(self):
        self._registrar()
        self.assertFalse(LiquidacionComisiones.objects.exists())

    def test_20_no_crea_movimiento_economico_cita(self):
        self._registrar()
        self.assertFalse(MovimientoEconomicoCita.objects.exists())

    def test_21_no_modifica_costo_de_citas(self):
        cita = self.crear_cita(costo=Decimal('437.50'))
        self._registrar()
        cita.refresh_from_db()
        self.assertEqual(cita.costo, Decimal('437.50'))

    def test_22_no_modifica_precio_del_servicio(self):
        precio_original = self.servicio.precio
        self._registrar()
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.precio, precio_original)

    def test_23_no_modifica_reglas_de_beneficio(self):
        total_inicial = ReglaBeneficioReferido.objects.count()
        self._registrar()
        self.assertEqual(ReglaBeneficioReferido.objects.count(), total_inicial)

    def test_24_no_modifica_tarifas_de_servicio(self):
        total_inicial = TarifaServicio.objects.count()
        self._registrar()
        self.assertEqual(TarifaServicio.objects.count(), total_inicial)

    def test_25_codigo_institucional_sigue_funcionando(self):
        response = self._registrar(codigo_institucional='MOR')
        self.assertRedirects(response, reverse('lista_pacientes'))
        paciente = Paciente.objects.get(nombre=self.nombre_nuevo)
        asignacion = CodigoInstitucionalPaciente.objects.get(paciente=paciente)
        self.assertEqual(asignacion.codigo, 'MOR')

    def test_26_familiares_relacionados_siguen_funcionando(self):
        response = self._registrar(
            pacientes_relacionados=[str(self.otro_paciente.pk)],
        )
        self.assertRedirects(response, reverse('lista_pacientes'))
        paciente = Paciente.objects.get(nombre=self.nombre_nuevo)
        self.assertIn(self.otro_paciente, paciente.pacientes_relacionados.all())

    def test_27_textos_visibles_dicen_captacion_y_no_referido(self):
        self._registrar()
        paciente = Paciente.objects.get(nombre=self.nombre_nuevo)
        detalle = self.client.get(
            reverse('detalle_paciente', args=[paciente.pk])
        )
        sin_captacion = self.client.get(
            reverse('detalle_paciente', args=[self.paciente.pk])
        )
        self.assertContains(detalle, 'Beneficio por captación')
        self.assertContains(detalle, 'Paciente con captación registrada')
        self.assertContains(detalle, 'Captador:')
        self.assertNotContains(
            detalle,
            '<h2 id="benefit-title">Beneficio de referido</h2>',
        )
        self.assertNotContains(
            detalle,
            'Paciente referido',
        )
        self.assertContains(
            sin_captacion,
            'Este paciente no tiene una captación registrada.',
        )

    def test_campo_se_muestra_solo_a_usuario_con_permiso_de_captacion(self):
        recepcion = User.objects.create_user(
            'recepcion_captacion',
            password='pruebas',
            is_staff=True,
        )
        permiso = Permission.objects.get(
            content_type__app_label='ventas',
            codename='register_captacion',
        )
        recepcion.user_permissions.add(permiso)
        self.client.force_login(recepcion)
        autorizado = self.client.get(reverse('registrar_paciente'))
        self.assertContains(autorizado, 'Código / QR de captación')

        sin_permiso = User.objects.create_user('recepcion_sin_captacion')
        self.client.force_login(sin_permiso)
        no_autorizado = self.client.get(reverse('registrar_paciente'))
        self.assertNotContains(no_autorizado, 'Código / QR de captación')

    def test_enter_del_lector_valida_sin_enviar_formulario(self):
        response = self.client.get(reverse('registrar_paciente'))
        self.assertContains(response, 'event.preventDefault()')
        self.assertContains(response, 'event.key === "Enter"')
        self.assertContains(response, 'data-validar-captacion')
