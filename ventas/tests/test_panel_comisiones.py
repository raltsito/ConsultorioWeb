from decimal import Decimal

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from clinica.models import Cita, MovimientoEconomicoCita
from clinica.services import anular_movimiento_economico
from ventas.models import Captador, ComisionCaptacion, EventoCaptacion
from ventas.queries import obtener_resumen_comisiones
from ventas.services import (
    evaluar_y_generar_comision,
    reconciliar_estado_comision,
)
from ventas.tests.test_generacion_comisiones import GeneracionComisionMixin


class PanelComisionesTests(GeneracionComisionMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.consultor = User.objects.create_user(
            username="consulta_comisiones",
            password="pruebas",
        )
        permiso = Permission.objects.get(
            codename="view_comisiones_captacion"
        )
        cls.consultor.user_permissions.add(permiso)

    def setUp(self):
        self.servicio.refresh_from_db()
        self.client.force_login(self.consultor)

    def crear_comision(
        self,
        *,
        paciente=None,
        porcentaje=7,
        importe_servicio="400.00",
        importe_pago="100.00",
    ):
        paciente = paciente or self.paciente
        captacion = self.crear_captacion(
            paciente=paciente,
            porcentaje=porcentaje,
        )
        cita = self.crear_cita_asistida(
            paciente=paciente,
            costo=Decimal(importe_servicio),
        )
        pago = self.registrar_pago_cita(
            cita,
            importe=importe_pago,
            importe_servicio=importe_servicio,
        )
        comision = evaluar_y_generar_comision(
            captacion,
            usuario=self.staff,
        ).comision
        return comision, cita, pago

    def test_panel_suma_dos_comisiones_pendientes(self):
        self.crear_comision()
        self.crear_comision(
            paciente=self.otro_paciente,
            porcentaje=8,
            importe_servicio="500.00",
        )
        resumen = obtener_resumen_comisiones()

        self.assertEqual(resumen.cantidad_pendiente, 2)
        self.assertEqual(resumen.monto_pendiente, Decimal("68.00"))

    def test_suspendidas_se_muestran_separadas_del_monto_pagadero(self):
        self.crear_comision()
        suspendida, _, _ = self.crear_comision(
            paciente=self.otro_paciente,
            porcentaje=8,
            importe_servicio="500.00",
        )
        ComisionCaptacion.objects.filter(pk=suspendida.pk).update(
            estado=ComisionCaptacion.ESTADO_SUSPENDIDA
        )
        resumen = obtener_resumen_comisiones()

        self.assertEqual(resumen.monto_pendiente, Decimal("28.00"))
        self.assertEqual(resumen.monto_suspendido, Decimal("40.00"))
        self.assertEqual(resumen.monto_total, Decimal("68.00"))

    def test_listado_muestra_campos_financieros_historicos(self):
        comision, _, _ = self.crear_comision()

        respuesta = self.client.get(reverse("ventas:comisiones_panel"))

        self.assertContains(respuesta, comision.captador_nombre_snapshot)
        self.assertContains(respuesta, comision.paciente_nombre_snapshot)
        self.assertContains(respuesta, "$400.00")
        self.assertContains(respuesta, "7%")
        self.assertContains(respuesta, "$28.00")
        self.assertContains(respuesta, "Pendiente de pago")

    def test_detalle_utiliza_base_y_monto_de_comision(self):
        comision, _, _ = self.crear_comision()

        respuesta = self.client.get(
            reverse("ventas:comision_detalle", args=[comision.pk])
        )
        self.assertContains(respuesta, "Base histórica utilizada")
        self.assertContains(respuesta, "$400.00")
        self.assertContains(respuesta, "$28.00")

    def test_detalle_no_recalcula_despues_de_cambios_operativos(self):
        comision, cita, _ = self.crear_comision()
        self.servicio.precio = Decimal("999.00")
        self.servicio.save(update_fields=["precio"])
        cita.costo = Decimal("888.00")
        cita.save(update_fields=["costo"])
        Cita.objects.filter(pk=cita.pk).update(
            importe_servicio_snapshot=Decimal("777.00"),
        )

        respuesta = self.client.get(
            reverse("ventas:comision_detalle", args=[comision.pk])
        )

        self.assertEqual(
            respuesta.context["comision"].base_calculo,
            Decimal("400.00"),
        )
        self.assertEqual(
            respuesta.context["comision"].monto_calculado,
            Decimal("28.00"),
        )

    def test_cita_familiar_aparece_como_una_obligacion(self):
        captacion = self.crear_captacion(porcentaje=8)
        cita = self.crear_cita_asistida(costo=Decimal("600.00"))
        cita.pacientes_adicionales.add(self.otro_paciente)
        self.registrar_pago_cita(
            cita,
            importe="200.00",
            importe_servicio="450.00",
        )
        evaluar_y_generar_comision(captacion)

        respuesta = self.client.get(reverse("ventas:comisiones_panel"))

        self.assertEqual(respuesta.context["pagina"].paginator.count, 1)
        self.assertContains(respuesta, "$450.00")
        self.assertContains(respuesta, "$36.00")

    def test_panel_muestra_snapshot_del_principal_no_del_adicional(self):
        captacion = self.crear_captacion(porcentaje=8)
        cita = self.crear_cita_asistida(costo=Decimal("600.00"))
        cita.pacientes_adicionales.add(self.otro_paciente)
        self.registrar_pago_cita(
            cita,
            importe="200.00",
            importe_servicio="450.00",
        )
        evaluar_y_generar_comision(captacion)

        respuesta = self.client.get(reverse("ventas:comisiones_panel"))

        self.assertContains(respuesta, self.paciente.nombre)
        self.assertNotContains(respuesta, self.otro_paciente.nombre)
        self.assertEqual(ComisionCaptacion.objects.count(), 1)

    def test_suspendida_es_visible_en_listado_filtro_y_detalle(self):
        comision, _, _ = self.crear_comision()
        ComisionCaptacion.objects.filter(pk=comision.pk).update(
            estado=ComisionCaptacion.ESTADO_SUSPENDIDA
        )

        listado = self.client.get(
            reverse("ventas:comisiones_panel"),
            {"estado": ComisionCaptacion.ESTADO_SUSPENDIDA},
        )
        detalle = self.client.get(
            reverse("ventas:comision_detalle", args=[comision.pk])
        )

        self.assertContains(listado, "Suspendida")
        self.assertContains(detalle, "Comisión suspendida")

    def test_detalle_muestra_auditoria_completa(self):
        comision, cita, pago = self.crear_comision()
        anular_movimiento_economico(movimiento=pago, usuario=self.staff, motivo="CorrecciÃ³n")
        reconciliar_estado_comision(comision, usuario=self.staff)
        self.registrar_pago_cita(cita, importe="20.00")
        reconciliar_estado_comision(comision, usuario=self.staff)

        respuesta = self.client.get(
            reverse("ventas:comision_detalle", args=[comision.pk])
        )

        self.assertContains(respuesta, "Comisión generada")
        self.assertContains(respuesta, "Comisión suspendida")
        self.assertContains(respuesta, "Comisión reactivada")

    def test_permiso_es_especifico_para_el_panel(self):
        usuario_sin_permiso = User.objects.create_user(
            username="sin_permiso_comisiones",
            password="pruebas",
        )
        self.client.force_login(usuario_sin_permiso)

        denegada = self.client.get(reverse("ventas:comisiones_panel"))
        self.client.force_login(self.consultor)
        permitida = self.client.get(reverse("ventas:comisiones_panel"))

        self.assertEqual(denegada.status_code, 403)
        self.assertEqual(permitida.status_code, 200)

    def test_abrir_panel_y_detalle_no_modifica_estado_ni_dominios(self):
        comision, cita, pago = self.crear_comision()
        estado_original = (
            ComisionCaptacion.objects.count(),
            comision.estado,
            EventoCaptacion.objects.count(),
            MovimientoEconomicoCita.objects.count(),
            pago.estado,
            cita.importe_servicio_snapshot,
        )

        self.client.get(reverse("ventas:comisiones_panel"))
        self.client.get(reverse("ventas:comision_detalle", args=[comision.pk]))
        comision.refresh_from_db()
        pago.refresh_from_db()
        cita.refresh_from_db()

        self.assertEqual(
            (
                ComisionCaptacion.objects.count(),
                comision.estado,
                EventoCaptacion.objects.count(),
                MovimientoEconomicoCita.objects.count(),
                pago.estado,
                cita.importe_servicio_snapshot,
            ),
            estado_original,
        )

    def test_filtros_por_estado_captador_y_paciente(self):
        pendiente, _, _ = self.crear_comision()
        suspendida, _, _ = self.crear_comision(
            paciente=self.otro_paciente,
        )
        ComisionCaptacion.objects.filter(pk=suspendida.pk).update(
            estado=ComisionCaptacion.ESTADO_SUSPENDIDA
        )

        por_estado = self.client.get(
            reverse("ventas:comisiones_panel"),
            {"estado": "suspendida"},
        )
        por_captador = self.client.get(
            reverse("ventas:comisiones_panel"),
            {"captador": pendiente.captacion.captador_id},
        )
        por_paciente = self.client.get(
            reverse("ventas:comisiones_panel"),
            {"paciente": self.otro_paciente.nombre},
        )

        self.assertEqual(por_estado.context["pagina"].paginator.count, 1)
        self.assertEqual(por_captador.context["pagina"].paginator.count, 2)
        self.assertEqual(por_paciente.context["pagina"].paginator.count, 1)

    def test_clasificacion_y_filtro_interno_externo(self):
        self.crear_comision()
        usuario_interno = User.objects.create_user(
            username="captador_interno_panel",
            first_name="Irene",
            last_name="Interna",
        )
        captador_interno = Captador.objects.create(
            tipo=Captador.TIPO_INTERNO,
            usuario=usuario_interno,
        )
        paciente_interno = self.crear_otro_paciente(
            "Paciente Interno",
            "5550000099",
        )
        captacion = self.crear_captacion(
            paciente=paciente_interno,
            aprobar=False,
        )
        captacion.captador = captador_interno
        captacion.codigo = captador_interno.codigo_activo
        captacion.captador_nombre_snapshot = captador_interno.nombre_display
        captacion.captador_tipo_snapshot = captador_interno.clasificacion_display
        captacion.estado = captacion.ESTADO_APROBADA
        captacion.porcentaje_comision = 7
        captacion.save()
        cita = self.crear_cita_asistida(
            paciente=paciente_interno,
            costo=Decimal("400.00"),
        )
        self.registrar_pago_cita(cita, importe_servicio="400.00")
        evaluar_y_generar_comision(captacion)

        internos = self.client.get(
            reverse("ventas:comisiones_panel"),
            {"tipo": Captador.TIPO_INTERNO},
        )
        externos = self.client.get(
            reverse("ventas:comisiones_panel"),
            {"tipo": Captador.TIPO_EXTERNO},
        )

        self.assertContains(internos, "Usuario interno")
        self.assertContains(internos, "Irene Interna")
        self.assertEqual(
            [
                item.captador_nombre_snapshot
                for item in internos.context["pagina"].object_list
            ],
            ["Irene Interna"],
        )
        self.assertEqual(
            [
                item.captador_nombre_snapshot
                for item in externos.context["pagina"].object_list
            ],
            [self.captador.nombre_display],
        )
