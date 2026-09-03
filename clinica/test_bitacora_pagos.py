from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import Cita, CobroCita, MovimientoEconomicoCita, Pago
from .services_pagos import anular_pago, confirmar_pago, registrar_diferencia_pago, registrar_pago
from .tests_helpers import ClinicaTestDataMixin


class BitacoraPagosSoloLecturaTests(ClinicaTestDataMixin, TestCase):
    def setUp(self):
        self.client.force_login(self.staff)

    def consultar(self):
        return self.client.get(
            reverse('bitacora_diaria'),
            {'fecha': self.fecha.isoformat()},
        )

    def registrar_pago_terapeuta(self, cita, importe='400.00'):
        return registrar_pago(
            cita=cita,
            importe_esperado='450.00',
            importe_reportado=importe,
            metodo_pago='Efectivo',
            origen_registro=Pago.ORIGEN_TERAPEUTA,
            registrado_por=self.usuario_terapeuta,
        )[0]

    def test_cita_sin_cobro_muestra_guion_y_conserva_costo(self):
        cita = self.crear_cita(
            costo=Decimal('333.37'),
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )

        response = self.consultar()

        self.assertEqual(response.status_code, 200)
        cita_contexto = response.context['citas'][0]
        self.assertIsNone(cita_contexto.pago_bitacora)
        self.assertEqual(cita_contexto.costo, Decimal('333.37'))
        self.assertContains(response, 'Registrar pago')
        self.assertContains(
            response,
            reverse('registrar_pago_recepcion', args=[cita.pk]),
        )
        self.assertContains(response, '$333')
        self.assertEqual(response.context['monto_dia'], Decimal('333.37'))

    def test_pago_pendiente_muestra_estado_e_importe_reportado(self):
        cita = self.crear_cita()
        pago = self.registrar_pago_terapeuta(cita, '400.00')

        response = self.consultar()

        cita_contexto = response.context['citas'][0]
        self.assertEqual(cita_contexto.pago_bitacora.pk, pago.pk)
        self.assertEqual(cita_contexto.importe_pago_bitacora, Decimal('400.00'))
        self.assertContains(response, 'Pendiente de verificación')
        self.assertContains(response, '$400.00')
        self.assertContains(
            response,
            reverse('confirmar_pago_recepcion', args=[pago.pk]),
        )

    def test_pago_confirmado_muestra_importe_verificado(self):
        cita = self.crear_cita()
        pago = self.registrar_pago_terapeuta(cita, '450.00')
        confirmar_pago(
            pago=pago,
            importe_verificado='450.00',
            verificado_por=self.staff,
        )

        response = self.consultar()

        cita_contexto = response.context['citas'][0]
        self.assertEqual(cita_contexto.pago_bitacora.estado, Pago.ESTADO_CONFIRMADO)
        self.assertEqual(cita_contexto.importe_pago_bitacora, Decimal('450.00'))
        self.assertContains(response, 'Confirmado')
        self.assertContains(response, '$450.00')
        self.assertNotContains(
            response,
            reverse('confirmar_pago_recepcion', args=[pago.pk]),
        )

    def test_pago_con_diferencia_muestra_importe_verificado(self):
        cita = self.crear_cita()
        pago = self.registrar_pago_terapeuta(cita, '400.00')
        registrar_diferencia_pago(
            pago=pago,
            importe_verificado='350.00',
            observacion='Recepción verificó un importe distinto.',
            verificado_por=self.staff,
        )

        response = self.consultar()

        cita_contexto = response.context['citas'][0]
        self.assertEqual(
            cita_contexto.pago_bitacora.estado,
            Pago.ESTADO_CON_DIFERENCIA,
        )
        self.assertEqual(cita_contexto.importe_pago_bitacora, Decimal('350.00'))
        self.assertContains(response, 'Con diferencia')
        self.assertContains(response, '$350.00')
        self.assertNotContains(
            response,
            reverse('confirmar_pago_recepcion', args=[pago.pk]),
        )

    def test_pago_anulado_no_se_presenta_como_cobro_valido(self):
        cita = self.crear_cita()
        pago = self.registrar_pago_terapeuta(cita)
        anular_pago(
            pago=pago,
            anulado_por=self.staff,
            motivo='Registro de prueba anulado.',
        )

        response = self.consultar()

        self.assertIsNone(response.context['citas'][0].pago_bitacora)
        self.assertNotContains(response, 'Anulado')
        self.assertNotContains(
            response,
            reverse('confirmar_pago_recepcion', args=[pago.pk]),
        )

    def test_post_confirma_mismo_pago_sin_modificar_cita_ni_movimientos(self):
        cita = self.crear_cita(
            costo=Decimal('777.00'),
            metodo_pago='Transferencia',
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )
        pago = self.registrar_pago_terapeuta(cita, '450.00')
        pago_id = pago.pk
        cita_original = (cita.costo, cita.metodo_pago, cita.estatus)
        total_pagos = Pago.objects.count()
        total_movimientos = MovimientoEconomicoCita.objects.count()

        respuesta = self.client.post(
            reverse('confirmar_pago_recepcion', args=[pago.pk]),
        )

        self.assertRedirects(
            respuesta,
            f"{reverse('bitacora_diaria')}?fecha={cita.fecha.isoformat()}",
        )
        pago.refresh_from_db()
        cita.refresh_from_db()
        self.assertEqual(pago.pk, pago_id)
        self.assertEqual(Pago.objects.count(), total_pagos)
        self.assertEqual(pago.estado, Pago.ESTADO_CONFIRMADO)
        self.assertEqual(pago.importe_verificado, pago.importe_reportado)
        self.assertEqual(pago.verificado_por, self.staff)
        self.assertIsNotNone(pago.verificado_en)
        self.assertEqual((cita.costo, cita.metodo_pago, cita.estatus), cita_original)
        self.assertEqual(
            MovimientoEconomicoCita.objects.count(),
            total_movimientos,
        )

    def test_segundo_post_es_idempotente_y_mantiene_ingreso_legacy(self):
        cita = self.crear_cita(
            costo=Decimal('333.37'),
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )
        pago = self.registrar_pago_terapeuta(cita, '450.00')
        url = reverse('confirmar_pago_recepcion', args=[pago.pk])

        self.client.post(url)
        primera_fecha = Pago.objects.get(pk=pago.pk).verificado_en
        self.client.post(url)

        pago.refresh_from_db()
        response = self.consultar()
        self.assertEqual(Pago.objects.filter(pk=pago.pk).count(), 1)
        self.assertEqual(pago.verificado_en, primera_fecha)
        self.assertEqual(response.context['monto_dia'], Decimal('333.37'))

    def test_prioriza_pendiente_terapeuta_sobre_otro_pago_mas_reciente(self):
        cita = self.crear_cita()
        pendiente = self.registrar_pago_terapeuta(cita, '50.00')
        registrar_pago(
            cita=cita,
            importe_esperado='999.00',
            importe_reportado='400.00',
            metodo_pago='Transferencia',
            origen_registro=Pago.ORIGEN_RECEPCION,
            registrado_por=self.staff,
        )

        response = self.consultar()

        cita_contexto = response.context['citas'][0]
        self.assertEqual(cita_contexto.pago_bitacora.pk, pendiente.pk)
        self.assertEqual(cita_contexto.importe_pago_bitacora, Decimal('50.00'))
        self.assertContains(response, 'Pendiente de verificación')

    def test_sin_pendiente_muestra_el_pago_no_anulado_mas_reciente(self):
        cita = self.crear_cita()
        registrar_pago(
            cita=cita,
            importe_esperado='450.00',
            importe_reportado='300.00',
            metodo_pago='Efectivo',
            origen_registro=Pago.ORIGEN_RECEPCION,
            registrado_por=self.staff,
        )
        reciente, _ = registrar_pago(
            cita=cita,
            importe_esperado='999.00',
            importe_reportado='400.00',
            metodo_pago='Transferencia',
            origen_registro=Pago.ORIGEN_RECEPCION,
            registrado_por=self.staff,
        )

        response = self.consultar()

        cita_contexto = response.context['citas'][0]
        self.assertEqual(cita_contexto.pago_bitacora.pk, reciente.pk)
        self.assertEqual(cita_contexto.importe_pago_bitacora, Decimal('400.00'))
        self.assertContains(response, 'Confirmado')
        self.assertContains(response, '$400.00')

    def test_consulta_no_crea_ni_modifica_registros_economicos(self):
        cita = self.crear_cita(estatus=Cita.ESTATUS_SI_ASISTIO)
        pago = self.registrar_pago_terapeuta(cita)
        estado_antes = {
            'pago': Pago.objects.get(pk=pago.pk).__dict__.copy(),
            'pagos': Pago.objects.count(),
            'cobros': CobroCita.objects.count(),
            'movimientos': MovimientoEconomicoCita.objects.count(),
        }

        response = self.consultar()

        self.assertEqual(response.status_code, 200)
        pago.refresh_from_db()
        self.assertEqual(Pago.objects.count(), estado_antes['pagos'])
        self.assertEqual(CobroCita.objects.count(), estado_antes['cobros'])
        self.assertEqual(
            MovimientoEconomicoCita.objects.count(),
            estado_antes['movimientos'],
        )
        for campo in (
            'estado',
            'importe_reportado',
            'importe_verificado',
            'verificado_por_id',
            'verificado_en',
        ):
            self.assertEqual(getattr(pago, campo), estado_antes['pago'][campo])


class RegistroPagoRecepcionTests(ClinicaTestDataMixin, TestCase):
    def setUp(self):
        self.client.force_login(self.staff)

    def registrar(self, cita, **datos):
        payload = {
            'metodo_pago': 'Efectivo',
            'importe_recibido': '450.00',
        }
        payload.update(datos)
        return self.client.post(
            reverse('registrar_pago_recepcion', args=[cita.pk]),
            payload,
        )

    def test_cita_atendida_sin_pago_puede_registrarse_desde_recepcion(self):
        cita = self.crear_cita(
            costo=Decimal('500.00'),
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )

        respuesta = self.registrar(cita)

        self.assertRedirects(
            respuesta,
            f"{reverse('bitacora_diaria')}?fecha={cita.fecha.isoformat()}",
        )
        cobro = CobroCita.objects.get(cita=cita)
        pago = Pago.objects.get(cobro=cobro)
        self.assertEqual(cobro.importe_esperado, Decimal('500.00'))
        self.assertEqual(pago.importe_reportado, Decimal('450.00'))
        self.assertEqual(pago.importe_verificado, Decimal('450.00'))
        self.assertEqual(pago.metodo_pago, 'Efectivo')
        self.assertEqual(pago.origen_registro, Pago.ORIGEN_RECEPCION)
        self.assertEqual(pago.estado, Pago.ESTADO_CONFIRMADO)
        self.assertEqual(pago.registrado_por, self.staff)
        self.assertEqual(pago.verificado_por, self.staff)
        self.assertIsNotNone(pago.verificado_en)

    def test_registro_no_modifica_costo_ni_metodo_administrativos(self):
        cita = self.crear_cita(
            costo=Decimal('777.00'),
            metodo_pago='Transferencia',
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )

        self.registrar(
            cita,
            metodo_pago='Debito',
            importe_recibido='450.00',
        )

        cita.refresh_from_db()
        self.assertEqual(cita.costo, Decimal('777.00'))
        self.assertEqual(cita.metodo_pago, 'Transferencia')

    def test_segundo_registro_no_crea_pago_duplicado(self):
        cita = self.crear_cita(estatus=Cita.ESTATUS_SI_ASISTIO)

        self.registrar(cita)
        self.registrar(cita, metodo_pago='Transferencia', importe_recibido='300.00')

        self.assertEqual(CobroCita.objects.filter(cita=cita).count(), 1)
        self.assertEqual(Pago.objects.filter(cobro__cita=cita).count(), 1)

    def test_cita_no_atendida_no_permite_registrar_pago(self):
        cita = self.crear_cita(estatus=Cita.ESTATUS_CONFIRMADA)

        self.registrar(cita)

        self.assertFalse(CobroCita.objects.filter(cita=cita).exists())
        self.assertFalse(Pago.objects.filter(cobro__cita=cita).exists())

    def test_pase_no_se_acepta_como_entrada_de_dinero(self):
        cita = self.crear_cita(estatus=Cita.ESTATUS_SI_ASISTIO)

        self.registrar(cita, metodo_pago='Pase')

        self.assertFalse(CobroCita.objects.filter(cita=cita).exists())
        self.assertFalse(Pago.objects.filter(cobro__cita=cita).exists())

    def test_bitacora_muestra_boton_solo_para_atendida_sin_pago(self):
        atendida = self.crear_cita(estatus=Cita.ESTATUS_SI_ASISTIO)
        no_atendida = self.crear_cita(
            fecha=self.fecha,
            hora='11:00',
            estatus=Cita.ESTATUS_CONFIRMADA,
        )

        respuesta = self.client.get(
            reverse('bitacora_diaria'),
            {'fecha': self.fecha.isoformat()},
        )

        self.assertContains(
            respuesta,
            reverse('registrar_pago_recepcion', args=[atendida.pk]),
        )
        self.assertNotContains(
            respuesta,
            reverse('registrar_pago_recepcion', args=[no_atendida.pk]),
        )

    def test_pago_existente_oculta_registro_nuevo_y_muestra_estado_formal(self):
        cita = self.crear_cita(estatus=Cita.ESTATUS_SI_ASISTIO)
        self.registrar(cita)

        respuesta = self.client.get(
            reverse('bitacora_diaria'),
            {'fecha': self.fecha.isoformat()},
        )

        self.assertNotContains(
            respuesta,
            reverse('registrar_pago_recepcion', args=[cita.pk]),
        )
        self.assertContains(respuesta, 'Confirmado')
        self.assertContains(respuesta, '$450.00')
