"""
clinica/services.py — Motor de Cálculo de Nómina

Contiene la lógica de negocio financiera del sistema INTRA.
Las vistas NO deben calcular nómina directamente; deben llamar a estas funciones.

Funciones principales:
  - calcular_nomina_semanal()  → genera o recalcula un CorteSemanal en borrador
  - aprobar_corte_semanal()    → cambia el estatus a 'aprobado' (no se puede recalcular después)
  - preview_nomina_semanal()   → retorna un dict con el cálculo SIN persistir en BD
"""

from dataclasses import dataclass
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.utils import timezone

from datetime import datetime, time, timedelta

from .models import (
    Cita,
    CorteSemanal,
    LineaNomina,
    MovimientoEconomicoCita,
    ReglaTerapeuta,
)
from .pricing import calcular_importe_servicio_con_captacion


def movimientos_confirmados_cita(cita):
    return MovimientoEconomicoCita.objects.filter(
        cita=cita,
        estado=MovimientoEconomicoCita.ESTADO_CONFIRMADO,
    )


def cita_tiene_movimiento_confirmado(cita):
    return movimientos_confirmados_cita(cita).filter(
        importe__gt=Decimal("0.00"),
    ).exists()


def total_recibido_cita(cita):
    resultado = movimientos_confirmados_cita(cita).aggregate(
        total=Sum("importe"),
    )
    return resultado["total"] or Decimal("0.00")


def total_movimientos_confirmados_en_rango(
    fecha_inicio,
    fecha_fin,
    *,
    terapeuta_id=None,
    paciente_division_ids=None,
):
    zona_horaria = timezone.get_current_timezone()
    instante_inicio = timezone.make_aware(
        datetime.combine(fecha_inicio, time.min),
        zona_horaria,
    )
    instante_fin = timezone.make_aware(
        datetime.combine(fecha_fin + timedelta(days=1), time.min),
        zona_horaria,
    )
    movimientos = MovimientoEconomicoCita.objects.filter(
        estado=MovimientoEconomicoCita.ESTADO_CONFIRMADO,
        registrado_en__gte=instante_inicio,
        registrado_en__lt=instante_fin,
    )
    if terapeuta_id:
        movimientos = movimientos.filter(
            cita__terapeuta_id=terapeuta_id,
        )
    if paciente_division_ids is not None:
        movimientos = movimientos.filter(
            cita__paciente__division_id__in=paciente_division_ids,
        )
    resultado = movimientos.aggregate(total=Sum("importe"))
    return resultado["total"] or Decimal("0.00")


def _guardar_snapshots_servicio(cita):
    if cita.importe_servicio_snapshot is not None:
        return cita

    calculo = calcular_importe_servicio_con_captacion(
        paciente=cita.paciente,
        servicio=cita.servicio,
    )
    if calculo.importe_final is None:
        return cita

    cita.precio_servicio_base_snapshot = calculo.precio_general
    cita.descuento_captacion_porcentaje_snapshot = (
        calculo.porcentaje_descuento
    )
    cita.importe_servicio_snapshot = calculo.importe_final
    cita.save(
        update_fields=[
            "precio_servicio_base_snapshot",
            "descuento_captacion_porcentaje_snapshot",
            "importe_servicio_snapshot",
        ]
    )
    return cita


@transaction.atomic
def registrar_movimiento_economico(
    *,
    cita,
    importe,
    metodo,
    usuario,
    referencia="",
    clave_idempotencia=None,
):
    importe_decimal = Decimal(importe)
    if importe_decimal <= Decimal("0.00"):
        raise ValidationError("El importe debe ser mayor a cero.")

    datos_movimiento = {
        "cita": cita,
        "tipo": MovimientoEconomicoCita.TIPO_COBRO,
        "importe": importe_decimal,
        "metodo": metodo,
        "referencia": (referencia or "").strip(),
        "registrado_por": usuario,
    }
    if clave_idempotencia is not None:
        movimiento_existente = MovimientoEconomicoCita.objects.filter(
            clave_idempotencia=clave_idempotencia,
        ).first()
        if movimiento_existente is not None:
            return movimiento_existente, False
        datos_movimiento["clave_idempotencia"] = clave_idempotencia

    movimiento = MovimientoEconomicoCita(**datos_movimiento)
    movimiento.full_clean()
    movimiento.save()
    return movimiento, True


@transaction.atomic
def registrar_movimiento_recepcion_desde_cita(*, cita, usuario):
    cita_bloqueada = (
        Cita.objects.select_for_update()
        .select_related(
            "paciente",
            "servicio",
        )
        .get(pk=cita.pk)
    )

    if cita_bloqueada.estatus != Cita.ESTATUS_SI_ASISTIO:
        raise ValidationError(
            "El movimiento de Recepción sólo corresponde a una cita asistida."
        )
    if cita_bloqueada.costo is None:
        raise ValidationError("La cita no tiene un importe registrado.")
    if cita_bloqueada.costo <= Decimal("0.00"):
        raise ValidationError("El importe registrado debe ser mayor a cero.")

    metodos_validos = {valor for valor, _ in Cita.PAGO_CHOICES}
    if cita_bloqueada.metodo_pago not in metodos_validos:
        raise ValidationError(
            "Selecciona un método de pago antes de confirmar la asistencia."
        )

    movimiento_existente = (
        movimientos_confirmados_cita(cita_bloqueada)
        .order_by("registrado_en", "id")
        .first()
    )
    if movimiento_existente is not None:
        return movimiento_existente, False

    _guardar_snapshots_servicio(cita_bloqueada)

    movimiento = MovimientoEconomicoCita(
        cita=cita_bloqueada,
        tipo=MovimientoEconomicoCita.TIPO_COBRO,
        importe=cita_bloqueada.costo,
        metodo=cita_bloqueada.metodo_pago,
        referencia="Registrado desde el flujo existente de Recepción",
        registrado_por=usuario,
    )
    movimiento.full_clean()
    movimiento.save()
    return movimiento, True


@transaction.atomic
def anular_movimiento_economico(*, movimiento, usuario, motivo):
    movimiento_bloqueado = MovimientoEconomicoCita.objects.select_for_update().get(
        pk=movimiento.pk,
    )
    if movimiento_bloqueado.estado == MovimientoEconomicoCita.ESTADO_ANULADO:
        return movimiento_bloqueado, False

    motivo_limpio = (motivo or "").strip()
    if not motivo_limpio:
        raise ValidationError("El motivo de anulación es obligatorio.")

    movimiento_bloqueado.estado = MovimientoEconomicoCita.ESTADO_ANULADO
    movimiento_bloqueado.anulado_en = timezone.now()
    movimiento_bloqueado.anulado_por = usuario
    movimiento_bloqueado.motivo_anulacion = motivo_limpio
    movimiento_bloqueado.save(
        update_fields=[
            "estado",
            "anulado_en",
            "anulado_por",
            "motivo_anulacion",
        ]
    )
    return movimiento_bloqueado, True


@dataclass(frozen=True)
class ResultadoIncorporacionComision:
    estado: str
    linea: LineaNomina | None


def _fecha_local_comision(comision):
    return timezone.localtime(comision.generada_en).date()


def actualizar_totales_corte(corte):
    """Actualiza snapshots sin mezclar comisiones de captación con bonos."""
    subtotal_sesiones = (
        corte.lineas.filter(tipo=LineaNomina.TIPO_SESION)
        .aggregate(total=Sum("monto"))["total"]
        or Decimal("0.00")
    )
    total_bonos_automaticos = (
        corte.lineas.filter(
            tipo__in=(
                LineaNomina.TIPO_BONO_UMBRAL,
                LineaNomina.TIPO_BONO_POR_PACIENTE,
                LineaNomina.TIPO_PENALIZACION,
            )
        ).aggregate(total=Sum("monto"))["total"]
        or Decimal("0.00")
    )
    total_expositor = (
        corte.lineas.filter(tipo=LineaNomina.TIPO_EXPOSITOR)
        .aggregate(total=Sum("monto"))["total"]
        or Decimal("0.00")
    )
    total_comisiones = (
        corte.lineas.filter(tipo=LineaNomina.TIPO_COMISION_CAPTACION)
        .aggregate(total=Sum("monto"))["total"]
        or Decimal("0.00")
    )
    bonos_extra = (
        corte.bonos_extra.aggregate(total=Sum("monto"))["total"]
        or Decimal("0.00")
    )
    corte.subtotal_sesiones = subtotal_sesiones
    corte.total_bonos = total_bonos_automaticos + bonos_extra
    corte.total_pago = (
        subtotal_sesiones
        + total_bonos_automaticos
        + bonos_extra
        + total_expositor
        + total_comisiones
    )
    corte.save(
        update_fields=(
            "subtotal_sesiones",
            "total_bonos",
            "total_pago",
        )
    )
    return corte


@transaction.atomic
def incorporar_comision_captacion_a_corte(comision, *, corte_destino=None):
    """Incorpora una comisión de terapeuta una sola vez a un corte borrador."""
    from ventas.classification import captador_es_terapeuta
    from ventas.models import ComisionCaptacion, LineaLiquidacionComision

    comision = (
        ComisionCaptacion.objects.select_for_update()
        .select_related(
            "captacion__captador__usuario__perfil_terapeuta",
        )
        .get(pk=comision.pk)
    )
    captador = comision.captacion.captador
    if not captador_es_terapeuta(captador):
        raise ValueError("La comisión no pertenece a un captador terapeuta.")
    if LineaLiquidacionComision.objects.select_for_update().filter(
        comision=comision,
        activa=True,
    ).exists():
        raise ValueError("La comisión ya tiene un destino activo en liquidaciones.")

    linea_existente = (
        LineaNomina.objects.select_for_update()
        .filter(comision_captacion=comision)
        .first()
    )
    if linea_existente:
        return ResultadoIncorporacionComision("ya_incorporada", linea_existente)
    if comision.estado != ComisionCaptacion.ESTADO_PENDIENTE_PAGO:
        raise ValueError("La comisión está suspendida y no puede incorporarse.")

    terapeuta = captador.usuario.perfil_terapeuta
    fecha_referencia = _fecha_local_comision(comision)
    if corte_destino is None:
        corte = (
            CorteSemanal.objects.select_for_update()
            .filter(
                terapeuta=terapeuta,
                estatus=CorteSemanal.ESTATUS_BORRADOR,
                fecha_fin__gte=fecha_referencia,
            )
            .order_by("fecha_inicio", "id")
            .first()
        )
    else:
        corte = CorteSemanal.objects.select_for_update().get(pk=corte_destino.pk)
        if corte.terapeuta_id != terapeuta.pk or corte.fecha_fin < fecha_referencia:
            raise ValueError("El corte no corresponde al terapeuta o al periodo disponible.")

    if corte is None:
        return ResultadoIncorporacionComision("sin_corte_disponible", None)
    if corte.estatus != CorteSemanal.ESTATUS_BORRADOR:
        raise ValueError("Sólo se pueden incorporar comisiones a cortes en borrador.")

    try:
        with transaction.atomic():
            linea = LineaNomina.objects.create(
                corte=corte,
                cita=None,
                comision_captacion=comision,
                tipo=LineaNomina.TIPO_COMISION_CAPTACION,
                concepto=f"Comisión de captación #{comision.pk}",
                monto=comision.monto_calculado,
            )
    except IntegrityError:
        linea = LineaNomina.objects.get(comision_captacion=comision)
        return ResultadoIncorporacionComision("ya_incorporada", linea)

    actualizar_totales_corte(corte)
    return ResultadoIncorporacionComision("incorporada", linea)


def incorporar_comisiones_captacion_pendientes(corte):
    """Incorpora al corte las comisiones elegibles generadas hasta su cierre."""
    from ventas.queries import comisiones_captacion_terapeutas_pendientes

    comisiones = comisiones_captacion_terapeutas_pendientes().filter(
        captacion__captador__usuario__perfil_terapeuta=corte.terapeuta,
    )
    resultados = []
    for comision in comisiones:
        if _fecha_local_comision(comision) > corte.fecha_fin:
            continue
        resultados.append(
            incorporar_comision_captacion_a_corte(
                comision,
                corte_destino=corte,
            )
        )
    return resultados


# =============================================================================
# HELPERS INTERNOS
# =============================================================================

def _resolver_monto_sesion(cita, regla):
    """
    Determina el monto a pagar al terapeuta por una cita concreta,
    aplicando la jerarquía de reglas de ReglaTerapeuta.

    Orden de prioridad:
      1. pago_pareja   → si la cita tiene pacientes_adicionales (pareja/familiar)
      2. pago_individual
      3. pago_por_sesion
      4. tabulador_base.pago_base  (fallback al tabulador general)
      5. 0.00 con advertencia      (sin tarifa configurada)

    Retorna: (monto: Decimal, concepto: str)
    """
    tiene_adicionales = cita.pacientes_adicionales.exists()

    if tiene_adicionales and regla.pago_pareja is not None:
        return regla.pago_pareja, "Sesión de pareja/familiar"

    if regla.pago_individual is not None:
        return regla.pago_individual, "Sesión individual"

    if regla.pago_por_sesion is not None:
        return regla.pago_por_sesion, "Sesión"

    if regla.tabulador_base and regla.tabulador_base.pago_base is not None:
        cat = regla.tabulador_base.numero
        return regla.tabulador_base.pago_base, f"Sesión (Tabulador Cat. {cat})"

    return Decimal("0.00"), "Sesión (sin tarifa definida — revisar ReglaTerapeuta)"


def _calcular_bonos_automaticos(total_sesiones, regla):
    """
    Calcula los bonos automáticos según la ReglaTerapeuta del terapeuta.
    Retorna una lista de dicts {tipo, concepto, monto} lista para crear LineaNomina.

    Bonos que evalúa:
      - Bono por umbral individual (bono_umbral_monto / bono_umbral_pacientes)
      - Bono por paciente (supervisor: bono_por_paciente × total_sesiones)
      - Bono por umbral del TabuladorGeneral (si no tiene bono individual definido)
    """
    lineas_bono = []

    if total_sesiones == 0:
        return lineas_bono

    # --- Bono por volumen/umbral individual (repetible) ---
    # Ejemplo: $100 por cada 5 pacientes → si atiende 12, cobra 2 × $100
    if regla.bono_umbral_monto and regla.bono_umbral_pacientes:
        veces = total_sesiones // regla.bono_umbral_pacientes
        if veces > 0:
            monto = regla.bono_umbral_monto * veces
            lineas_bono.append({
                "tipo": LineaNomina.TIPO_BONO_UMBRAL,
                "concepto": (
                    f"Bono por volumen: {veces} × ${regla.bono_umbral_monto} "
                    f"({total_sesiones} sesiones, umbral cada {regla.bono_umbral_pacientes})"
                ),
                "monto": monto,
            })

    # --- Bono por paciente (supervisor, acumulativo por cada sesión) ---
    # Ejemplo: José Arcadio +$25 por cada paciente atendido
    if regla.bono_por_paciente:
        monto = regla.bono_por_paciente * total_sesiones
        lineas_bono.append({
            "tipo": LineaNomina.TIPO_BONO_POR_PACIENTE,
            "concepto": (
                f"Bono supervisor: {total_sesiones} × ${regla.bono_por_paciente} por paciente"
            ),
            "monto": monto,
        })

    # --- Fallback: bono del TabuladorGeneral si el terapeuta no tiene bono individual ---
    if not regla.bono_umbral_monto and regla.tabulador_base:
        tab = regla.tabulador_base
        if tab.bono_monto and tab.bono_umbral_pacientes:
            veces = total_sesiones // tab.bono_umbral_pacientes
            if veces > 0:
                monto = tab.bono_monto * veces
                lineas_bono.append({
                    "tipo": LineaNomina.TIPO_BONO_UMBRAL,
                    "concepto": (
                        f"Bono tabulador Cat.{tab.numero}: {veces} × ${tab.bono_monto} "
                        f"({total_sesiones} sesiones, umbral cada {tab.bono_umbral_pacientes})"
                    ),
                    "monto": monto,
                })

    return lineas_bono


# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================

def calcular_nomina_semanal(terapeuta, fecha_inicio, fecha_fin):
    """
    Genera o recalcula el CorteSemanal (en estatus 'borrador') para un terapeuta
    en el rango de fechas dado (viernes a jueves).

    - Si ya existe un CorteSemanal en borrador, lo recalcula borrando las líneas previas.
    - Si el corte existe pero ya fue aprobado o pagado, lanza ValueError (no se toca).
    - Los BonoExtra manuales pre-existentes NO se borran; se suman al total_bonos.

    Retorna: instancia de CorteSemanal actualizada.
    Lanza:
      - ValueError si el corte ya fue aprobado/pagado.
      - ValueError si el terapeuta no tiene ReglaTerapeuta ni TabuladorGeneral asignado.
    """
    # 1. Obtener regla de pago
    try:
        regla = terapeuta.regla_pago
    except ReglaTerapeuta.DoesNotExist:
        raise ValueError(
            f"El terapeuta '{terapeuta}' no tiene una ReglaTerapeuta asignada. "
            "Configúrala en el panel de administración antes de generar la nómina."
        )

    # 2. Obtener citas completadas del periodo
    citas = (
        Cita.objects
        .filter(
            terapeuta=terapeuta,
            fecha__range=(fecha_inicio, fecha_fin),
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )
        .select_related("servicio", "consultorio", "paciente")
        .prefetch_related("pacientes_adicionales")
        .order_by("fecha", "hora")
    )

    total_sesiones = citas.count()
    # Citas con sin_bono=True se pagan pero no cuentan para bonos adicionales
    total_sesiones_para_bono = citas.filter(sin_bono=False).count()

    # 3. Calcular pago base por sesión → genera líneas tipo 'sesion'
    lineas_sesion = []
    subtotal_sesiones = Decimal("0.00")

    for cita in citas:
        monto, concepto = _resolver_monto_sesion(cita, regla)
        subtotal_sesiones += monto
        lineas_sesion.append({
            "tipo": LineaNomina.TIPO_SESION,
            "cita": cita,
            "concepto": f"{concepto} — {cita.paciente} ({cita.fecha})",
            "monto": monto,
        })

    # 4. Calcular bonos automáticos → genera líneas tipo 'bono_umbral' / 'bono_por_paciente'
    lineas_bono = _calcular_bonos_automaticos(total_sesiones_para_bono, regla)
    total_bonos_automaticos = sum(b["monto"] for b in lineas_bono)

    # 5. Persistir en una transacción atómica
    with transaction.atomic():
        corte, _ = CorteSemanal.objects.get_or_create(
            terapeuta=terapeuta,
            fecha_inicio=fecha_inicio,
            defaults={"fecha_fin": fecha_fin, "estatus": CorteSemanal.ESTATUS_BORRADOR},
        )
        corte = CorteSemanal.objects.select_for_update().get(pk=corte.pk)

        if corte.estatus != CorteSemanal.ESTATUS_BORRADOR:
            raise ValueError(
                f"El corte del {fecha_inicio} al {fecha_fin} para '{terapeuta}' "
                f"ya está en estatus '{corte.get_estatus_display()}' y no puede recalcularse. "
                "Solo los borradores pueden recalcularse."
            )

        # Borrar líneas automáticas (sesión y bonos).
        # Las líneas de penalización y expositor se conservan — son pagos ya
        # registrados manualmente y no deben recalcularse.
        PRESERVAR = [
            LineaNomina.TIPO_PENALIZACION,
            LineaNomina.TIPO_EXPOSITOR,
            LineaNomina.TIPO_COMISION_CAPTACION,
        ]
        corte.lineas.exclude(tipo__in=PRESERVAR).delete()

        # Crear líneas de sesión
        LineaNomina.objects.bulk_create([
            LineaNomina(
                corte=corte,
                cita=l["cita"],
                tipo=l["tipo"],
                concepto=l["concepto"],
                monto=l["monto"],
            )
            for l in lineas_sesion
        ])

        # Crear líneas de bono automático
        LineaNomina.objects.bulk_create([
            LineaNomina(
                corte=corte,
                cita=None,
                tipo=b["tipo"],
                concepto=b["concepto"],
                monto=b["monto"],
            )
            for b in lineas_bono
        ])

        incorporar_comisiones_captacion_pendientes(corte)

        # Actualizar snapshots del periodo y del total económico.
        corte.fecha_fin = fecha_fin
        corte.total_sesiones = total_sesiones
        corte.save(update_fields=("fecha_fin", "total_sesiones"))
        actualizar_totales_corte(corte)

    return corte


def preview_nomina_semanal(terapeuta, fecha_inicio, fecha_fin):
    """
    Calcula la nómina semanal SIN persistir nada en la base de datos.
    Útil para mostrar un resumen antes de confirmar el corte.

    Nota: Los BonoExtra manuales NO se incluyen en el preview
    (requieren un CorteSemanal ya existente en BD).

    Retorna: dict con el desglose completo del cálculo.
    """
    try:
        regla = terapeuta.regla_pago
    except ReglaTerapeuta.DoesNotExist:
        return {
            "error": f"'{terapeuta}' no tiene ReglaTerapeuta asignada.",
            "total_sesiones": 0,
            "subtotal_sesiones": Decimal("0.00"),
            "total_bonos": Decimal("0.00"),
            "total_pago": Decimal("0.00"),
            "lineas": [],
        }

    citas = (
        Cita.objects
        .filter(
            terapeuta=terapeuta,
            fecha__range=(fecha_inicio, fecha_fin),
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )
        .select_related("servicio", "consultorio", "paciente")
        .prefetch_related("pacientes_adicionales")
        .order_by("fecha", "hora")
    )

    total_sesiones = citas.count()
    total_sesiones_para_bono = citas.filter(sin_bono=False).count()
    lineas = []
    subtotal_sesiones = Decimal("0.00")

    for cita in citas:
        monto, concepto = _resolver_monto_sesion(cita, regla)
        subtotal_sesiones += monto
        lineas.append({
            "tipo": LineaNomina.TIPO_SESION,
            "cita": cita,
            "concepto": f"{concepto} — {cita.paciente} ({cita.fecha})",
            "monto": monto,
        })

    lineas_bono = _calcular_bonos_automaticos(total_sesiones_para_bono, regla)
    total_bonos = sum(b["monto"] for b in lineas_bono)
    lineas.extend(lineas_bono)

    return {
        "terapeuta": terapeuta,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "regla": regla,
        "total_sesiones": total_sesiones,
        "subtotal_sesiones": subtotal_sesiones,
        "total_bonos": total_bonos,
        "total_pago": subtotal_sesiones + total_bonos,
        "lineas": lineas,
    }


# =============================================================================
# APROBACIÓN DE CORTE
# =============================================================================

@transaction.atomic
def aprobar_corte_semanal(corte, aprobado_por):
    """
    Cambia el estatus del CorteSemanal de 'borrador' a 'aprobado'.
    Una vez aprobado, el corte no puede recalcularse (calcular_nomina_semanal lanzará error).

    Parámetros:
      corte        : instancia de CorteSemanal en estatus 'borrador'
      aprobado_por : instancia de User que realiza la aprobación

    Retorna: CorteSemanal actualizado.
    Lanza: ValueError si el corte no está en borrador.
    """
    from django.utils import timezone

    corte = CorteSemanal.objects.select_for_update().get(pk=corte.pk)
    if corte.estatus != CorteSemanal.ESTATUS_BORRADOR:
        raise ValueError(
            f"Solo se pueden aprobar cortes en borrador. "
            f"Este corte está en estatus '{corte.get_estatus_display()}'."
        )

    comisiones_suspendidas = corte.lineas.filter(
        tipo=LineaNomina.TIPO_COMISION_CAPTACION,
        comision_captacion__estado="suspendida",
    )
    if comisiones_suspendidas.exists():
        raise ValueError(
            "El corte contiene comisiones de captación suspendidas. "
            "Debe revisarlas antes de aprobar."
        )

    corte.estatus = CorteSemanal.ESTATUS_APROBADO
    corte.aprobado_por = aprobado_por
    corte.aprobado_en = timezone.now()
    corte.save()

    return corte


# =============================================================================
# PENALIZACIÓN → PAGO AL TERAPEUTA
# =============================================================================

def registrar_pago_penalizacion_terapeuta(penalizacion):
    """
    Cuando una penalización de inasistencia es cobrada al paciente, el terapeuta
    recibe un bono del 50% de su tabulador como compensación por la inasistencia.

    El pago completo de la sesión atendida (cita_cobro) se registra por el flujo
    normal de Sesiones Atendidas al recalcular la nómina — no se duplica aquí.

    La línea se crea como TIPO_PENALIZACION para que sobreviva el recálculo
    de calcular_nomina_semanal.

    Retorna: LineaNomina creada, o None si no fue posible registrarla.
    """
    cita_origen = penalizacion.cita_origen
    cita_cobro = penalizacion.cita_cobro
    terapeuta = cita_origen.terapeuta

    if not terapeuta or not cita_cobro:
        return None

    try:
        regla = terapeuta.regla_pago
    except ReglaTerapeuta.DoesNotExist:
        return None

    monto_sesion, concepto_sesion = _resolver_monto_sesion(cita_origen, regla)
    monto_penalizacion = (monto_sesion * Decimal("0.50")).quantize(Decimal("0.01"))

    if monto_sesion <= Decimal("0.00"):
        return None

    # Periodo del cobro (viernes–jueves)
    fecha_ref = cita_cobro.fecha
    viernes = fecha_ref - timedelta(days=(fecha_ref.weekday() - 4) % 7)
    domingo = viernes + timedelta(days=6)

    paciente_nombre = cita_origen.paciente.nombre if cita_origen.paciente else "paciente"

    with transaction.atomic():
        corte, _ = CorteSemanal.objects.get_or_create(
            terapeuta=terapeuta,
            fecha_inicio=viernes,
            defaults={"fecha_fin": domingo, "estatus": CorteSemanal.ESTATUS_BORRADOR},
        )

        # Único bono: 50% del tabulador por la inasistencia del paciente
        linea = LineaNomina.objects.create(
            corte=corte,
            cita=cita_origen,
            tipo=LineaNomina.TIPO_PENALIZACION,
            concepto=(
                f"Penalización inasistencia — {paciente_nombre} "
                f"({cita_origen.fecha:%d/%m/%Y}) — 50% de {concepto_sesion.lower()}"
            ),
            monto=monto_penalizacion,
        )

        corte.total_bonos = (corte.total_bonos or Decimal("0.00")) + monto_penalizacion
        corte.total_pago = (corte.total_pago or Decimal("0.00")) + monto_penalizacion
        corte.save(update_fields=["total_bonos", "total_pago"])

    return linea
