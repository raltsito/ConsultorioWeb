"""
clinica/services.py — Motor de Cálculo de Nómina

Contiene la lógica de negocio financiera del sistema INTRA.
Las vistas NO deben calcular nómina directamente; deben llamar a estas funciones.

Funciones principales:
  - calcular_nomina_semanal()  → genera o recalcula un CorteSemanal en borrador
  - aprobar_corte_semanal()    → cambia el estatus a 'aprobado' (no se puede recalcular después)
  - preview_nomina_semanal()   → retorna un dict con el cálculo SIN persistir en BD
"""

from decimal import Decimal
from django.db import transaction
from django.db.models import Sum

from datetime import timedelta

from .models import (
    Cita,
    CorteSemanal,
    LineaNomina,
    ReglaTerapeuta,
)


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
    en el rango de fechas dado (lunes a domingo).

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
    lineas_bono = _calcular_bonos_automaticos(total_sesiones, regla)
    total_bonos_automaticos = sum(b["monto"] for b in lineas_bono)

    # 5. Persistir en una transacción atómica
    with transaction.atomic():
        corte, _ = CorteSemanal.objects.get_or_create(
            terapeuta=terapeuta,
            fecha_inicio=fecha_inicio,
            defaults={"fecha_fin": fecha_fin, "estatus": CorteSemanal.ESTATUS_BORRADOR},
        )

        if corte.estatus != CorteSemanal.ESTATUS_BORRADOR:
            raise ValueError(
                f"El corte del {fecha_inicio} al {fecha_fin} para '{terapeuta}' "
                f"ya está en estatus '{corte.get_estatus_display()}' y no puede recalcularse. "
                "Solo los borradores pueden recalcularse."
            )

        # Borrar líneas automáticas (sesión y bonos).
        # Las líneas de penalización se conservan — son pagos ya registrados,
        # no se recalculan y deben seguir sumándose al total_pago del corte.
        corte.lineas.exclude(tipo=LineaNomina.TIPO_PENALIZACION).delete()

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

        # Sumar BonoExtra manuales existentes en este corte
        bonos_extra = corte.bonos_extra.aggregate(total=Sum("monto"))["total"] or Decimal("0.00")

        # Sumar líneas de penalización ya registradas (sobreviven al recalculo)
        total_penalizaciones = (
            corte.lineas.filter(tipo=LineaNomina.TIPO_PENALIZACION)
            .aggregate(total=Sum("monto"))["total"] or Decimal("0.00")
        )

        # Actualizar snapshot del corte
        corte.fecha_fin = fecha_fin
        corte.total_sesiones = total_sesiones
        corte.subtotal_sesiones = subtotal_sesiones
        corte.total_bonos = total_bonos_automaticos + bonos_extra + total_penalizaciones
        corte.total_pago = subtotal_sesiones + total_bonos_automaticos + bonos_extra + total_penalizaciones
        corte.save()

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

    lineas_bono = _calcular_bonos_automaticos(total_sesiones, regla)
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

    if corte.estatus != CorteSemanal.ESTATUS_BORRADOR:
        raise ValueError(
            f"Solo se pueden aprobar cortes en borrador. "
            f"Este corte está en estatus '{corte.get_estatus_display()}'."
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
    recibe el 50% de lo que habría ganado en esa sesión.

    - Calcula el monto usando la ReglaTerapeuta del terapeuta de la cita original.
    - Agrega una LineaNomina de tipo 'penalizacion' al CorteSemanal de la semana
      en que se cobró la penalización (fecha de la cita_cobro).
    - Si no existe CorteSemanal para esa semana, lo crea en borrador.
    - Si el corte de esa semana ya está aprobado/pagado, busca el corte de la
      semana actual como alternativa.
    - Si el terapeuta no tiene ReglaTerapeuta configurada, no hace nada (silencioso).

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
        return None  # Sin regla de pago configurada — no se puede calcular

    # Monto: 50% del pago que habría ganado el terapeuta por esa sesión
    monto_sesion, concepto_sesion = _resolver_monto_sesion(cita_origen, regla)
    monto = (monto_sesion * Decimal("0.50")).quantize(Decimal("0.01"))

    if monto <= Decimal("0.00"):
        return None

    # Semana del cobro (lunes–domingo)
    fecha_ref = cita_cobro.fecha
    lunes = fecha_ref - timedelta(days=fecha_ref.weekday())
    domingo = lunes + timedelta(days=6)

    with transaction.atomic():
        # Obtenemos o creamos el corte de la semana del cobro.
        # La línea de penalización se registra en ese corte sin importar
        # su estatus (borrador o aprobado): no modifica líneas automáticas.
        corte, _ = CorteSemanal.objects.get_or_create(
            terapeuta=terapeuta,
            fecha_inicio=lunes,
            defaults={"fecha_fin": domingo, "estatus": CorteSemanal.ESTATUS_BORRADOR},
        )

        paciente_nombre = cita_origen.paciente.nombre if cita_origen.paciente else "paciente"
        linea = LineaNomina.objects.create(
            corte=corte,
            cita=cita_origen,
            tipo=LineaNomina.TIPO_PENALIZACION,
            concepto=(
                f"Penalización inasistencia — {paciente_nombre} "
                f"({cita_origen.fecha:%d/%m/%Y}) — 50% de {concepto_sesion.lower()}"
            ),
            monto=monto,
        )

        # Actualizar totales del corte sumando esta línea
        corte.total_bonos = (corte.total_bonos or Decimal("0.00")) + monto
        corte.total_pago = (corte.total_pago or Decimal("0.00")) + monto
        corte.save(update_fields=["total_bonos", "total_pago"])

    return linea
