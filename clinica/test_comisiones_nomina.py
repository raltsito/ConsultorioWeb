from datetime import date, datetime, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import MovimientoEconomicoCita
from ventas.models import (
    Captacion,
    Captador,
    ComisionCaptacion,
    LineaLiquidacionComision,
    LiquidacionComisiones,
)
from ventas.queries import (
    comision_tiene_destino_pago,
    comisiones_captacion_terapeutas_pendientes,
)

from .models import Cita, CorteSemanal, LineaNomina, Paciente
from .services import (
    aprobar_corte_semanal,
    calcular_nomina_semanal,
    incorporar_comision_captacion_a_corte,
)
from .tests_helpers import ClinicaTestDataMixin


class ComisionesCaptacionNominaTests(ClinicaTestDataMixin, TestCase):
    def setUp(self):
        self.captador = Captador.objects.create(
            tipo=Captador.TIPO_INTERNO,
            usuario=self.usuario_terapeuta,
        )
        self.crear_regla(pago_por_sesion=Decimal("200.00"))

    def crear_comision(
        self,
        *,
        monto="36.25",
        estado=ComisionCaptacion.ESTADO_PENDIENTE_PAGO,
        captador=None,
    ):
        captador = captador or self.captador
        indice = ComisionCaptacion.objects.count() + 1
        paciente = Paciente.objects.create(
            nombre=f"Paciente comisión {indice}",
            fecha_nacimiento=self.paciente.fecha_nacimiento,
            sexo=self.paciente.sexo,
            telefono=f"5558{indice:06d}",
            servicio_inicial=self.servicio,
            division=self.division,
        )
        captacion = Captacion.objects.create(
            paciente=paciente,
            captador=captador,
            codigo=captador.codigo_activo,
            captador_nombre_snapshot=captador.nombre_display,
            captador_tipo_snapshot=captador.clasificacion_display,
        )
        cita = self.crear_cita(
            paciente=paciente,
            fecha=date(2030, 1, 7),
            hora=time(8 + indice, 0),
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )
        return ComisionCaptacion.objects.create(
            captacion=captacion,
            cita_generadora=cita,
            captador_nombre_snapshot=captador.nombre_display,
            paciente_nombre_snapshot=paciente.nombre,
            porcentaje_aplicado=Decimal("7.00"),
            base_calculo=Decimal("400.00"),
            monto_calculado=Decimal(monto),
            estado=estado,
        )

    def fijar_generacion(self, comision, fecha):
        instante = timezone.make_aware(datetime.combine(fecha, time(12, 0)))
        ComisionCaptacion.objects.filter(pk=comision.pk).update(
            generada_en=instante,
        )
        comision.refresh_from_db()

    def crear_corte(self, inicio, fin, *, estatus="borrador"):
        return CorteSemanal.objects.create(
            terapeuta=self.terapeuta,
            fecha_inicio=inicio,
            fecha_fin=fin,
            estatus=estatus,
        )

    def test_identifica_solo_captador_con_perfil_terapeuta(self):
        comision = self.crear_comision()
        corte = self.crear_corte(date(2030, 1, 7), date(2030, 1, 13))

        resultado = incorporar_comision_captacion_a_corte(comision)

        self.assertEqual(resultado.estado, "incorporada")
        self.assertEqual(resultado.linea.corte, corte)

        externo = Captador.objects.create(
            tipo=Captador.TIPO_EXTERNO,
            nombre_externo="Captador externo",
            tipo_organizacion=Captador.ORG_OTRO,
        )
        with self.assertRaisesMessage(ValueError, "captador terapeuta"):
            incorporar_comision_captacion_a_corte(
                self.crear_comision(captador=externo)
            )

        interno = Captador.objects.create(
            tipo=Captador.TIPO_INTERNO,
            usuario=User.objects.create_user("captador_no_clinico"),
        )
        with self.assertRaisesMessage(ValueError, "captador terapeuta"):
            incorporar_comision_captacion_a_corte(
                self.crear_comision(captador=interno)
            )

    def test_monto_es_historico_y_estado_no_cambia(self):
        comision = self.crear_comision(monto="36.25")
        self.crear_corte(date(2030, 1, 7), date(2030, 1, 13))
        linea = incorporar_comision_captacion_a_corte(comision).linea

        self.servicio.precio = Decimal("9999.00")
        self.servicio.save(update_fields=["precio"])
        comision.cita_generadora.costo = Decimal("1.00")
        comision.cita_generadora.save(update_fields=["costo"])
        linea.refresh_from_db()
        comision.refresh_from_db()

        self.assertEqual(linea.monto, Decimal("36.25"))
        self.assertEqual(linea.tipo, LineaNomina.TIPO_COMISION_CAPTACION)
        self.assertEqual(
            comision.estado,
            ComisionCaptacion.ESTADO_PENDIENTE_PAGO,
        )

    def test_suspendida_no_se_incorpora(self):
        comision = self.crear_comision(
            estado=ComisionCaptacion.ESTADO_SUSPENDIDA
        )
        self.crear_corte(date(2030, 1, 7), date(2030, 1, 13))
        with self.assertRaisesMessage(ValueError, "suspendida"):
            incorporar_comision_captacion_a_corte(comision)
        self.assertFalse(LineaNomina.objects.exists())

    def test_asigna_misma_semana_y_si_esta_cerrada_la_siguiente(self):
        comision = self.crear_comision()
        self.fijar_generacion(comision, date(2030, 1, 8))
        corte_cerrado = self.crear_corte(
            date(2030, 1, 7),
            date(2030, 1, 13),
            estatus=CorteSemanal.ESTATUS_APROBADO,
        )
        corte_siguiente = self.crear_corte(
            date(2030, 1, 14),
            date(2030, 1, 20),
        )

        linea = incorporar_comision_captacion_a_corte(comision).linea

        self.assertEqual(linea.corte, corte_siguiente)
        corte_cerrado.refresh_from_db()
        self.assertEqual(corte_cerrado.estatus, CorteSemanal.ESTATUS_APROBADO)
        self.assertFalse(corte_cerrado.lineas.exists())

    def test_sin_corte_borrador_no_inventa_periodo(self):
        comision = self.crear_comision()
        resultado = incorporar_comision_captacion_a_corte(comision)
        self.assertEqual(resultado.estado, "sin_corte_disponible")
        self.assertIsNone(resultado.linea)
        self.assertFalse(CorteSemanal.objects.exists())

    def test_doble_ejecucion_es_idempotente(self):
        comision = self.crear_comision()
        self.crear_corte(date(2030, 1, 7), date(2030, 1, 13))
        primera = incorporar_comision_captacion_a_corte(comision)
        segunda = incorporar_comision_captacion_a_corte(comision)
        self.assertEqual(primera.estado, "incorporada")
        self.assertEqual(segunda.estado, "ya_incorporada")
        self.assertEqual(primera.linea, segunda.linea)
        self.assertEqual(
            LineaNomina.objects.filter(comision_captacion=comision).count(),
            1,
        )

    def test_rechaza_doble_destino_con_liquidacion(self):
        comision = self.crear_comision()
        liquidacion = LiquidacionComisiones.objects.create(
            captador=self.captador,
            beneficiario_nombre_snapshot=self.captador.nombre_display,
        )
        LineaLiquidacionComision.objects.create(
            liquidacion=liquidacion,
            comision=comision,
        )
        self.crear_corte(date(2030, 1, 7), date(2030, 1, 13))

        self.assertTrue(comision_tiene_destino_pago(comision))
        with self.assertRaisesMessage(ValueError, "liquidaciones"):
            incorporar_comision_captacion_a_corte(comision)
        self.assertFalse(
            LineaNomina.objects.filter(comision_captacion=comision).exists()
        )

    def test_calculo_incorpora_pendientes_y_preserva_al_recalcular(self):
        comision = self.crear_comision(monto="36.00")
        corte = calcular_nomina_semanal(
            self.terapeuta,
            date(2030, 1, 7),
            date(2030, 1, 13),
        )
        linea = corte.lineas.get(comision_captacion=comision)
        calcular_nomina_semanal(
            self.terapeuta,
            date(2030, 1, 7),
            date(2030, 1, 13),
        )

        linea.refresh_from_db()
        self.assertEqual(linea.monto, Decimal("36.00"))
        self.assertEqual(
            corte.lineas.filter(comision_captacion=comision).count(),
            1,
        )

    def test_total_separa_sesiones_bonos_y_comisiones(self):
        self.terapeuta.regla_pago.bono_por_paciente = Decimal("300.00")
        self.terapeuta.regla_pago.save(update_fields=["bono_por_paciente"])
        self.crear_comision(monto="36.00")
        segunda = self.crear_comision(monto="42.00")
        segunda.cita_generadora.estatus = Cita.ESTATUS_CANCELO
        segunda.cita_generadora.save(update_fields=["estatus"])

        corte = calcular_nomina_semanal(
            self.terapeuta,
            date(2030, 1, 7),
            date(2030, 1, 13),
        )

        self.assertEqual(corte.subtotal_sesiones, Decimal("200.00"))
        self.assertEqual(corte.total_bonos, Decimal("300.00"))
        self.assertEqual(corte.total_pago, Decimal("578.00"))

    def test_suspendida_bloquea_aprobacion_y_reactivada_permite(self):
        comision = self.crear_comision()
        corte = calcular_nomina_semanal(
            self.terapeuta,
            date(2030, 1, 7),
            date(2030, 1, 13),
        )
        comision.estado = ComisionCaptacion.ESTADO_SUSPENDIDA
        comision.save(update_fields=["estado"])
        with self.assertRaisesMessage(ValueError, "suspendidas"):
            aprobar_corte_semanal(corte, self.staff)
        corte.refresh_from_db()
        self.assertEqual(corte.estatus, CorteSemanal.ESTATUS_BORRADOR)

        comision.estado = ComisionCaptacion.ESTADO_PENDIENTE_PAGO
        comision.save(update_fields=["estado"])
        aprobar_corte_semanal(corte, self.staff)
        corte.refresh_from_db()
        self.assertEqual(corte.estatus, CorteSemanal.ESTATUS_APROBADO)
        self.assertEqual(corte.lineas.filter(comision_captacion=comision).count(), 1)

    def test_suspension_posterior_no_modifica_corte_aprobado(self):
        comision = self.crear_comision(monto="36.25")
        corte = calcular_nomina_semanal(
            self.terapeuta,
            date(2030, 1, 7),
            date(2030, 1, 13),
        )
        aprobar_corte_semanal(corte, self.staff)
        total = corte.total_pago
        linea = corte.lineas.get(comision_captacion=comision)

        comision.estado = ComisionCaptacion.ESTADO_SUSPENDIDA
        comision.save(update_fields=["estado"])

        corte.refresh_from_db()
        linea.refresh_from_db()
        self.assertEqual(corte.estatus, CorteSemanal.ESTATUS_APROBADO)
        self.assertEqual(corte.total_pago, total)
        self.assertEqual(linea.monto, Decimal("36.25"))

    def test_query_pendientes_y_no_crea_liquidacion_ni_pago(self):
        comision = self.crear_comision()
        self.assertEqual(
            list(comisiones_captacion_terapeutas_pendientes()),
            [comision],
        )
        self.crear_corte(date(2030, 1, 7), date(2030, 1, 13))
        incorporar_comision_captacion_a_corte(comision)
        self.assertFalse(
            comisiones_captacion_terapeutas_pendientes().filter(
                pk=comision.pk
            ).exists()
        )
        self.assertFalse(LiquidacionComisiones.objects.exists())
        self.assertFalse(MovimientoEconomicoCita.objects.exists())

    def test_ui_muestra_concepto_estado_y_enlace(self):
        comision = self.crear_comision(monto="36.25")
        calcular_nomina_semanal(
            self.terapeuta,
            date(2030, 1, 7),
            date(2030, 1, 13),
        )
        self.client.force_login(self.staff)
        respuesta = self.client.get(
            reverse("nomina_detalle", args=[self.terapeuta.pk]),
            {
                "fecha_inicio": "2030-01-07",
                "fecha_fin": "2030-01-13",
            },
        )
        self.assertContains(respuesta, "Comisiones de captación")
        self.assertContains(respuesta, f"Comisión de captación #{comision.pk}")
        self.assertContains(respuesta, "$36,25")
