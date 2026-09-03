from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from ventas.models import Captacion, ComisionCaptacion, LiquidacionComisiones

from .models import (
    Cita,
    CobroCita,
    CorteSemanal,
    LineaNomina,
    MovimientoEconomicoCita,
    Pago,
    ReglaBeneficioReferido,
    TarifaServicio,
)
from .services_pagos import (
    anular_pago,
    confirmar_pago,
    registrar_diferencia_pago,
    registrar_pago,
)
from .tests_helpers import ClinicaTestDataMixin


class PagoInfraestructuraTests(ClinicaTestDataMixin, TestCase):
    def setUp(self):
        self.cita = self.crear_cita(
            costo=Decimal("487.50"),
            metodo_pago="Transferencia",
            estatus=Cita.ESTATUS_CONFIRMADA,
        )

    def registrar_terapeuta(self, **cambios):
        datos = {
            "cita": self.cita,
            "importe_esperado": Decimal("500.00"),
            "importe_reportado": Decimal("450.00"),
            "metodo_pago": "Efectivo",
            "origen_registro": Pago.ORIGEN_TERAPEUTA,
            "registrado_por": self.usuario_terapeuta,
        }
        datos.update(cambios)
        return registrar_pago(**datos)

    def test_registra_pago_pendiente_del_terapeuta_con_trazabilidad(self):
        antes = timezone.now()
        pago, creado = self.registrar_terapeuta()

        self.assertTrue(creado)
        self.assertEqual(pago.cobro.cita, self.cita)
        self.assertEqual(pago.cobro.importe_esperado, Decimal("500.00"))
        self.assertEqual(pago.importe_reportado, Decimal("450.00"))
        self.assertEqual(pago.metodo_pago, "Efectivo")
        self.assertEqual(pago.origen_registro, Pago.ORIGEN_TERAPEUTA)
        self.assertEqual(pago.estado, Pago.ESTADO_PENDIENTE_VERIFICACION)
        self.assertEqual(pago.registrado_por, self.usuario_terapeuta)
        self.assertGreaterEqual(pago.registrado_en, antes)
        self.assertIsNone(pago.importe_verificado)
        self.assertIsNone(pago.verificado_por)
        self.assertIsNone(pago.verificado_en)

        pago.refresh_from_db()
        pago.cobro.refresh_from_db()
        self.assertIsInstance(pago.cobro.importe_esperado, Decimal)
        self.assertIsInstance(pago.importe_reportado, Decimal)

    def test_recepcion_registra_pago_confirmado(self):
        pago, creado = registrar_pago(
            cita=self.cita,
            importe_esperado="450.00",
            importe_reportado="450.00",
            metodo_pago="Debito",
            origen_registro=Pago.ORIGEN_RECEPCION,
            registrado_por=self.staff,
        )

        self.assertTrue(creado)
        self.assertEqual(pago.estado, Pago.ESTADO_CONFIRMADO)
        self.assertEqual(pago.origen_registro, Pago.ORIGEN_RECEPCION)
        self.assertEqual(pago.importe_verificado, Decimal("450.00"))
        self.assertEqual(pago.verificado_por, self.staff)
        self.assertIsNotNone(pago.verificado_en)

    def test_cobro_es_unico_y_congela_importe_esperado(self):
        primero, _ = registrar_pago(
            cita=self.cita,
            importe_esperado="450.00",
            importe_reportado="400.00",
            metodo_pago="Efectivo",
            origen_registro=Pago.ORIGEN_RECEPCION,
            registrado_por=self.staff,
        )
        self.cita.costo = Decimal("900.00")
        self.cita.save(update_fields=("costo",))

        segundo, _ = registrar_pago(
            cita=self.cita,
            importe_esperado="900.00",
            importe_reportado="50.00",
            metodo_pago="Transferencia",
            origen_registro=Pago.ORIGEN_RECEPCION,
            registrado_por=self.staff,
        )

        primero.cobro.refresh_from_db()
        self.assertEqual(CobroCita.objects.filter(cita=self.cita).count(), 1)
        self.assertEqual(primero.cobro_id, segundo.cobro_id)
        self.assertEqual(primero.cobro.importe_esperado, Decimal("450.00"))

    def test_dos_pagos_parciales_conservan_fecha_metodo_y_usuario(self):
        dia_uno = timezone.now()
        dia_dos = dia_uno + timedelta(days=1)
        with patch("clinica.services_pagos.timezone.now", return_value=dia_uno):
            primero, _ = self.registrar_terapeuta(
                importe_esperado=Decimal("450.00"),
                importe_reportado=Decimal("400.00"),
                metodo_pago="Efectivo",
            )
        confirmar_pago(
            pago=primero,
            importe_verificado=Decimal("400.00"),
            verificado_por=self.staff,
        )
        with patch("clinica.services_pagos.timezone.now", return_value=dia_dos):
            segundo, _ = registrar_pago(
                cita=self.cita,
                importe_esperado=Decimal("999.00"),
                importe_reportado=Decimal("50.00"),
                metodo_pago="Transferencia",
                origen_registro=Pago.ORIGEN_RECEPCION,
                registrado_por=self.staff,
            )

        self.assertNotEqual(primero.pk, segundo.pk)
        self.assertEqual(primero.cobro_id, segundo.cobro_id)
        self.assertEqual(primero.registrado_en, dia_uno)
        self.assertEqual(segundo.registrado_en, dia_dos)
        self.assertEqual(primero.metodo_pago, "Efectivo")
        self.assertEqual(segundo.metodo_pago, "Transferencia")
        self.assertEqual(primero.registrado_por, self.usuario_terapeuta)
        self.assertEqual(segundo.registrado_por, self.staff)

    def test_pago_confirmado_parcial_calcula_pendiente(self):
        pago, _ = self.registrar_terapeuta(
            importe_esperado=Decimal("450.00"),
            importe_reportado=Decimal("400.00"),
        )
        confirmar_pago(
            pago=pago,
            importe_verificado=Decimal("400.00"),
            verificado_por=self.staff,
        )

        self.assertEqual(pago.cobro.total_confirmado, Decimal("400.00"))
        self.assertEqual(pago.cobro.saldo, Decimal("50.00"))
        self.assertEqual(
            pago.cobro.situacion_saldo,
            CobroCita.SITUACION_PENDIENTE,
        )

    def test_pago_pendiente_no_reduce_saldo_oficial(self):
        pago, _ = self.registrar_terapeuta(
            importe_esperado=Decimal("450.00"),
            importe_reportado=Decimal("400.00"),
        )

        self.assertEqual(pago.cobro.total_confirmado, Decimal("0.00"))
        self.assertEqual(pago.cobro.saldo, Decimal("450.00"))

    def test_dos_pagos_confirmados_calculan_saldado(self):
        primero, _ = registrar_pago(
            cita=self.cita,
            importe_esperado=Decimal("450.00"),
            importe_reportado=Decimal("400.00"),
            metodo_pago="Efectivo",
            origen_registro=Pago.ORIGEN_RECEPCION,
            registrado_por=self.staff,
        )
        segundo, _ = registrar_pago(
            cita=self.cita,
            importe_esperado=Decimal("450.00"),
            importe_reportado=Decimal("50.00"),
            metodo_pago="Transferencia",
            origen_registro=Pago.ORIGEN_RECEPCION,
            registrado_por=self.staff,
        )

        self.assertNotEqual(primero.pk, segundo.pk)
        self.assertEqual(primero.cobro.total_confirmado, Decimal("450.00"))
        self.assertEqual(primero.cobro.saldo, Decimal("0.00"))
        self.assertEqual(
            primero.cobro.situacion_saldo,
            CobroCita.SITUACION_SALDADO,
        )

    def test_sobrepago_calcula_saldo_a_favor(self):
        pago, _ = registrar_pago(
            cita=self.cita,
            importe_esperado=Decimal("450.00"),
            importe_reportado=Decimal("500.00"),
            metodo_pago="Efectivo",
            origen_registro=Pago.ORIGEN_RECEPCION,
            registrado_por=self.staff,
        )

        self.assertEqual(pago.cobro.total_confirmado, Decimal("500.00"))
        self.assertEqual(pago.cobro.saldo, Decimal("-50.00"))
        self.assertEqual(
            pago.cobro.situacion_saldo,
            CobroCita.SITUACION_A_FAVOR,
        )

    def test_pago_anulado_no_cuenta_en_saldo(self):
        pago, _ = registrar_pago(
            cita=self.cita,
            importe_esperado=Decimal("450.00"),
            importe_reportado=Decimal("400.00"),
            metodo_pago="Efectivo",
            origen_registro=Pago.ORIGEN_RECEPCION,
            registrado_por=self.staff,
        )
        anular_pago(
            pago=pago,
            anulado_por=self.staff,
            motivo="Entrada capturada por error.",
        )

        self.assertEqual(pago.cobro.total_confirmado, Decimal("0.00"))
        self.assertEqual(pago.cobro.saldo, Decimal("450.00"))

    def test_servicio_rechaza_pase_como_pago_monetario(self):
        with self.assertRaises(ValidationError):
            self.registrar_terapeuta(metodo_pago="Pase")

        self.assertFalse(CobroCita.objects.filter(cita=self.cita).exists())
        self.assertFalse(Pago.objects.exists())

    def test_importes_cero_son_validos(self):
        pago, creado = self.registrar_terapeuta(
            importe_esperado=Decimal("0.00"),
            importe_reportado=Decimal("0.00"),
        )
        self.assertTrue(creado)
        self.assertEqual(pago.cobro.importe_esperado, Decimal("0.00"))
        self.assertEqual(pago.importe_reportado, Decimal("0.00"))

    def test_rechaza_importes_invalidos(self):
        for campo, valor in (
            ("importe_esperado", Decimal("-0.01")),
            ("importe_reportado", Decimal("-1.00")),
            ("importe_reportado", "no-es-un-importe"),
            ("importe_reportado", True),
        ):
            with self.subTest(campo=campo, valor=valor):
                with self.assertRaises(ValidationError):
                    self.registrar_terapeuta(**{campo: valor})
        self.assertFalse(Pago.objects.exists())

    def test_rechaza_metodo_origen_y_actor_invalidos(self):
        for cambios in (
            {"metodo_pago": "Criptomoneda"},
            {"origen_registro": "desconocido"},
            {"registrado_por": None},
        ):
            with self.subTest(cambios=cambios):
                with self.assertRaises(ValidationError):
                    self.registrar_terapeuta(**cambios)
        self.assertFalse(Pago.objects.exists())

    def test_registro_identico_es_idempotente(self):
        primero, creado_primero = self.registrar_terapeuta()
        segundo, creado_segundo = self.registrar_terapeuta()

        self.assertTrue(creado_primero)
        self.assertFalse(creado_segundo)
        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(Pago.objects.count(), 1)

    def test_registro_incompatible_no_duplica_pago_activo(self):
        self.registrar_terapeuta()
        with self.assertRaises(ValidationError):
            self.registrar_terapeuta(importe_reportado=Decimal("400.00"))
        self.assertEqual(Pago.objects.count(), 1)

    def test_constraint_impide_dos_pagos_activos_del_checkout_terapeuta(self):
        primero, _ = self.registrar_terapeuta()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Pago.objects.create(
                    cobro=primero.cobro,
                    importe_reportado=Decimal("500.00"),
                    metodo_pago="Efectivo",
                    origen_registro=Pago.ORIGEN_TERAPEUTA,
                    registrado_por=self.usuario_terapeuta,
                )
        self.assertEqual(Pago.objects.count(), 1)

    def test_confirmacion_actualiza_el_pago_sin_crear_otro(self):
        pago, _ = self.registrar_terapeuta()
        confirmado, actualizado = confirmar_pago(
            pago=pago,
            importe_verificado=Decimal("450.00"),
            verificado_por=self.staff,
        )

        self.assertTrue(actualizado)
        self.assertEqual(confirmado.pk, pago.pk)
        self.assertEqual(confirmado.estado, Pago.ESTADO_CONFIRMADO)
        self.assertEqual(confirmado.importe_verificado, Decimal("450.00"))
        self.assertEqual(confirmado.verificado_por, self.staff)
        self.assertIsNotNone(confirmado.verificado_en)
        self.assertEqual(Pago.objects.count(), 1)

    def test_confirmacion_repetida_compatible_es_idempotente(self):
        pago, _ = self.registrar_terapeuta()
        confirmado, _ = confirmar_pago(
            pago=pago,
            importe_verificado="450.00",
            verificado_por=self.staff,
        )
        verificado_en_original = confirmado.verificado_en

        repetido, actualizado = confirmar_pago(
            pago=confirmado,
            importe_verificado="450.00",
            verificado_por=self.staff,
        )
        self.assertFalse(actualizado)
        self.assertEqual(repetido.verificado_en, verificado_en_original)
        self.assertEqual(Pago.objects.count(), 1)

    def test_confirmacion_incompatible_se_rechaza(self):
        pago, _ = self.registrar_terapeuta()
        with self.assertRaises(ValidationError):
            confirmar_pago(
                pago=pago,
                importe_verificado=Decimal("400.00"),
                verificado_por=self.staff,
            )
        pago.refresh_from_db()
        self.assertEqual(pago.estado, Pago.ESTADO_PENDIENTE_VERIFICACION)
        self.assertIsNone(pago.importe_verificado)

    def test_diferencia_conserva_importe_reportado_y_trazabilidad(self):
        pago, _ = self.registrar_terapeuta()
        conciliado, actualizado = registrar_diferencia_pago(
            pago=pago,
            importe_verificado=Decimal("400.00"),
            observacion="Recepción contó 400 pesos.",
            verificado_por=self.staff,
        )

        self.assertTrue(actualizado)
        self.assertEqual(conciliado.estado, Pago.ESTADO_CON_DIFERENCIA)
        self.assertEqual(conciliado.importe_reportado, Decimal("450.00"))
        self.assertEqual(conciliado.importe_verificado, Decimal("400.00"))
        self.assertEqual(conciliado.verificado_por, self.staff)
        self.assertIsNotNone(conciliado.verificado_en)
        self.assertEqual(
            conciliado.observacion_diferencia,
            "Recepción contó 400 pesos.",
        )

    def test_diferencia_requiere_importes_distintos_y_observacion(self):
        pago, _ = self.registrar_terapeuta()
        for importe, observacion in (
            (Decimal("450.00"), "Coinciden"),
            (Decimal("400.00"), ""),
        ):
            with self.subTest(importe=importe, observacion=observacion):
                with self.assertRaises(ValidationError):
                    registrar_diferencia_pago(
                        pago=pago,
                        importe_verificado=importe,
                        observacion=observacion,
                        verificado_por=self.staff,
                    )

    def test_anulacion_conserva_registro_y_trazabilidad(self):
        pago, _ = self.registrar_terapeuta()
        anulado, actualizado = anular_pago(
            pago=pago,
            anulado_por=self.staff,
            motivo="Registro capturado por error.",
        )

        self.assertTrue(actualizado)
        self.assertEqual(anulado.estado, Pago.ESTADO_ANULADO)
        self.assertEqual(anulado.anulado_por, self.staff)
        self.assertIsNotNone(anulado.anulado_en)
        self.assertEqual(anulado.motivo_anulacion, "Registro capturado por error.")
        self.assertTrue(Pago.objects.filter(pk=pago.pk).exists())

        repetido, actualizado_repetido = anular_pago(
            pago=anulado,
            anulado_por=self.staff,
            motivo="Intento repetido.",
        )
        self.assertFalse(actualizado_repetido)
        self.assertEqual(repetido.motivo_anulacion, "Registro capturado por error.")

    def test_permite_reemplazo_controlado_despues_de_anulacion(self):
        primero, _ = self.registrar_terapeuta()
        anular_pago(
            pago=primero,
            anulado_por=self.staff,
            motivo="Se reemplazará por el dato correcto.",
        )

        reemplazo, creado = self.registrar_terapeuta(
            importe_reportado=Decimal("425.00")
        )
        self.assertTrue(creado)
        self.assertNotEqual(reemplazo.pk, primero.pk)
        self.assertEqual(Pago.objects.count(), 2)
        self.assertEqual(
            Pago.objects.exclude(estado=Pago.ESTADO_ANULADO).count(),
            1,
        )

    def test_modelo_rechaza_estados_sin_trazabilidad_requerida(self):
        cobro = CobroCita.objects.create(
            cita=self.cita,
            importe_esperado=Decimal("500.00"),
        )
        pago = Pago(
            cobro=cobro,
            importe_reportado=Decimal("450.00"),
            metodo_pago="Efectivo",
            origen_registro=Pago.ORIGEN_TERAPEUTA,
            registrado_por=self.usuario_terapeuta,
            estado=Pago.ESTADO_CONFIRMADO,
        )
        with self.assertRaises(ValidationError):
            pago.full_clean()

        pago.estado = Pago.ESTADO_ANULADO
        with self.assertRaises(ValidationError):
            pago.full_clean()

    def test_servicios_no_modifican_cita_ni_otros_modulos(self):
        cita_antes = {
            "estatus": self.cita.estatus,
            "costo": self.cita.costo,
            "metodo_pago": self.cita.metodo_pago,
            "precio_servicio_base_snapshot": self.cita.precio_servicio_base_snapshot,
            "descuento_captacion_porcentaje_snapshot": (
                self.cita.descuento_captacion_porcentaje_snapshot
            ),
            "importe_servicio_snapshot": self.cita.importe_servicio_snapshot,
        }
        precio_servicio_antes = self.servicio.precio
        conteos_antes = {
            "tarifas": TarifaServicio.objects.count(),
            "beneficios": ReglaBeneficioReferido.objects.count(),
            "captaciones": Captacion.objects.count(),
            "comisiones": ComisionCaptacion.objects.count(),
            "movimientos": MovimientoEconomicoCita.objects.count(),
            "cortes": CorteSemanal.objects.count(),
            "lineas_nomina": LineaNomina.objects.count(),
            "liquidaciones": LiquidacionComisiones.objects.count(),
        }

        pago, _ = self.registrar_terapeuta()
        registrar_diferencia_pago(
            pago=pago,
            importe_verificado=Decimal("400.00"),
            observacion="Diferencia de aislamiento.",
            verificado_por=self.staff,
        )

        self.cita.refresh_from_db()
        self.servicio.refresh_from_db()
        self.assertEqual(
            {
                "estatus": self.cita.estatus,
                "costo": self.cita.costo,
                "metodo_pago": self.cita.metodo_pago,
                "precio_servicio_base_snapshot": self.cita.precio_servicio_base_snapshot,
                "descuento_captacion_porcentaje_snapshot": (
                    self.cita.descuento_captacion_porcentaje_snapshot
                ),
                "importe_servicio_snapshot": self.cita.importe_servicio_snapshot,
            },
            cita_antes,
        )
        self.assertEqual(self.servicio.precio, precio_servicio_antes)
        self.assertEqual(
            {
                "tarifas": TarifaServicio.objects.count(),
                "beneficios": ReglaBeneficioReferido.objects.count(),
                "captaciones": Captacion.objects.count(),
                "comisiones": ComisionCaptacion.objects.count(),
                "movimientos": MovimientoEconomicoCita.objects.count(),
                "cortes": CorteSemanal.objects.count(),
                "lineas_nomina": LineaNomina.objects.count(),
                "liquidaciones": LiquidacionComisiones.objects.count(),
            },
            conteos_antes,
        )
