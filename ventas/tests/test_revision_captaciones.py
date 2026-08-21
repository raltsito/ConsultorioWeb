from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from clinica.tests_helpers import ClinicaTestDataMixin

from ventas.models import Captacion, Captador, EventoCaptacion
from ventas.services import (
    CaptacionYaRevisadaError,
    MotivoRechazoObligatorioError,
    PorcentajeComisionInvalidoError,
    aprobar_captacion,
    cambiar_estado_captador,
    rechazar_captacion,
    registrar_captacion,
)


class RevisionCaptacionMixin(ClinicaTestDataMixin):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.direccion = User.objects.create_user(
            "direccion_captaciones",
            password="pruebas",
        )
        cls.recepcion = User.objects.create_user(
            "recepcion_revision",
            password="pruebas",
        )
        cls.consulta = User.objects.create_user(
            "consulta_revision",
            password="pruebas",
        )
        permisos = {
            permiso.codename: permiso
            for permiso in Permission.objects.filter(
                content_type__app_label="ventas",
                codename__in=(
                    "review_captacion",
                    "register_captacion",
                    "view_captaciones",
                ),
            )
        }
        cls.direccion.user_permissions.add(permisos["review_captacion"])
        cls.recepcion.user_permissions.add(permisos["register_captacion"])
        cls.consulta.user_permissions.add(permisos["view_captaciones"])
        cls.captador = Captador.objects.create(
            tipo=Captador.TIPO_EXTERNO,
            nombre_externo="Escuela Histórica",
            tipo_organizacion=Captador.ORG_ESCUELA,
        )

    def crear_captacion(self):
        return registrar_captacion(
            paciente=self.paciente,
            codigo=self.captador.codigo_activo,
            usuario=self.recepcion,
        )


class ServiciosRevisionCaptacionTests(RevisionCaptacionMixin, TestCase):
    def test_pendiente_puede_aprobarse_con_porcentaje_1(self):
        captacion = aprobar_captacion(
            captacion=self.crear_captacion(),
            porcentaje=1,
            usuario=self.direccion,
        )
        self.assertEqual(captacion.estado, Captacion.ESTADO_APROBADA)
        self.assertEqual(captacion.porcentaje_comision, 1)
        self.assertEqual(captacion.decidido_por, self.direccion)
        self.assertIsNotNone(captacion.decidido_en)

    def test_pendiente_puede_aprobarse_con_porcentaje_10(self):
        captacion = aprobar_captacion(
            captacion=self.crear_captacion(),
            porcentaje=10,
            usuario=self.direccion,
        )
        self.assertEqual(captacion.porcentaje_comision, 10)

    def test_porcentajes_fuera_del_rango_son_rechazados(self):
        captacion = self.crear_captacion()
        for porcentaje in (0, 11):
            with self.subTest(porcentaje=porcentaje):
                with self.assertRaises(PorcentajeComisionInvalidoError):
                    aprobar_captacion(
                        captacion=captacion,
                        porcentaje=porcentaje,
                        usuario=self.direccion,
                    )
        captacion.refresh_from_db()
        self.assertEqual(captacion.estado, Captacion.ESTADO_PENDIENTE)

    def test_porcentaje_no_entero_es_rechazado(self):
        captacion = self.crear_captacion()
        with self.assertRaises(PorcentajeComisionInvalidoError):
            aprobar_captacion(
                captacion=captacion,
                porcentaje=7.5,
                usuario=self.direccion,
            )

    def test_pendiente_puede_rechazarse_sin_porcentaje(self):
        captacion = rechazar_captacion(
            captacion=self.crear_captacion(),
            motivo="Registro incorrecto.",
            usuario=self.direccion,
        )
        self.assertEqual(captacion.estado, Captacion.ESTADO_RECHAZADA)
        self.assertIsNone(captacion.porcentaje_comision)
        self.assertEqual(captacion.decidido_por, self.direccion)
        self.assertIsNotNone(captacion.decidido_en)
        self.assertEqual(captacion.motivo_rechazo, "Registro incorrecto.")

    def test_rechazo_exige_motivo(self):
        captacion = self.crear_captacion()
        with self.assertRaises(MotivoRechazoObligatorioError):
            rechazar_captacion(
                captacion=captacion,
                motivo="  ",
                usuario=self.direccion,
            )

    def test_aprobacion_genera_evento_estructurado(self):
        captacion = aprobar_captacion(
            captacion=self.crear_captacion(),
            porcentaje=7,
            usuario=self.direccion,
        )
        evento = EventoCaptacion.objects.get(captacion=captacion)
        self.assertEqual(evento.accion, EventoCaptacion.ACCION_APROBADA)
        self.assertEqual(evento.estado_anterior, Captacion.ESTADO_PENDIENTE)
        self.assertEqual(evento.estado_nuevo, Captacion.ESTADO_APROBADA)
        self.assertEqual(evento.porcentaje_comision, 7)
        self.assertEqual(evento.usuario, self.direccion)

    def test_rechazo_genera_evento_estructurado(self):
        captacion = rechazar_captacion(
            captacion=self.crear_captacion(),
            motivo="No corresponde.",
            usuario=self.direccion,
        )
        evento = EventoCaptacion.objects.get(captacion=captacion)
        self.assertEqual(evento.accion, EventoCaptacion.ACCION_RECHAZADA)
        self.assertEqual(evento.estado_nuevo, Captacion.ESTADO_RECHAZADA)
        self.assertEqual(evento.motivo, "No corresponde.")

    def test_decisiones_son_inmutables(self):
        aprobada = aprobar_captacion(
            captacion=self.crear_captacion(),
            porcentaje=5,
            usuario=self.direccion,
        )
        acciones = (
            lambda: aprobar_captacion(
                captacion=aprobada,
                porcentaje=8,
                usuario=self.direccion,
            ),
            lambda: rechazar_captacion(
                captacion=aprobada,
                motivo="Cambio",
                usuario=self.direccion,
            ),
        )
        for accion in acciones:
            with self.assertRaises(CaptacionYaRevisadaError):
                accion()
        aprobada.refresh_from_db()
        self.assertEqual(aprobada.porcentaje_comision, 5)
        self.assertEqual(aprobada.eventos.count(), 1)

    def test_rechazada_no_puede_volver_a_decidirse(self):
        rechazada = rechazar_captacion(
            captacion=self.crear_captacion(),
            motivo="Definitivo",
            usuario=self.direccion,
        )
        with self.assertRaises(CaptacionYaRevisadaError):
            aprobar_captacion(
                captacion=rechazada,
                porcentaje=5,
                usuario=self.direccion,
            )
        with self.assertRaises(CaptacionYaRevisadaError):
            rechazar_captacion(
                captacion=rechazada,
                motivo="Otro",
                usuario=self.direccion,
            )
        self.assertEqual(rechazada.eventos.count(), 1)


class VistasRevisionCaptacionTests(RevisionCaptacionMixin, TestCase):
    def test_direccion_puede_aprobar(self):
        captacion = self.crear_captacion()
        self.client.force_login(self.direccion)
        response = self.client.post(
            reverse("ventas:captacion_aprobar", args=[captacion.pk]),
            {"porcentaje_comision": 7},
        )
        self.assertRedirects(
            response,
            reverse("ventas:captacion_detalle", args=[captacion.pk]),
        )
        captacion.refresh_from_db()
        self.assertEqual(captacion.estado, Captacion.ESTADO_APROBADA)
        self.assertEqual(captacion.porcentaje_comision, 7)

    def test_porcentaje_vacio_cero_y_once_no_aprueban(self):
        for valor in ("", "0", "11"):
            with self.subTest(valor=valor):
                captacion = self.crear_captacion()
                self.client.force_login(self.direccion)
                self.client.post(
                    reverse("ventas:captacion_aprobar", args=[captacion.pk]),
                    {"porcentaje_comision": valor},
                )
                captacion.refresh_from_db()
                self.assertEqual(captacion.estado, Captacion.ESTADO_PENDIENTE)
                captacion.delete()

    def test_direccion_puede_rechazar(self):
        captacion = self.crear_captacion()
        self.client.force_login(self.direccion)
        self.client.post(
            reverse("ventas:captacion_rechazar", args=[captacion.pk]),
            {"motivo_rechazo": "Paciente registrado incorrectamente."},
        )
        captacion.refresh_from_db()
        self.assertEqual(captacion.estado, Captacion.ESTADO_RECHAZADA)
        self.assertEqual(
            captacion.motivo_rechazo,
            "Paciente registrado incorrectamente.",
        )

    def test_motivo_vacio_no_rechaza(self):
        captacion = self.crear_captacion()
        self.client.force_login(self.direccion)
        self.client.post(
            reverse("ventas:captacion_rechazar", args=[captacion.pk]),
            {"motivo_rechazo": ""},
        )
        captacion.refresh_from_db()
        self.assertEqual(captacion.estado, Captacion.ESTADO_PENDIENTE)

    def test_registro_y_consulta_no_otorgan_permiso_de_revision(self):
        captacion = self.crear_captacion()
        for usuario in (self.recepcion, self.consulta):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                response = self.client.post(
                    reverse("ventas:captacion_aprobar", args=[captacion.pk]),
                    {"porcentaje_comision": 7},
                )
                self.assertEqual(response.status_code, 403)

    def test_captador_sin_permiso_no_puede_aprobar_su_captacion(self):
        usuario = User.objects.create_user("captador_sin_revision", password="pruebas")
        captador = Captador.objects.create(
            tipo=Captador.TIPO_INTERNO,
            usuario=usuario,
        )
        captacion = registrar_captacion(
            paciente=self.otro_paciente,
            codigo=captador.codigo_activo,
            usuario=self.recepcion,
        )
        self.client.force_login(usuario)
        response = self.client.post(
            reverse("ventas:captacion_aprobar", args=[captacion.pk]),
            {"porcentaje_comision": 10},
        )
        self.assertEqual(response.status_code, 403)

    def test_doble_post_no_duplica_decision_ni_evento(self):
        captacion = self.crear_captacion()
        self.client.force_login(self.direccion)
        url = reverse("ventas:captacion_aprobar", args=[captacion.pk])
        self.client.post(url, {"porcentaje_comision": 4})
        self.client.post(url, {"porcentaje_comision": 9})
        captacion.refresh_from_db()
        self.assertEqual(captacion.porcentaje_comision, 4)
        self.assertEqual(captacion.eventos.count(), 1)

    def test_detalle_oculta_controles_despues_de_decidir(self):
        captacion = aprobar_captacion(
            captacion=self.crear_captacion(),
            porcentaje=6,
            usuario=self.direccion,
        )
        self.client.force_login(self.direccion)
        response = self.client.get(
            reverse("ventas:captacion_detalle", args=[captacion.pk])
        )
        self.assertContains(response, "Comisión autorizada")
        self.assertNotContains(response, "Aprobar captación")
        self.assertNotContains(response, "$0.00")

    def test_listado_muestra_contadores_estado_y_porcentaje(self):
        aprobar_captacion(
            captacion=self.crear_captacion(),
            porcentaje=8,
            usuario=self.direccion,
        )
        self.client.force_login(self.direccion)
        response = self.client.get(reverse("ventas:captaciones_lista"))
        self.assertContains(response, "Aprobadas")
        self.assertContains(response, "8%")


class HistoricoRevisionCaptacionTests(RevisionCaptacionMixin, TestCase):
    def test_captador_inactivo_no_impide_revisar_captacion_existente(self):
        captacion = self.crear_captacion()
        cambiar_estado_captador(
            self.captador,
            activar=False,
            usuario=self.direccion,
            motivo="Pausa comercial",
        )
        aprobada = aprobar_captacion(
            captacion=captacion,
            porcentaje=5,
            usuario=self.direccion,
        )
        self.assertEqual(aprobada.estado, Captacion.ESTADO_APROBADA)

    def test_cambios_del_captador_no_modifican_snapshots(self):
        captacion = self.crear_captacion()
        self.captador.nombre_externo = "Nombre posterior"
        self.captador.save(update_fields=["nombre_externo"])
        captacion.refresh_from_db()
        self.assertEqual(
            captacion.captador_nombre_snapshot,
            "Escuela Histórica",
        )
