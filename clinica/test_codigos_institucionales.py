from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import CodigoInstitucionalPaciente, Paciente, PacienteTerapeutaAcceso
from .services_codigos import actualizar_codigos_institucionales
from .tests_helpers import ClinicaTestDataMixin


class CodigosInstitucionalesTests(ClinicaTestDataMixin, TestCase):
    def setUp(self):
        PacienteTerapeutaAcceso.objects.create(
            terapeuta=self.terapeuta,
            paciente=self.paciente,
            creado_por=self.staff,
        )

    def _url(self):
        return reverse('administrar_codigos_paciente', args=[self.paciente.id])

    def _actualizar(self, codigo=''):
        return self.client.post(
            self._url(),
            {'codigo_institucional': codigo},
        )

    def _datos_nuevo_paciente(self, numero=1, codigo=''):
        return {
            'nombre': f'Paciente recepción {numero}',
            'fecha_nacimiento': '1995-05-10',
            'sexo': 'Femenino',
            'telefono': f'55511122{numero:02d}',
            'identidad_contacto': 'propio',
            'servicio_inicial': str(self.servicio.id),
            'codigo_institucional': codigo,
        }

    def test_recepcion_crea_paciente_sin_codigo(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('registrar_paciente'),
            self._datos_nuevo_paciente(),
        )
        self.assertRedirects(response, reverse('lista_pacientes'))
        paciente = Paciente.objects.get(nombre='Paciente recepción 1')
        self.assertFalse(paciente.codigos_institucionales.exists())

    def test_nuevo_expediente_renderiza_selector_cerrado(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('registrar_paciente'))
        self.assertContains(response, 'data-patient-code-selector')
        self.assertContains(response, 'patient-code-selector__menu')
        self.assertContains(response, 'role="listbox"')
        self.assertContains(response, 'hidden')
        self.assertContains(response, 'patient_codes.css')

    def test_recepcion_crea_paciente_con_cada_tipo_de_codigo(self):
        self.client.force_login(self.staff)
        codigos = ('MOR', 'ROS', 'C100-B', 'C100-M', 'C100-A')
        for numero, codigo in enumerate(codigos, start=1):
            with self.subTest(codigo=codigo):
                response = self.client.post(
                    reverse('registrar_paciente'),
                    self._datos_nuevo_paciente(numero, codigo),
                )
                self.assertRedirects(response, reverse('lista_pacientes'))
                asignacion = CodigoInstitucionalPaciente.objects.get(
                    paciente__nombre=f'Paciente recepción {numero}',
                )
                self.assertEqual(asignacion.codigo, codigo)
                self.assertTrue(asignacion.activo)
                self.assertEqual(asignacion.asignado_por_usuario, self.staff)
                self.assertIsNotNone(asignacion.fecha_asignacion)

    def test_servicio_y_base_de_datos_impiden_varios_codigos_activos(self):
        with self.assertRaises(ValidationError):
            actualizar_codigos_institucionales(
                paciente=self.paciente,
                codigos={'MOR', 'ROS'},
                usuario=self.usuario_terapeuta,
                terapeuta=self.terapeuta,
            )

        CodigoInstitucionalPaciente.objects.create(
            paciente=self.paciente,
            codigo='MOR',
            asignado_por=self.terapeuta,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            CodigoInstitucionalPaciente.objects.create(
                paciente=self.paciente,
                codigo='ROS',
                asignado_por=self.terapeuta,
            )

    def test_terapeuta_cambia_codigo_y_conserva_historial(self):
        self.client.force_login(self.usuario_terapeuta)
        for codigo in ('MOR', 'ROS', 'AZI'):
            response = self._actualizar(codigo)
            self.assertRedirects(
                response,
                reverse('expediente_terapeuta_detalle', args=[self.paciente.id]),
            )

        historial = list(
            self.paciente.codigos_institucionales.order_by('fecha_asignacion')
        )
        self.assertEqual([item.codigo for item in historial], ['MOR', 'ROS', 'AZI'])
        self.assertFalse(historial[0].activo)
        self.assertFalse(historial[1].activo)
        self.assertTrue(historial[2].activo)
        for anterior in historial[:2]:
            self.assertEqual(anterior.retirado_por_usuario, self.usuario_terapeuta)
            self.assertIsNotNone(anterior.fecha_retiro)

    def test_codigo_100_cambia_de_nivel_y_se_retira(self):
        self.client.force_login(self.usuario_terapeuta)
        for codigo in ('C100-A', 'C100-M', 'C100-B', ''):
            self._actualizar(codigo)

        historial = self.paciente.codigos_institucionales.filter(
            codigo__startswith='C100-'
        ).order_by('fecha_asignacion')
        self.assertEqual(
            list(historial.values_list('codigo', flat=True)),
            ['C100-A', 'C100-M', 'C100-B'],
        )
        self.assertFalse(historial.filter(activo=True).exists())
        self.assertTrue(
            all(item.fecha_retiro is not None for item in historial)
        )

    def test_sin_codigo_pasa_a_vio(self):
        self.client.force_login(self.usuario_terapeuta)
        self._actualizar('VIO')
        asignacion = self.paciente.codigos_institucionales.get(activo=True)
        self.assertEqual(asignacion.codigo, 'VIO')
        self.assertEqual(
            asignacion.asignado_por_usuario,
            self.usuario_terapeuta,
        )

    def test_terapeuta_sin_relacion_y_usuario_no_autorizado_no_modifican(self):
        self.client.force_login(self.usuario_otro_terapeuta)
        self.assertEqual(self._actualizar('MOR').status_code, 403)

        recepcion = User.objects.create_user(
            'recepcion_codigos',
            password='x',
            is_staff=True,
        )
        self.client.force_login(recepcion)
        self.assertEqual(self._actualizar('MOR').status_code, 403)
        self.assertFalse(self.paciente.codigos_institucionales.exists())

    def test_codigo_invalido_no_modifica_paciente(self):
        self.client.force_login(self.usuario_terapeuta)
        response = self._actualizar('INVALIDO')
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.paciente.codigos_institucionales.exists())

    def test_agenda_muestra_un_solo_indicador_activo(self):
        fecha_local = date(2030, 1, 7)
        self.crear_cita(fecha=fecha_local)
        CodigoInstitucionalPaciente.objects.create(
            paciente=self.paciente,
            codigo='MOR',
            asignado_por=self.terapeuta,
        )
        self.client.force_login(self.staff)
        with patch('clinica.views.timezone.localdate', return_value=fecha_local):
            response = self.client.get(reverse('home'))
        self.assertContains(response, '<th>Código</th>', html=True)
        self.assertContains(response, 'patient-code-dot--MOR', count=1)

    def test_listado_y_expedientes_muestran_solo_codigo_activo(self):
        CodigoInstitucionalPaciente.objects.create(
            paciente=self.paciente,
            codigo='MOR',
            asignado_por=self.terapeuta,
            activo=False,
        )
        CodigoInstitucionalPaciente.objects.create(
            paciente=self.paciente,
            codigo='VIH',
            asignado_por=self.terapeuta,
        )
        self.client.force_login(self.staff)
        listado = self.client.get(reverse('lista_pacientes'))
        detalle = self.client.get(
            reverse('detalle_paciente', args=[self.paciente.id])
        )
        self.assertNotContains(listado, 'patient-code-dot--MOR')
        self.assertContains(listado, 'patient-code-dot--VIH', count=1)
        self.assertContains(detalle, 'CÓDIGO')
        self.assertContains(detalle, 'Código VIH')
        self.assertNotContains(detalle, 'Código Morado')

        self.client.force_login(self.usuario_terapeuta)
        expediente = self.client.get(
            reverse('expediente_terapeuta_detalle', args=[self.paciente.id])
        )
        self.assertContains(expediente, 'Editar código')
        self.assertContains(expediente, 'Código VIH')

    def test_paciente_sin_codigo_no_produce_errores(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('lista_pacientes'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'patient-code-dot--')
