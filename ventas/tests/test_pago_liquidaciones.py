from decimal import Decimal

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from clinica.models import CorteSemanal, LineaNomina, Terapeuta
from clinica.models import MovimientoEconomicoCita
from ventas.models import (
    Captador,
    ComisionCaptacion,
    EventoLiquidacion,
    LineaLiquidacionComision,
    LiquidacionComisiones,
)
from ventas.queries import (
    comisiones_disponibles_para_liquidacion,
    estado_derivado_comision,
    queryset_comisiones_panel,
)
from ventas.services import (
    OperacionLiquidacionError,
    agregar_comisiones_borrador,
    cancelar_borrador_liquidacion,
    confirmar_pago_liquidacion,
    retirar_comision_borrador,
)
from ventas.tests.test_liquidaciones_operativas import (
    LiquidacionesOperativasMixin,
)


class PagoLiquidacionesTests(LiquidacionesOperativasMixin, TestCase):
    def pagar(self, liquidacion, metodo="transferencia", referencia="ABC123"):
        return confirmar_pago_liquidacion(
            liquidacion=liquidacion,
            metodo_pago=metodo,
            referencia=referencia,
            usuario=self.staff,
        )

    def test_pago_exitoso_congela_total_y_lineas(self):
        comisiones = [
            self.crear_comision(1, monto="40.00"),
            self.crear_comision(2, monto="28.00"),
            self.crear_comision(3, monto="35.00"),
        ]
        liquidacion = self.crear_borrador(comisiones)
        self.pagar(liquidacion)
        liquidacion.refresh_from_db()

        self.assertEqual(liquidacion.estado, LiquidacionComisiones.ESTADO_PAGADA)
        self.assertEqual(liquidacion.monto_total_snapshot, Decimal("103.00"))
        self.assertEqual(liquidacion.metodo_pago, "transferencia")
        self.assertEqual(liquidacion.referencia, "ABC123")
        self.assertIsNotNone(liquidacion.pagada_en)
        self.assertEqual(liquidacion.pagada_por, self.staff)
        self.assertEqual(
            list(
                liquidacion.lineas.order_by("comision_id").values_list(
                    "monto_liquidado_snapshot",
                    flat=True,
                )
            ),
            [Decimal("40.00"), Decimal("28.00"), Decimal("35.00")],
        )
        self.assertFalse(liquidacion.lineas.filter(activa=False).exists())
        self.assertTrue(
            all(
                comision.estado == ComisionCaptacion.ESTADO_PENDIENTE_PAGO
                for comision in comisiones
            )
        )

    def test_efectivo_con_referencia_es_valido(self):
        liquidacion = self.crear_borrador([self.crear_comision(1)])
        self.pagar(liquidacion, metodo="efectivo", referencia=" RECIBO-001 ")
        liquidacion.refresh_from_db()
        self.assertEqual(liquidacion.metodo_pago, "efectivo")
        self.assertEqual(liquidacion.referencia, "RECIBO-001")

    def test_referencia_vacia_y_metodo_invalido_no_modifican(self):
        for metodo, referencia, codigo in (
            ("transferencia", "", "referencia_obligatoria"),
            ("efectivo", "   ", "referencia_obligatoria"),
            ("tarjeta", "T-1", "metodo_invalido"),
        ):
            with self.subTest(metodo=metodo, referencia=referencia):
                liquidacion = self.crear_borrador([self.crear_comision(len(LiquidacionComisiones.objects.all()) + 1)])
                with self.assertRaises(OperacionLiquidacionError) as contexto:
                    self.pagar(liquidacion, metodo=metodo, referencia=referencia)
                self.assertEqual(contexto.exception.codigo, codigo)
                liquidacion.refresh_from_db()
                self.assertEqual(liquidacion.estado, "borrador")
                self.assertIsNone(liquidacion.monto_total_snapshot)

    def test_sin_lineas_o_con_suspendida_rechaza_todo(self):
        vacia = LiquidacionComisiones.objects.create(
            captador=self.captador,
            beneficiario_nombre_snapshot=self.captador.nombre_display,
        )
        with self.assertRaises(OperacionLiquidacionError) as contexto:
            self.pagar(vacia)
        self.assertEqual(contexto.exception.codigo, "liquidacion_sin_lineas")

        comisiones = [self.crear_comision(1), self.crear_comision(2)]
        liquidacion = self.crear_borrador(comisiones)
        comisiones[1].estado = ComisionCaptacion.ESTADO_SUSPENDIDA
        comisiones[1].save(update_fields=["estado"])
        with self.assertRaises(OperacionLiquidacionError):
            self.pagar(liquidacion)
        liquidacion.refresh_from_db()
        self.assertEqual(liquidacion.estado, "borrador")
        self.assertFalse(
            liquidacion.lineas.filter(
                monto_liquidado_snapshot__isnull=False
            ).exists()
        )

    def test_captador_terapeuta_se_revalida_al_pagar(self):
        usuario = User.objects.create_user("terapeuta_pago")
        Terapeuta.objects.create(usuario=usuario, nombre="Terapeuta Pago")
        captador = Captador.objects.create(
            tipo=Captador.TIPO_INTERNO,
            usuario=usuario,
        )
        comision = self.crear_comision(1, captador=captador)
        liquidacion = LiquidacionComisiones.objects.create(
            captador=captador,
            beneficiario_nombre_snapshot=captador.nombre_display,
        )
        LineaLiquidacionComision.objects.create(
            liquidacion=liquidacion,
            comision=comision,
        )
        with self.assertRaises(OperacionLiquidacionError) as contexto:
            self.pagar(liquidacion)
        self.assertEqual(contexto.exception.codigo, "captador_no_elegible")

    def test_decimal_exacto_y_sin_recalcular_fuentes_externas(self):
        comisiones = [
            self.crear_comision(1, monto="28.35"),
            self.crear_comision(2, monto="40.10"),
            self.crear_comision(3, monto="35.55"),
        ]
        liquidacion = self.crear_borrador(comisiones)
        for comision in comisiones:
            comision.cita_generadora.costo = Decimal("9999.00")
            comision.cita_generadora.save(update_fields=["costo"])
        self.servicio.precio = Decimal("8888.00")
        self.servicio.save(update_fields=["precio"])
        self.pagar(liquidacion)
        liquidacion.refresh_from_db()
        self.assertEqual(liquidacion.monto_total_snapshot, Decimal("104.00"))

    def test_snapshots_son_inmutables_ante_cambios_posteriores(self):
        comision = self.crear_comision(1, monto="40.00")
        liquidacion = self.crear_borrador([comision])
        self.pagar(liquidacion)
        liquidacion.refresh_from_db()
        linea = liquidacion.lineas.get()
        instante_pago = liquidacion.pagada_en

        comision.monto_calculado = Decimal("999.00")
        comision.save(update_fields=["monto_calculado"])
        liquidacion.refresh_from_db()
        linea.refresh_from_db()
        self.assertEqual(liquidacion.monto_total_snapshot, Decimal("40.00"))
        self.assertEqual(linea.monto_liquidado_snapshot, Decimal("40.00"))
        self.assertEqual(liquidacion.pagada_en, instante_pago)

    def test_doble_pago_es_rechazado_y_no_duplica_evento(self):
        liquidacion = self.crear_borrador([self.crear_comision(1)])
        self.pagar(liquidacion)
        liquidacion.refresh_from_db()
        evidencia = (
            liquidacion.pagada_en,
            liquidacion.pagada_por_id,
            liquidacion.referencia,
            liquidacion.monto_total_snapshot,
        )
        with self.assertRaises(OperacionLiquidacionError):
            self.pagar(liquidacion, referencia="SEGUNDO")
        liquidacion.refresh_from_db()
        self.assertEqual(
            (
                liquidacion.pagada_en,
                liquidacion.pagada_por_id,
                liquidacion.referencia,
                liquidacion.monto_total_snapshot,
            ),
            evidencia,
        )
        self.assertEqual(
            liquidacion.eventos.filter(
                accion=EventoLiquidacion.ACCION_LIQUIDACION_PAGADA
            ).count(),
            1,
        )

    def test_pagada_rechaza_agregar_retirar_y_cancelar(self):
        comision = self.crear_comision(1)
        adicional = self.crear_comision(2)
        liquidacion = self.crear_borrador([comision])
        self.pagar(liquidacion)
        for operacion in (
            lambda: agregar_comisiones_borrador(
                liquidacion=liquidacion,
                comisiones=[adicional],
                usuario=self.staff,
            ),
            lambda: retirar_comision_borrador(
                liquidacion=liquidacion,
                comision=comision,
                usuario=self.staff,
                motivo="No permitido",
            ),
            lambda: cancelar_borrador_liquidacion(
                liquidacion=liquidacion,
                usuario=self.staff,
                motivo="No permitido",
            ),
        ):
            with self.assertRaises(OperacionLiquidacionError):
                operacion()

    def test_pagada_no_vuelve_a_disponible_y_estado_es_derivado(self):
        comision = self.crear_comision(1)
        liquidacion = self.crear_borrador([comision])
        self.pagar(liquidacion)
        self.assertNotIn(
            comision,
            comisiones_disponibles_para_liquidacion(captador=self.captador),
        )
        anotada = queryset_comisiones_panel().get(pk=comision.pk)
        self.assertEqual(estado_derivado_comision(anotada), "pagada")

    def test_pago_no_crea_pago_financiero_ni_nomina(self):
        liquidacion = self.crear_borrador([self.crear_comision(1)])
        self.pagar(liquidacion)
        self.assertFalse(MovimientoEconomicoCita.objects.exists())
        self.assertFalse(CorteSemanal.objects.exists())
        self.assertFalse(LineaNomina.objects.exists())

    def test_evento_pagada_conserva_evidencia(self):
        comision = self.crear_comision(1, monto="40.00")
        liquidacion = self.crear_borrador([comision])
        self.pagar(liquidacion, referencia="TRX-123")
        evento = liquidacion.eventos.get(
            accion=EventoLiquidacion.ACCION_LIQUIDACION_PAGADA
        )
        self.assertEqual(evento.usuario, self.staff)
        self.assertEqual(evento.detalle["monto_total"], "40.00")
        self.assertEqual(evento.detalle["referencia"], "TRX-123")
        self.assertEqual(evento.detalle["comision_ids"], [comision.pk])


class PagoLiquidacionesInterfazTests(LiquidacionesOperativasMixin, TestCase):
    def test_pago_iniciado_desde_finanzas_regresa_al_panel(self):
        liquidacion = self.crear_borrador([self.crear_comision(1)])
        self.client.force_login(self.staff)

        respuesta = self.client.post(
            reverse(
                "ventas:liquidacion_registrar_pago",
                args=[liquidacion.pk],
            ),
            {
                "metodo_pago": "transferencia",
                "referencia": "TRX-FINANZAS",
                "origen": "finanzas",
            },
        )

        self.assertRedirects(
            respuesta,
            reverse("ventas:liquidaciones_panel"),
        )
        liquidacion.refresh_from_db()
        self.assertEqual(
            liquidacion.estado,
            LiquidacionComisiones.ESTADO_PAGADA,
        )

    def test_permiso_pay_es_independiente(self):
        liquidacion = self.crear_borrador([self.crear_comision(1)])
        usuario = User.objects.create_user("finanzas_sin_permiso")
        self.client.force_login(usuario)
        url = reverse("ventas:liquidacion_registrar_pago", args=[liquidacion.pk])
        self.assertEqual(self.client.get(url).status_code, 403)

        usuario.user_permissions.add(
            Permission.objects.get(codename="pay_liquidacion")
        )
        response = self.client.post(
            url,
            {"metodo_pago": "transferencia", "referencia": "TRX-1"},
        )
        self.assertEqual(response.status_code, 302)
        liquidacion.refresh_from_db()
        self.assertEqual(liquidacion.estado, "pagada")

    def test_ui_borrador_bloqueado_y_pagado(self):
        comision = self.crear_comision(1)
        liquidacion = self.crear_borrador([comision])
        self.client.force_login(self.staff)
        detalle_url = reverse("ventas:liquidacion_detalle", args=[liquidacion.pk])
        response = self.client.get(detalle_url)
        self.assertContains(response, "Registrar pago")

        comision.estado = ComisionCaptacion.ESTADO_SUSPENDIDA
        comision.save(update_fields=["estado"])
        response = self.client.get(detalle_url)
        self.assertNotContains(response, "Registrar pago")
        self.assertContains(response, "Revísalas antes de registrar el pago")

        comision.estado = ComisionCaptacion.ESTADO_PENDIENTE_PAGO
        comision.save(update_fields=["estado"])
        confirmar_pago_liquidacion(
            liquidacion=liquidacion,
            metodo_pago="transferencia",
            referencia="TRX-2",
            usuario=self.staff,
        )
        response = self.client.get(detalle_url)
        self.assertContains(response, "Monto pagado")
        self.assertContains(response, "TRX-2")
        self.assertContains(response, "$40.00")
        self.assertNotContains(response, "Agregar seleccionadas")
        self.assertNotContains(response, "Cancelar borrador")
        self.assertNotContains(response, "Registrar pago")
