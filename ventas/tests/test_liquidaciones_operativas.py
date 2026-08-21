from datetime import time
from decimal import Decimal

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from clinica.models import CorteSemanal, LineaNomina, Paciente, Terapeuta
from clinica.tests_helpers import ClinicaTestDataMixin
from clinica.models import MovimientoEconomicoCita
from ventas.models import (
    Captacion,
    Captador,
    ComisionCaptacion,
    EventoLiquidacion,
    LineaLiquidacionComision,
    LiquidacionComisiones,
)
from ventas.queries import comisiones_disponibles_para_liquidacion
from ventas.services import (
    OperacionLiquidacionError,
    agregar_comisiones_borrador,
    borrador_tiene_comisiones_no_elegibles,
    cancelar_borrador_liquidacion,
    crear_borrador_liquidacion,
    retirar_comision_borrador,
    total_provisional_liquidacion,
)


class LiquidacionesOperativasMixin(ClinicaTestDataMixin):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.captador = Captador.objects.create(
            tipo=Captador.TIPO_EXTERNO,
            nombre_externo="Escuela ABC",
            tipo_organizacion=Captador.ORG_ESCUELA,
        )

    def crear_paciente(self, indice):
        return Paciente.objects.create(
            nombre=f"Paciente LiquidaciÃ³n {indice}",
            fecha_nacimiento=self.paciente.fecha_nacimiento,
            sexo="Femenino",
            telefono=f"555100{indice:04d}",
            servicio_inicial=self.servicio,
            division=self.division,
        )

    def crear_comision(
        self,
        indice,
        *,
        captador=None,
        monto="40.00",
        estado=ComisionCaptacion.ESTADO_PENDIENTE_PAGO,
    ):
        captador = captador or self.captador
        paciente = self.crear_paciente(indice)
        captacion = Captacion.objects.create(
            paciente=paciente,
            captador=captador,
            codigo=captador.codigo_activo,
            captador_nombre_snapshot=captador.nombre_display,
            captador_tipo_snapshot=captador.clasificacion_display,
        )
        cita = self.crear_cita(
            paciente=paciente,
            hora=time(9 + indice, 0),
        )
        return ComisionCaptacion.objects.create(
            captacion=captacion,
            cita_generadora=cita,
            captador_nombre_snapshot=captador.nombre_display,
            paciente_nombre_snapshot=paciente.nombre,
            porcentaje_aplicado=7,
            base_calculo=Decimal("400.00"),
            monto_calculado=Decimal(monto),
            estado=estado,
        )

    def crear_borrador(self, comisiones):
        return crear_borrador_liquidacion(
            captador=self.captador,
            comisiones=comisiones,
            usuario=self.staff,
        )


class ServiciosLiquidacionTests(LiquidacionesOperativasMixin, TestCase):
    def test_crea_borrador_atomico_con_total_provisional(self):
        comisiones = [
            self.crear_comision(1, monto="40.00"),
            self.crear_comision(2, monto="28.00"),
            self.crear_comision(3, monto="35.00"),
        ]
        liquidacion = self.crear_borrador(comisiones)

        self.assertEqual(liquidacion.estado, "borrador")
        self.assertEqual(liquidacion.beneficiario_nombre_snapshot, "Escuela ABC")
        self.assertEqual(liquidacion.lineas.filter(activa=True).count(), 3)
        self.assertEqual(total_provisional_liquidacion(liquidacion), Decimal("103.00"))
        self.assertIsNone(liquidacion.monto_total_snapshot)

    def test_no_mezcla_captadores_ni_crea_parcialmente(self):
        otro = Captador.objects.create(
            tipo=Captador.TIPO_EXTERNO,
            nombre_externo="Escuela B",
            tipo_organizacion=Captador.ORG_ESCUELA,
        )
        comisiones = [self.crear_comision(1), self.crear_comision(2, captador=otro)]
        with self.assertRaises(OperacionLiquidacionError):
            self.crear_borrador(comisiones)
        self.assertFalse(LiquidacionComisiones.objects.exists())
        self.assertFalse(LineaLiquidacionComision.objects.exists())

    def test_suspendida_o_reservada_hacen_fallar_toda_la_seleccion(self):
        valida = self.crear_comision(1)
        suspendida = self.crear_comision(2, estado="suspendida")
        with self.assertRaises(OperacionLiquidacionError):
            self.crear_borrador([valida, suspendida])
        self.assertFalse(LiquidacionComisiones.objects.exists())

        reservada = self.crear_comision(3)
        self.crear_borrador([reservada])
        with self.assertRaises(OperacionLiquidacionError):
            crear_borrador_liquidacion(
                captador=self.captador,
                comisiones=[valida, reservada],
                usuario=self.staff,
            )
        self.assertEqual(LiquidacionComisiones.objects.count(), 1)

    def test_doble_envio_no_crea_segundo_borrador(self):
        comision = self.crear_comision(1)
        self.crear_borrador([comision])
        with self.assertRaises(OperacionLiquidacionError) as contexto:
            self.crear_borrador([comision])
        self.assertEqual(contexto.exception.codigo, "comision_no_disponible")
        self.assertEqual(LiquidacionComisiones.objects.count(), 1)

    def test_terapeuta_rechazado_e_interno_no_clinico_aceptado(self):
        usuario_terapeuta = User.objects.create_user("captador_terapeuta")
        Terapeuta.objects.create(usuario=usuario_terapeuta, nombre="ClÃ­nico")
        captador_terapeuta = Captador.objects.create(
            tipo=Captador.TIPO_INTERNO,
            usuario=usuario_terapeuta,
        )
        comision_terapeuta = self.crear_comision(1, captador=captador_terapeuta)
        with self.assertRaises(OperacionLiquidacionError) as contexto:
            crear_borrador_liquidacion(
                captador=captador_terapeuta,
                comisiones=[comision_terapeuta],
                usuario=self.staff,
            )
        self.assertEqual(contexto.exception.codigo, "captador_no_elegible")

        usuario_interno = User.objects.create_user("captador_administrativo")
        captador_interno = Captador.objects.create(
            tipo=Captador.TIPO_INTERNO,
            usuario=usuario_interno,
        )
        comision_interna = self.crear_comision(2, captador=captador_interno)
        liquidacion = crear_borrador_liquidacion(
            captador=captador_interno,
            comisiones=[comision_interna],
            usuario=self.staff,
        )
        self.assertEqual(liquidacion.captador, captador_interno)

    def test_agrega_y_rechaza_otro_captador_sin_parcialidad(self):
        primera = self.crear_comision(1)
        segunda = self.crear_comision(2)
        liquidacion = self.crear_borrador([primera])
        agregar_comisiones_borrador(
            liquidacion=liquidacion,
            comisiones=[segunda],
            usuario=self.staff,
        )
        self.assertEqual(liquidacion.lineas.filter(activa=True).count(), 2)

        otro = Captador.objects.create(
            tipo=Captador.TIPO_EXTERNO,
            nombre_externo="Escuela B",
            tipo_organizacion=Captador.ORG_ESCUELA,
        )
        ajena = self.crear_comision(3, captador=otro)
        tercera = self.crear_comision(4)
        with self.assertRaises(OperacionLiquidacionError):
            agregar_comisiones_borrador(
                liquidacion=liquidacion,
                comisiones=[tercera, ajena],
                usuario=self.staff,
            )
        self.assertEqual(liquidacion.lineas.filter(activa=True).count(), 2)

    def test_retirar_conserva_historico_y_permite_reutilizar(self):
        comision = self.crear_comision(1)
        liquidacion = self.crear_borrador([comision])
        linea_original = retirar_comision_borrador(
            liquidacion=liquidacion,
            comision=comision,
            usuario=self.staff,
            motivo="CorrecciÃ³n administrativa",
        )
        self.assertFalse(linea_original.activa)
        self.assertIsNotNone(linea_original.retirada_en)
        self.assertEqual(linea_original.retirada_por, self.staff)
        self.assertTrue(linea_original.motivo_retiro)

        nueva = self.crear_borrador([comision])
        self.assertTrue(nueva.lineas.get().activa)
        self.assertEqual(comision.lineas_liquidacion.count(), 2)

    def test_cancelar_libera_todas_y_deja_borrador_inmutable(self):
        comisiones = [self.crear_comision(i) for i in (1, 2, 3)]
        liquidacion = self.crear_borrador(comisiones)
        cancelar_borrador_liquidacion(
            liquidacion=liquidacion,
            usuario=self.staff,
            motivo="Borrador descartado",
        )
        liquidacion.refresh_from_db()
        self.assertEqual(liquidacion.estado, "cancelada")
        self.assertEqual(liquidacion.lineas.filter(activa=True).count(), 0)
        self.assertEqual(
            comisiones_disponibles_para_liquidacion(captador=self.captador).count(),
            3,
        )
        with self.assertRaises(OperacionLiquidacionError):
            agregar_comisiones_borrador(
                liquidacion=liquidacion,
                comisiones=[comisiones[0]],
                usuario=self.staff,
            )
        with self.assertRaises(OperacionLiquidacionError):
            retirar_comision_borrador(
                liquidacion=liquidacion,
                comision=comisiones[0],
                usuario=self.staff,
                motivo="Segundo retiro",
            )

    def test_suspension_y_reactivacion_no_modifican_linea(self):
        comision = self.crear_comision(1)
        liquidacion = self.crear_borrador([comision])
        linea = liquidacion.lineas.get()
        comision.estado = ComisionCaptacion.ESTADO_SUSPENDIDA
        comision.save(update_fields=["estado"])
        self.assertTrue(borrador_tiene_comisiones_no_elegibles(liquidacion))
        linea.refresh_from_db()
        self.assertTrue(linea.activa)

        comision.estado = ComisionCaptacion.ESTADO_PENDIENTE_PAGO
        comision.save(update_fields=["estado"])
        self.assertFalse(borrador_tiene_comisiones_no_elegibles(liquidacion))
        self.assertEqual(liquidacion.lineas.filter(activa=True).count(), 1)

    def test_eventos_por_operacion_y_sin_eventos_en_fallos(self):
        primera = self.crear_comision(1)
        segunda = self.crear_comision(2)
        liquidacion = self.crear_borrador([primera])
        agregar_comisiones_borrador(
            liquidacion=liquidacion,
            comisiones=[segunda],
            usuario=self.staff,
        )
        retirar_comision_borrador(
            liquidacion=liquidacion,
            comision=segunda,
            usuario=self.staff,
            motivo="Retiro de prueba",
        )
        cancelar_borrador_liquidacion(
            liquidacion=liquidacion,
            usuario=self.staff,
            motivo="CancelaciÃ³n de prueba",
        )
        acciones = list(liquidacion.eventos.values_list("accion", flat=True))
        self.assertIn(EventoLiquidacion.ACCION_LIQUIDACION_CREADA, acciones)
        self.assertEqual(acciones.count(EventoLiquidacion.ACCION_COMISION_AGREGADA), 2)
        self.assertIn(EventoLiquidacion.ACCION_COMISION_RETIRADA, acciones)
        self.assertIn(EventoLiquidacion.ACCION_BORRADOR_CANCELADO, acciones)
        cantidad = len(acciones)
        with self.assertRaises(OperacionLiquidacionError):
            cancelar_borrador_liquidacion(
                liquidacion=liquidacion,
                usuario=self.staff,
                motivo="Duplicada",
            )
        self.assertEqual(liquidacion.eventos.count(), cantidad)

    def test_total_usa_monto_historico_y_no_crea_pagos_ni_nomina(self):
        comision = self.crear_comision(1, monto="28.00")
        liquidacion = self.crear_borrador([comision])
        comision.cita_generadora.costo = Decimal("9999.00")
        comision.cita_generadora.save(update_fields=["costo"])
        self.servicio.precio = Decimal("8888.00")
        self.servicio.save(update_fields=["precio"])
        self.assertEqual(total_provisional_liquidacion(liquidacion), Decimal("28.00"))
        self.assertFalse(MovimientoEconomicoCita.objects.exists())
        self.assertFalse(CorteSemanal.objects.exists())
        self.assertFalse(LineaNomina.objects.exists())


class InterfazLiquidacionesTests(LiquidacionesOperativasMixin, TestCase):
    def otorgar(self, usuario, *codenames):
        usuario.user_permissions.add(
            *Permission.objects.filter(codename__in=codenames)
        )

    def test_panel_solo_muestra_checkbox_para_disponibles(self):
        disponible = self.crear_comision(1)
        suspendida = self.crear_comision(2, estado="suspendida")
        reservada = self.crear_comision(3)
        usuario_terapeuta = User.objects.create_user("terapeuta_panel")
        Terapeuta.objects.create(
            usuario=usuario_terapeuta,
            nombre="Terapeuta Panel",
        )
        captador_terapeuta = Captador.objects.create(
            tipo=Captador.TIPO_INTERNO,
            usuario=usuario_terapeuta,
        )
        comision_terapeuta = self.crear_comision(
            4,
            captador=captador_terapeuta,
        )
        self.crear_borrador([reservada])
        self.client.force_login(self.staff)
        response = self.client.get(reverse("ventas:comisiones_panel"))
        self.assertContains(
            response,
            f'aria-label="Seleccionar comisión {disponible.pk}"',
        )
        self.assertNotContains(
            response,
            f'aria-label="Seleccionar comisión {suspendida.pk}"',
        )
        self.assertNotContains(
            response,
            f'aria-label="Seleccionar comisión {reservada.pk}"',
        )
        self.assertNotContains(
            response,
            f'aria-label="Seleccionar comisiÃ³n {comision_terapeuta.pk}"',
        )

    def test_permisos_separan_crear_modificar_y_cancelar(self):
        comision = self.crear_comision(1)
        usuario = User.objects.create_user("operador_liquidaciones")
        self.client.force_login(usuario)
        url_crear = reverse("ventas:liquidacion_crear")
        response = self.client.post(url_crear, {"comisiones": [comision.pk]})
        self.assertEqual(response.status_code, 403)

        self.otorgar(usuario, "create_liquidacion")
        response = self.client.post(url_crear, {"comisiones": [comision.pk]})
        self.assertEqual(response.status_code, 302)
        liquidacion = LiquidacionComisiones.objects.get()

        url_agregar = reverse("ventas:liquidacion_agregar", args=[liquidacion.pk])
        response = self.client.post(url_agregar, {"comisiones": []})
        self.assertEqual(response.status_code, 403)
        url_cancelar = reverse("ventas:liquidacion_cancelar", args=[liquidacion.pk])
        response = self.client.post(url_cancelar, {"motivo": "No autorizado"})
        self.assertEqual(response.status_code, 403)

    def test_detalle_muestra_total_y_comision_suspendida(self):
        comision = self.crear_comision(1, monto="40.00")
        liquidacion = self.crear_borrador([comision])
        comision.estado = ComisionCaptacion.ESTADO_SUSPENDIDA
        comision.save(update_fields=["estado"])
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("ventas:liquidacion_detalle", args=[liquidacion.pk])
        )
        self.assertContains(response, "Total provisional")
        self.assertContains(response, "Suspendida / no elegible")
        self.assertNotContains(response, "MÃ©todo de pago")
        self.assertNotContains(response, "Referencia")
