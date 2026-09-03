from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count, Exists, OuterRef, Q, Subquery, Sum

from .models import (
    Captador,
    ComisionCaptacion,
    EventoCaptacion,
    LineaLiquidacionComision,
    LiquidacionComisiones,
)


@dataclass(frozen=True)
class ResumenObligacionesComisiones:
    cantidad_pendiente: int
    monto_pendiente: Decimal
    cantidad_suspendida: int
    monto_suspendido: Decimal
    cantidad_total: int
    monto_total: Decimal


@dataclass(frozen=True)
class DetalleObligacionComision:
    comision: ComisionCaptacion
    tiene_pago_vigente: bool
    total_recibido: Decimal
    adeudo: Decimal
    saldo_favor: Decimal
    eventos: tuple


@dataclass(frozen=True)
class ResumenLiquidaciones:
    cantidad_borradores: int
    total_provisional_borradores: Decimal
    cantidad_pagadas: int
    monto_historico_pagado: Decimal
    cantidad_canceladas: int
    cantidad_con_incidencia: int


def queryset_comisiones_panel():
    lineas_activas = LineaLiquidacionComision.objects.filter(
        comision_id=OuterRef("pk"),
        activa=True,
    )
    return ComisionCaptacion.objects.select_related(
        "captacion",
        "captacion__captador",
        "captacion__captador__usuario",
        "captacion__captador__empresa",
        "captacion__decidido_por",
        "cita_generadora",
        "cita_generadora__paciente",
        "cita_generadora__servicio",
    ).annotate(
        esta_en_borrador=Exists(
            lineas_activas.filter(
                liquidacion__estado=LiquidacionComisiones.ESTADO_BORRADOR,
            )
        ),
        esta_pagada=Exists(
            lineas_activas.filter(
                liquidacion__estado=LiquidacionComisiones.ESTADO_PAGADA,
            )
        ),
        liquidacion_activa_id=Subquery(
            lineas_activas.order_by("id").values("liquidacion_id")[:1]
        ),
    ).order_by("-generada_en", "-id")


def estado_derivado_comision(comision):
    esta_pagada = getattr(comision, "esta_pagada", False)
    esta_en_borrador = getattr(comision, "esta_en_borrador", False)
    if esta_pagada and comision.estado == ComisionCaptacion.ESTADO_SUSPENDIDA:
        return "pagada_suspendida"
    if esta_pagada:
        return "pagada"
    if comision.estado == ComisionCaptacion.ESTADO_SUSPENDIDA:
        return "suspendida"
    if esta_en_borrador:
        return "reservada"
    return "disponible"


def obtener_resumen_comisiones():
    agregado = queryset_comisiones_panel().aggregate(
        cantidad_pendiente=Count(
            "id",
            filter=Q(
                estado=ComisionCaptacion.ESTADO_PENDIENTE_PAGO,
                esta_pagada=False,
            ),
        ),
        monto_pendiente=Sum(
            "monto_calculado",
            filter=Q(
                estado=ComisionCaptacion.ESTADO_PENDIENTE_PAGO,
                esta_pagada=False,
            ),
        ),
        cantidad_suspendida=Count(
            "id",
            filter=Q(
                estado=ComisionCaptacion.ESTADO_SUSPENDIDA,
                esta_pagada=False,
            ),
        ),
        monto_suspendido=Sum(
            "monto_calculado",
            filter=Q(
                estado=ComisionCaptacion.ESTADO_SUSPENDIDA,
                esta_pagada=False,
            ),
        ),
        cantidad_total=Count("id"),
        monto_total=Sum("monto_calculado"),
    )
    cero = Decimal("0.00")
    return ResumenObligacionesComisiones(
        cantidad_pendiente=agregado["cantidad_pendiente"],
        monto_pendiente=agregado["monto_pendiente"] or cero,
        cantidad_suspendida=agregado["cantidad_suspendida"],
        monto_suspendido=agregado["monto_suspendido"] or cero,
        cantidad_total=agregado["cantidad_total"],
        monto_total=agregado["monto_total"] or cero,
    )


def listar_comisiones(
    *,
    estado="",
    fecha_desde="",
    fecha_hasta="",
    captador_id="",
    paciente="",
    tipo_captador="",
    servicio_id="",
    busqueda="",
):
    comisiones = queryset_comisiones_panel()
    estados_validos = {
        ComisionCaptacion.ESTADO_PENDIENTE_PAGO,
        ComisionCaptacion.ESTADO_SUSPENDIDA,
        ComisionCaptacion.ESTADO_PAGADA,
    }
    tipos_validos = {valor for valor, _ in Captador.TIPO_CHOICES}

    if estado in estados_validos:
        if estado == ComisionCaptacion.ESTADO_PAGADA:
            comisiones = comisiones.filter(esta_pagada=True)
        else:
            comisiones = comisiones.filter(
                estado=estado,
                esta_pagada=False,
            )
    if fecha_desde:
        comisiones = comisiones.filter(generada_en__date__gte=fecha_desde)
    if fecha_hasta:
        comisiones = comisiones.filter(generada_en__date__lte=fecha_hasta)
    if str(captador_id).isdigit():
        comisiones = comisiones.filter(captacion__captador_id=captador_id)
    if paciente:
        comisiones = comisiones.filter(
            paciente_nombre_snapshot__icontains=paciente
        )
    if tipo_captador in tipos_validos:
        comisiones = comisiones.filter(
            captacion__captador__tipo=tipo_captador
        )
    if str(servicio_id).isdigit():
        comisiones = comisiones.filter(
            cita_generadora__servicio_id=servicio_id
        )
    if busqueda:
        comisiones = comisiones.filter(
            Q(captador_nombre_snapshot__icontains=busqueda)
            | Q(paciente_nombre_snapshot__icontains=busqueda)
        )
    return comisiones


def obtener_detalle_comision(comision_id):
    comision = queryset_comisiones_panel().get(pk=comision_id)
    cita = comision.cita_generadora
    cobro = getattr(cita, "cobro", None)
    total_recibido = (
        cobro.total_confirmado
        if cobro is not None
        else Decimal("0.00")
    )
    tiene_pago_vigente = total_recibido > Decimal("0.00")
    adeudo = Decimal("0.00")
    saldo_favor = Decimal("0.00")

    eventos = tuple(
        EventoCaptacion.objects.filter(
            captacion=comision.captacion,
            accion__in=(
                EventoCaptacion.ACCION_COMISION_GENERADA,
                EventoCaptacion.ACCION_COMISION_SUSPENDIDA,
                EventoCaptacion.ACCION_COMISION_REACTIVADA,
            ),
        )
        .select_related("usuario")
        .order_by("-creado_en", "-id")
    )
    return DetalleObligacionComision(
        comision=comision,
        tiene_pago_vigente=tiene_pago_vigente,
        total_recibido=total_recibido,
        adeudo=adeudo,
        saldo_favor=saldo_favor,
        eventos=eventos,
    )


def comisiones_disponibles_para_liquidacion(*, captador=None):
    comisiones = queryset_comisiones_panel().filter(
        estado=ComisionCaptacion.ESTADO_PENDIENTE_PAGO,
        captacion__captador__activo=True,
    ).exclude(
        lineas_liquidacion__activa=True,
    ).filter(
        Q(captacion__captador__tipo__in=(
            Captador.TIPO_EXTERNO,
            Captador.TIPO_EMPRESA,
        ))
        | Q(
            captacion__captador__tipo=Captador.TIPO_INTERNO,
            captacion__captador__usuario__perfil_terapeuta__isnull=True,
        )
    )
    if captador is not None:
        comisiones = comisiones.filter(captacion__captador=captador)
    return comisiones.distinct()


def obtener_liquidacion_detalle(liquidacion_id):
    return (
        LiquidacionComisiones.objects.select_related(
            "captador__usuario",
            "captador__usuario__perfil_terapeuta",
            "captador__empresa",
            "creada_por",
            "cancelada_por",
        )
        .prefetch_related(
            "lineas__agregada_por",
            "lineas__retirada_por",
            "lineas__comision__captacion",
            "lineas__comision__cita_generadora__servicio",
            "eventos__usuario",
        )
        .get(pk=liquidacion_id)
    )


def _lineas_suspendidas_activas():
    return LineaLiquidacionComision.objects.filter(
        liquidacion_id=OuterRef("pk"),
        activa=True,
        comision__estado=ComisionCaptacion.ESTADO_SUSPENDIDA,
    )


def queryset_liquidaciones_panel():
    return (
        LiquidacionComisiones.objects.select_related(
            "captador__usuario",
            "captador__empresa",
            "creada_por",
            "pagada_por",
            "cancelada_por",
        )
        .annotate(
            cantidad_comisiones=Count(
                "lineas",
                filter=Q(lineas__activa=True),
                distinct=True,
            ),
            total_provisional=Sum(
                "lineas__comision__monto_calculado",
                filter=Q(lineas__activa=True),
            ),
            tiene_incidencia_activa=Exists(_lineas_suspendidas_activas()),
        )
        .order_by("-creada_en", "-id")
    )


def liquidacion_tiene_incidencia_activa(liquidacion):
    if liquidacion.estado != LiquidacionComisiones.ESTADO_PAGADA:
        return False
    return liquidacion.lineas.filter(
        activa=True,
        comision__estado=ComisionCaptacion.ESTADO_SUSPENDIDA,
    ).exists()


def liquidaciones_con_incidencia_activa():
    return queryset_liquidaciones_panel().filter(
        estado=LiquidacionComisiones.ESTADO_PAGADA,
        tiene_incidencia_activa=True,
    )


def lineas_con_incidencia(liquidacion):
    return (
        liquidacion.lineas.filter(
            activa=True,
            comision__estado=ComisionCaptacion.ESTADO_SUSPENDIDA,
        )
        .select_related(
            "comision__captacion",
            "comision__cita_generadora__servicio",
        )
        .order_by("comision_id", "id")
    )


def eventos_incidencia_liquidacion(liquidacion):
    captacion_ids = liquidacion.lineas.filter(activa=True).values_list(
        "comision__captacion_id",
        flat=True,
    )
    return (
        EventoCaptacion.objects.filter(
            captacion_id__in=captacion_ids,
            accion__in=(
                EventoCaptacion.ACCION_COMISION_SUSPENDIDA,
                EventoCaptacion.ACCION_COMISION_REACTIVADA,
            ),
        )
        .select_related("usuario", "captacion")
        .order_by("-creado_en", "-id")
    )


def obtener_resumen_liquidaciones():
    cero = Decimal("0.00")
    borradores = LiquidacionComisiones.objects.filter(
        estado=LiquidacionComisiones.ESTADO_BORRADOR
    )
    pagadas = LiquidacionComisiones.objects.filter(
        estado=LiquidacionComisiones.ESTADO_PAGADA
    )
    agregado_borradores = borradores.aggregate(
        cantidad=Count("id", distinct=True),
        total=Sum(
            "lineas__comision__monto_calculado",
            filter=Q(lineas__activa=True),
        ),
    )
    agregado_pagadas = pagadas.aggregate(
        cantidad=Count("id"),
        total=Sum("monto_total_snapshot"),
    )
    return ResumenLiquidaciones(
        cantidad_borradores=agregado_borradores["cantidad"],
        total_provisional_borradores=agregado_borradores["total"] or cero,
        cantidad_pagadas=agregado_pagadas["cantidad"],
        monto_historico_pagado=agregado_pagadas["total"] or cero,
        cantidad_canceladas=LiquidacionComisiones.objects.filter(
            estado=LiquidacionComisiones.ESTADO_CANCELADA
        ).count(),
        cantidad_con_incidencia=liquidaciones_con_incidencia_activa().count(),
    )


def listar_liquidaciones(
    *,
    estado="",
    captador_id="",
    tipo_captador="",
    creada_desde="",
    creada_hasta="",
    pagada_desde="",
    pagada_hasta="",
    metodo_pago="",
    incidencia="",
    busqueda="",
):
    liquidaciones = queryset_liquidaciones_panel()
    estados_validos = {valor for valor, _ in LiquidacionComisiones.ESTADO_CHOICES}
    tipos_validos = {valor for valor, _ in Captador.TIPO_CHOICES}
    metodos_validos = {
        valor for valor, _ in LiquidacionComisiones.METODO_PAGO_CHOICES
    }
    if estado in estados_validos:
        liquidaciones = liquidaciones.filter(estado=estado)
    if str(captador_id).isdigit():
        liquidaciones = liquidaciones.filter(captador_id=captador_id)
    if tipo_captador in tipos_validos:
        liquidaciones = liquidaciones.filter(captador__tipo=tipo_captador)
    if creada_desde:
        liquidaciones = liquidaciones.filter(creada_en__date__gte=creada_desde)
    if creada_hasta:
        liquidaciones = liquidaciones.filter(creada_en__date__lte=creada_hasta)
    if pagada_desde:
        liquidaciones = liquidaciones.filter(pagada_en__date__gte=pagada_desde)
    if pagada_hasta:
        liquidaciones = liquidaciones.filter(pagada_en__date__lte=pagada_hasta)
    if metodo_pago in metodos_validos:
        liquidaciones = liquidaciones.filter(metodo_pago=metodo_pago)
    if incidencia == "si":
        liquidaciones = liquidaciones.filter(
            estado=LiquidacionComisiones.ESTADO_PAGADA,
            tiene_incidencia_activa=True,
        )
    elif incidencia == "no":
        liquidaciones = liquidaciones.exclude(
            estado=LiquidacionComisiones.ESTADO_PAGADA,
            tiene_incidencia_activa=True,
        )
    if busqueda:
        criterio = (
            Q(beneficiario_nombre_snapshot__icontains=busqueda)
            | Q(referencia__icontains=busqueda)
            | Q(captador__nombre_externo__icontains=busqueda)
            | Q(captador__usuario__username__icontains=busqueda)
            | Q(captador__empresa__nombre__icontains=busqueda)
        )
        if busqueda.isdigit():
            criterio |= Q(pk=int(busqueda))
        liquidaciones = liquidaciones.filter(criterio)
    return liquidaciones


def comision_tiene_destino_pago(comision):
    """Devuelve si la comisión ya está reservada en alguna vía de pago."""
    from clinica.models import LineaNomina

    en_liquidacion = LineaLiquidacionComision.objects.filter(
        comision=comision,
        activa=True,
    ).exists()
    en_nomina = LineaNomina.objects.filter(
        comision_captacion=comision,
    ).exists()
    return en_liquidacion or en_nomina


def comisiones_captacion_terapeutas_pendientes(*, generada_hasta=None):
    """Comisiones elegibles, sin destino, de captadores con perfil clínico."""
    from clinica.models import LineaNomina

    lineas_nomina = LineaNomina.objects.filter(
        comision_captacion_id=OuterRef("pk"),
    )
    liquidaciones_activas = LineaLiquidacionComision.objects.filter(
        comision_id=OuterRef("pk"),
        activa=True,
    )
    comisiones = (
        ComisionCaptacion.objects.filter(
            estado=ComisionCaptacion.ESTADO_PENDIENTE_PAGO,
            captacion__captador__tipo=Captador.TIPO_INTERNO,
            captacion__captador__usuario__perfil_terapeuta__isnull=False,
        )
        .annotate(
            ya_en_nomina=Exists(lineas_nomina),
            ya_en_liquidacion=Exists(liquidaciones_activas),
        )
        .filter(
            ya_en_nomina=False,
            ya_en_liquidacion=False,
        )
        .select_related(
            "captacion__captador__usuario__perfil_terapeuta",
            "cita_generadora",
        )
        .order_by("generada_en", "id")
    )
    if generada_hasta is not None:
        comisiones = comisiones.filter(generada_en__date__lte=generada_hasta)
    return comisiones
