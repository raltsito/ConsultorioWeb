from decimal import Decimal

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse
from ventas.models import ComisionCaptacion, EventoCaptacion, LiquidacionComisiones
from ventas.queries import (
    liquidaciones_con_incidencia_activa,
    obtener_resumen_liquidaciones,
)
from ventas.services import (
    cancelar_borrador_liquidacion,
    confirmar_pago_liquidacion,
)
from ventas.tests.test_liquidaciones_operativas import LiquidacionesOperativasMixin


class PanelLiquidacionesTests(LiquidacionesOperativasMixin, TestCase):
    def setUp(self):
        permiso = Permission.objects.get(codename="view_liquidaciones")
        self.staff.user_permissions.add(permiso)
        self.client.force_login(self.staff)

    def pagar(self, liquidacion, referencia="REF-7E"):
        return confirmar_pago_liquidacion(
            liquidacion=liquidacion,
            metodo_pago="transferencia",
            referencia=referencia,
            usuario=self.staff,
        )

    def usuario_finanzas(self, *, puede_pagar):
        usuario = User.objects.create_user(
            f"finanzas_panel_{'paga' if puede_pagar else 'consulta'}"
        )
        permisos = Permission.objects.filter(
            content_type__app_label="ventas",
            codename__in=(
                ["view_liquidaciones", "pay_liquidacion"]
                if puede_pagar
                else ["view_liquidaciones"]
            ),
        )
        usuario.user_permissions.add(*permisos)
        return usuario

    def test_panel_muestra_registrar_pago_para_borrador_con_permiso(self):
        liquidacion = self.crear_borrador([self.crear_comision(1)])
        self.client.force_login(self.usuario_finanzas(puede_pagar=True))

        respuesta = self.client.get(reverse("ventas:liquidaciones_panel"))

        self.assertContains(
            respuesta,
            reverse("ventas:liquidacion_registrar_pago", args=[liquidacion.pk]),
        )
        self.assertContains(respuesta, "Registrar pago")

    def test_panel_oculta_registrar_pago_sin_permiso(self):
        liquidacion = self.crear_borrador([self.crear_comision(1)])
        self.client.force_login(self.usuario_finanzas(puede_pagar=False))

        respuesta = self.client.get(reverse("ventas:liquidaciones_panel"))

        self.assertNotContains(
            respuesta,
            reverse("ventas:liquidacion_registrar_pago", args=[liquidacion.pk]),
        )

    def test_panel_oculta_registrar_pago_para_pagada(self):
        liquidacion = self.crear_borrador([self.crear_comision(1)])
        self.pagar(liquidacion)
        self.client.force_login(self.usuario_finanzas(puede_pagar=True))

        respuesta = self.client.get(reverse("ventas:liquidaciones_panel"))

        self.assertNotContains(
            respuesta,
            reverse("ventas:liquidacion_registrar_pago", args=[liquidacion.pk]),
        )

    def test_panel_oculta_registrar_pago_para_cancelada(self):
        liquidacion = self.crear_borrador([self.crear_comision(1)])
        cancelar_borrador_liquidacion(
            liquidacion=liquidacion,
            motivo="No debe pagarse",
            usuario=self.staff,
        )
        self.client.force_login(self.usuario_finanzas(puede_pagar=True))

        respuesta = self.client.get(reverse("ventas:liquidaciones_panel"))

        self.assertNotContains(
            respuesta,
            reverse("ventas:liquidacion_registrar_pago", args=[liquidacion.pk]),
        )

    def test_panel_lista_estados_y_totales_con_semantica_correcta(self):
        borrador = self.crear_borrador([self.crear_comision(1, monto="40.00")])
        pagada = self.crear_borrador([self.crear_comision(2, monto="28.00")])
        self.pagar(pagada)
        comision_pagada = pagada.lineas.get().comision
        comision_pagada.monto_calculado = Decimal("999.00")
        comision_pagada.save(update_fields=["monto_calculado"])
        cancelada = self.crear_borrador([self.crear_comision(3, monto="35.00")])
        cancelar_borrador_liquidacion(
            liquidacion=cancelada,
            motivo="Duplicada",
            usuario=self.staff,
        )

        respuesta = self.client.get(reverse("ventas:liquidaciones_panel"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, f"#{borrador.pk}")
        self.assertContains(respuesta, f"#{pagada.pk}")
        self.assertContains(respuesta, f"#{cancelada.pk}")
        self.assertEqual(
            [item.pk for item in respuesta.context["pagina"]],
            [cancelada.pk, pagada.pk, borrador.pk],
        )
        resumen = respuesta.context["resumen"]
        self.assertEqual(resumen.cantidad_borradores, 1)
        self.assertEqual(resumen.total_provisional_borradores, Decimal("40.00"))
        self.assertEqual(resumen.cantidad_pagadas, 1)
        self.assertEqual(resumen.monto_historico_pagado, Decimal("28.00"))
        self.assertEqual(resumen.cantidad_canceladas, 1)

    def test_filtros_por_estado_referencia_captador_e_incidencia(self):
        borrador = self.crear_borrador([self.crear_comision(1)])
        pagada = self.crear_borrador([self.crear_comision(2)])
        self.pagar(pagada, referencia="TRANSFER-UNICA")
        comision = pagada.lineas.get().comision
        comision.estado = ComisionCaptacion.ESTADO_SUSPENDIDA
        comision.save(update_fields=["estado"])

        for parametros in (
            {"estado": "pagada"},
            {"q": "TRANSFER-UNICA"},
            {"captador": str(self.captador.pk)},
            {"incidencia": "si"},
        ):
            with self.subTest(parametros=parametros):
                respuesta = self.client.get(
                    reverse("ventas:liquidaciones_panel"),
                    parametros,
                )
                ids = [item.pk for item in respuesta.context["pagina"]]
                self.assertIn(pagada.pk, ids)
        respuesta = self.client.get(
            reverse("ventas:liquidaciones_panel"), {"incidencia": "si"}
        )
        self.assertNotContains(respuesta, f"#{borrador.pk}")

    def test_incidencia_es_derivada_y_no_muta_datos(self):
        pagada = self.crear_borrador([self.crear_comision(1)])
        self.pagar(pagada)
        linea = pagada.lineas.get()
        snapshot = linea.monto_liquidado_snapshot
        eventos_antes = pagada.eventos.count()
        linea.comision.estado = ComisionCaptacion.ESTADO_SUSPENDIDA
        linea.comision.save(update_fields=["estado"])

        resumen = obtener_resumen_liquidaciones()
        self.client.get(reverse("ventas:liquidacion_detalle", args=[pagada.pk]))

        linea.refresh_from_db()
        pagada.refresh_from_db()
        self.assertEqual(resumen.cantidad_con_incidencia, 1)
        self.assertEqual(liquidaciones_con_incidencia_activa().get(), pagada)
        self.assertEqual(linea.monto_liquidado_snapshot, snapshot)
        self.assertEqual(pagada.eventos.count(), eventos_antes)
        self.assertEqual(pagada.estado, LiquidacionComisiones.ESTADO_PAGADA)

    def test_detalle_pagado_muestra_aviso_neutral_y_eventos_relacionados(self):
        pagada = self.crear_borrador([self.crear_comision(1)])
        self.pagar(pagada)
        comision = pagada.lineas.get().comision
        comision.estado = ComisionCaptacion.ESTADO_SUSPENDIDA
        comision.save(update_fields=["estado"])
        EventoCaptacion.objects.create(
            captacion=comision.captacion,
            accion=EventoCaptacion.ACCION_COMISION_SUSPENDIDA,
            usuario=self.staff,
            estado_anterior=comision.captacion.estado,
            estado_nuevo=comision.captacion.estado,
            motivo="Pago de cita anulado",
        )

        respuesta = self.client.get(
            reverse("ventas:liquidacion_detalle", args=[pagada.pk])
        )

        self.assertContains(respuesta, "Incidencia posterior al pago")
        self.assertContains(respuesta, "no genera automáticamente adeudos")
        self.assertContains(respuesta, "Pago de cita anulado")
        self.assertContains(respuesta, "Comisiones con incidencia activa")

    def test_reactivacion_elimina_incidencia_activa_sin_borrar_historia(self):
        pagada = self.crear_borrador([self.crear_comision(1)])
        self.pagar(pagada)
        comision = pagada.lineas.get().comision
        comision.estado = ComisionCaptacion.ESTADO_SUSPENDIDA
        comision.save(update_fields=["estado"])
        self.assertEqual(obtener_resumen_liquidaciones().cantidad_con_incidencia, 1)

        comision.estado = ComisionCaptacion.ESTADO_PENDIENTE_PAGO
        comision.save(update_fields=["estado"])

        self.assertEqual(obtener_resumen_liquidaciones().cantidad_con_incidencia, 0)
        self.assertFalse(liquidaciones_con_incidencia_activa().exists())

    def test_cancelada_muestra_evidencia_y_no_total_provisional(self):
        liquidacion = self.crear_borrador([self.crear_comision(1)])
        cancelar_borrador_liquidacion(
            liquidacion=liquidacion,
            motivo="Borrador incorrecto",
            usuario=self.staff,
        )
        respuesta = self.client.get(
            reverse("ventas:liquidacion_detalle", args=[liquidacion.pk])
        )
        self.assertContains(respuesta, "Evidencia de cancelación")
        self.assertContains(respuesta, "Borrador incorrecto")

    def test_permiso_de_consulta_es_independiente(self):
        usuario = User.objects.create_user("auditor_7e")
        self.client.force_login(usuario)
        self.assertEqual(
            self.client.get(reverse("ventas:liquidaciones_panel")).status_code,
            403,
        )
        usuario.user_permissions.add(Permission.objects.get(codename="view_liquidaciones"))
        usuario = User.objects.get(pk=usuario.pk)
        self.client.force_login(usuario)
        self.assertEqual(
            self.client.get(reverse("ventas:liquidaciones_panel")).status_code,
            200,
        )
        self.assertFalse(usuario.has_perm("ventas.pay_liquidacion"))

    def test_paginacion_es_de_25(self):
        LiquidacionComisiones.objects.bulk_create(
            [
                LiquidacionComisiones(
                    captador=self.captador,
                    beneficiario_nombre_snapshot=f"Beneficiario {indice}",
                )
                for indice in range(26)
            ]
        )
        respuesta = self.client.get(reverse("ventas:liquidaciones_panel"))
        self.assertEqual(len(respuesta.context["pagina"]), 25)
        self.assertEqual(respuesta.context["pagina"].paginator.num_pages, 2)
