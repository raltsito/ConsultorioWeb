from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import CodigoInstitucionalPaciente, PacienteTerapeutaAcceso
from .tests_helpers import ClinicaTestDataMixin


class CodigosInstitucionalesTests(ClinicaTestDataMixin, TestCase):
    def setUp(self):
        PacienteTerapeutaAcceso.objects.create(
            terapeuta=self.terapeuta, paciente=self.paciente, creado_por=self.staff
        )

    def _url(self):
        return reverse('administrar_codigos_paciente', args=[self.paciente.id])

    def test_paciente_sin_uno_y_varios_codigos(self):
        self.assertFalse(self.paciente.codigos_institucionales.exists())
        CodigoInstitucionalPaciente.objects.create(
            paciente=self.paciente,
            codigo='MOR',
            asignado_por=self.terapeuta,
        )
        CodigoInstitucionalPaciente.objects.create(
            paciente=self.paciente,
            codigo='ROS',
            asignado_por=self.terapeuta,
        )
        activos = self.paciente.codigos_institucionales.filter(activo=True)
        self.assertEqual(activos.count(), 2)

    def test_terapeuta_autorizado_asigna_y_sustituye_nivel_c100(self):
        self.client.force_login(self.usuario_terapeuta)
        self.client.post(self._url(), {'codigos': ['C100-B', 'ROS']})
        self.client.post(self._url(), {'codigos': ['C100-A', 'ROS']})
        activos = set(
            self.paciente.codigos_institucionales
            .filter(activo=True)
            .values_list('codigo', flat=True)
        )
        self.assertEqual(activos, {'C100-A', 'ROS'})
        anterior = self.paciente.codigos_institucionales.get(codigo='C100-B')
        self.assertIsNotNone(anterior.fecha_retiro)
        self.assertEqual(anterior.retirado_por, self.terapeuta)

    def test_rechaza_dos_niveles_c100(self):
        self.client.force_login(self.usuario_terapeuta)
        self.client.post(self._url(), {'codigos': ['C100-B', 'C100-M']})
        self.assertFalse(self.paciente.codigos_institucionales.exists())

    def test_terapeuta_sin_relacion_y_recepcion_no_modifican(self):
        self.client.force_login(self.usuario_otro_terapeuta)
        respuesta = self.client.post(self._url(), {'codigos': ['MOR']})
        self.assertEqual(respuesta.status_code, 403)

        recepcion = User.objects.create_user(
            'recepcion_codigos',
            password='x',
            is_staff=True,
        )
        self.client.force_login(recepcion)
        respuesta = self.client.post(self._url(), {'codigos': ['MOR']})
        self.assertEqual(respuesta.status_code, 403)

    def test_agenda_muestra_columna_y_varios_indicadores(self):
        fecha_local = date(2030, 1, 7)
        self.crear_cita(fecha=fecha_local)
        for codigo in ('MOR', 'ROS'):
            CodigoInstitucionalPaciente.objects.create(
                paciente=self.paciente,
                codigo=codigo,
                asignado_por=self.terapeuta,
            )
        self.client.force_login(self.staff)
        with patch(
            'clinica.views.timezone.localdate',
            return_value=fecha_local,
        ):
            response = self.client.get(reverse('home'))
        self.assertContains(response, '<th>Código</th>', html=True)
        self.assertContains(response, 'patient-code-dot--MOR')
        self.assertContains(response, 'patient-code-dot--ROS')

    def test_listado_y_expedientes_renderizan_codigos_y_gestion(self):
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
        self.assertContains(listado, '<th>Código</th>', html=True)
        self.assertContains(listado, 'patient-code-dot--VIH')
        self.assertContains(detalle, 'CÓDIGOS')
        self.assertNotContains(detalle, 'Administrar códigos')

        self.client.force_login(self.usuario_terapeuta)
        expediente = self.client.get(
            reverse('expediente_terapeuta_detalle', args=[self.paciente.id])
        )
        self.assertContains(expediente, 'Administrar códigos')
        self.assertContains(expediente, 'patient-code-dot--VIH')
