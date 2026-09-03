import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import unquote, urlparse

from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from clinica.models import Cita, CobroCita
from clinica.services import cita_tiene_movimiento_confirmado

from .classification import captador_es_elegible_para_liquidacion
from .models import (
    Captacion,
    Captador,
    CodigoCaptacion,
    EventoCaptacion,
    EventoCaptador,
    ComisionCaptacion,
    EventoLiquidacion,
    LineaLiquidacionComision,
    LiquidacionComisiones,
)


class CaptacionYaRevisadaError(ValueError):
    pass


class PorcentajeComisionInvalidoError(ValueError):
    pass


class MotivoRechazoObligatorioError(ValueError):
    pass


class DatosCalculoComisionInvalidosError(ValueError):
    pass


class OperacionLiquidacionError(ValueError):
    def __init__(self, codigo, mensaje):
        self.codigo = codigo
        super().__init__(mensaje)


@dataclass(frozen=True)
class ElegibilidadCaptacion:
    elegible: bool
    codigo: str = ""
    mensaje: str = ""


@dataclass(frozen=True)
class ResultadoGeneracionComision:
    estado: str
    captacion_id: int
    comision: ComisionCaptacion | None = None
    cita: Cita | None = None
    detalle: str = ""

    @property
    def generada(self):
        return self.estado == "generada"


@dataclass
class ResumenReconciliacionComisiones:
    conteos: dict = field(default_factory=dict)

    def agregar(self, resultado):
        self.conteos[resultado.estado] = self.conteos.get(resultado.estado, 0) + 1

    @property
    def evaluadas(self):
        return sum(self.conteos.values())


@dataclass(frozen=True)
class ResultadoReconciliacionEstadoComision:
    estado: str
    comision_id: int
    detalle: str = ""


@dataclass
class ResumenReconciliacionEstadosComision:
    conteos: dict = field(default_factory=dict)

    def agregar(self, resultado):
        self.conteos[resultado.estado] = self.conteos.get(resultado.estado, 0) + 1

    @property
    def evaluadas(self):
        return sum(self.conteos.values())


def citas_asistidas_del_paciente(paciente):
    """Fuente compartida para asistencias como principal o adicional."""
    return Cita.objects.filter(
        Q(paciente=paciente) | Q(pacientes_adicionales=paciente),
        estatus=Cita.ESTATUS_SI_ASISTIO,
    ).distinct()


def calcular_monto_comision(*, base_calculo, porcentaje):
    if not isinstance(base_calculo, Decimal):
        raise DatosCalculoComisionInvalidosError(
            "La base de cálculo debe proporcionarse como Decimal."
        )
    if base_calculo < Decimal("0"):
        raise DatosCalculoComisionInvalidosError(
            "La base de cálculo no puede ser negativa."
        )
    if isinstance(porcentaje, bool) or not isinstance(porcentaje, int):
        raise DatosCalculoComisionInvalidosError(
            "El porcentaje debe ser un número entero entre 1 y 10."
        )
    if porcentaje < 1 or porcentaje > 10:
        raise DatosCalculoComisionInvalidosError(
            "El porcentaje debe estar entre 1 y 10."
        )

    proporcion = Decimal(porcentaje) / Decimal("100")
    return (base_calculo * proporcion).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def evaluar_elegibilidad_captacion(paciente):
    if Captacion.objects.filter(paciente=paciente).exists():
        return ElegibilidadCaptacion(
            False,
            "ya_captado",
            "Este paciente ya cuenta con una captación registrada.",
        )
    tuvo_atencion = citas_asistidas_del_paciente(paciente).exists()
    if tuvo_atencion:
        return ElegibilidadCaptacion(
            False,
            "atencion_previa",
            "El paciente no es elegible para Captación porque ya cuenta con atención previa.",
        )
    return ElegibilidadCaptacion(True, "elegible", "Paciente nuevo elegible.")


# ============================================================================
# ===== INICIO RECUPERACIÓN CAPTACIÓN / QR: normalización ====================
# ============================================================================


def normalizar_token_captacion(valor):
    """Extrae el token de una lectura directa o de la URL del QR oficial."""
    valor = (valor or "").strip()
    if not valor:
        return ""

    parsed = urlparse(valor)
    if parsed.scheme or parsed.netloc:
        segmentos = [segmento for segmento in parsed.path.split("/") if segmento]
        return unquote(segmentos[-1]).strip() if segmentos else ""

    return unquote(parsed.path).strip().strip("/")


# ============================================================================
# ===== FIN RECUPERACIÓN CAPTACIÓN / QR: normalización =======================
# ============================================================================


def buscar_codigo_captacion(token):
    """Devuelve código y estado estable para la web y futuras interfaces."""
    token = normalizar_token_captacion(token)
    codigos = CodigoCaptacion.objects.select_related(
        "captador__usuario",
        "captador__empresa",
    )
    coincidencia_publica = re.fullmatch(r"INTRA([0-9]{4,})", token, re.IGNORECASE)
    if coincidencia_publica:
        codigo_id = int(coincidencia_publica.group(1))
        if codigo_id > 0 and token.upper() == f"INTRA{codigo_id:04d}":
            codigo = codigos.filter(pk=codigo_id).first()
        else:
            codigo = None
    else:
        codigo = codigos.filter(token=token).first()
    if not codigo:
        return None, "inexistente"
    if not codigo.activo:
        return codigo, "codigo_inactivo"
    if not codigo.captador.activo:
        return codigo, "inactivo"
    if (
        codigo.porcentaje_comision is None
        or not 0 <= codigo.porcentaje_comision <= 10
    ):
        return codigo, "sin_configurar"
    return codigo, "valido"


@transaction.atomic
def registrar_captacion(*, paciente, codigo, usuario, canal=""):
    paciente.__class__.objects.select_for_update().get(pk=paciente.pk)
    elegibilidad = evaluar_elegibilidad_captacion(paciente)
    if not elegibilidad.elegible:
        raise ValueError(elegibilidad.mensaje)

    codigo_bloqueado = CodigoCaptacion.objects.select_for_update().get(pk=codigo.pk)
    codigo = (
        CodigoCaptacion.objects
        .select_related(
            "captador__usuario",
            "captador__empresa",
        )
        .get(pk=codigo_bloqueado.pk)
    )
    if not codigo.activo or not codigo.captador.activo:
        raise ValueError(
            "Este captador está inactivo y no puede generar nuevas captaciones."
        )
    if (
        codigo.porcentaje_comision is None
        or not 0 <= codigo.porcentaje_comision <= 10
    ):
        raise ValueError(
            "Este código de captación aún no tiene una comisión configurada."
        )

    try:
        captacion = Captacion.objects.create(
            paciente=paciente,
            captador=codigo.captador,
            codigo=codigo,
            registrado_por=usuario,
            estado=Captacion.ESTADO_APROBADA,
            canal=canal.strip(),
            captador_nombre_snapshot=codigo.captador.nombre_display,
            captador_tipo_snapshot=codigo.captador.clasificacion_display,
            porcentaje_comision=codigo.porcentaje_comision,
            decidido_por=codigo.porcentaje_configurado_por,
            decidido_en=codigo.porcentaje_configurado_en,
        )
    except IntegrityError as exc:
        raise ValueError("Este paciente ya cuenta con una captación registrada.") from exc

    EventoCaptacion.objects.create(
        captacion=captacion,
        accion=EventoCaptacion.ACCION_APROBADA,
        usuario=codigo.porcentaje_configurado_por,
        estado_anterior=Captacion.ESTADO_PENDIENTE,
        estado_nuevo=Captacion.ESTADO_APROBADA,
        porcentaje_comision=captacion.porcentaje_comision,
        motivo="Aprobación automática por configuración previa del QR.",
    )
    return captacion


def _obtener_captacion_pendiente(captacion):
    captacion_bloqueada = Captacion.objects.select_for_update().get(
        pk=captacion.pk
    )
    if captacion_bloqueada.estado != Captacion.ESTADO_PENDIENTE:
        raise CaptacionYaRevisadaError("La captación ya fue revisada.")
    return captacion_bloqueada


@transaction.atomic
def aprobar_captacion(*, captacion, porcentaje, usuario):
    if isinstance(porcentaje, bool) or not isinstance(porcentaje, int):
        raise PorcentajeComisionInvalidoError(
            "El porcentaje debe ser un número entero entre 0 y 10."
        )
    if porcentaje < 0 or porcentaje > 10:
        raise PorcentajeComisionInvalidoError(
            "El porcentaje debe estar entre 0 y 10."
        )

    captacion = _obtener_captacion_pendiente(captacion)
    estado_anterior = captacion.estado
    captacion.estado = Captacion.ESTADO_APROBADA
    captacion.porcentaje_comision = porcentaje
    captacion.decidido_por = usuario
    captacion.decidido_en = timezone.now()
    captacion.motivo_rechazo = ""
    captacion.save(
        update_fields=[
            "estado",
            "porcentaje_comision",
            "decidido_por",
            "decidido_en",
            "motivo_rechazo",
            "actualizado_en",
        ]
    )
    EventoCaptacion.objects.create(
        captacion=captacion,
        accion=EventoCaptacion.ACCION_APROBADA,
        usuario=usuario,
        estado_anterior=estado_anterior,
        estado_nuevo=captacion.estado,
        porcentaje_comision=porcentaje,
    )
    return captacion


@transaction.atomic
def rechazar_captacion(*, captacion, motivo, usuario):
    motivo = (motivo or "").strip()
    if not motivo:
        raise MotivoRechazoObligatorioError(
            "El motivo del rechazo es obligatorio."
        )

    captacion = _obtener_captacion_pendiente(captacion)
    estado_anterior = captacion.estado
    captacion.estado = Captacion.ESTADO_RECHAZADA
    captacion.porcentaje_comision = None
    captacion.decidido_por = usuario
    captacion.decidido_en = timezone.now()
    captacion.motivo_rechazo = motivo
    captacion.save(
        update_fields=[
            "estado",
            "porcentaje_comision",
            "decidido_por",
            "decidido_en",
            "motivo_rechazo",
            "actualizado_en",
        ]
    )
    EventoCaptacion.objects.create(
        captacion=captacion,
        accion=EventoCaptacion.ACCION_RECHAZADA,
        usuario=usuario,
        estado_anterior=estado_anterior,
        estado_nuevo=captacion.estado,
        motivo=motivo,
    )
    return captacion


@transaction.atomic
def cambiar_estado_captador(captador, *, activar, usuario, motivo=""):
    captador = Captador.objects.select_for_update().get(pk=captador.pk)
    if captador.activo == activar:
        return captador

    captador.activo = activar
    if activar:
        captador.desactivado_en = None
        captador.desactivado_por = None
        captador.motivo_desactivacion = ""
        accion = EventoCaptador.ACCION_REACTIVADO
    else:
        captador.desactivado_en = timezone.now()
        captador.desactivado_por = usuario
        captador.motivo_desactivacion = motivo.strip()
        accion = EventoCaptador.ACCION_DESACTIVADO
    captador.save(update_fields=[
        "activo", "desactivado_en", "desactivado_por", "motivo_desactivacion"
    ])
    EventoCaptador.objects.create(
        captador=captador,
        accion=accion,
        usuario=usuario,
        detalle="Cambio de estado administrativo.",
    )
    return captador


def _primera_cita_asistida(paciente):
    """Obtiene la primera asistencia donde el paciente contrató el servicio.

    La elegibilidad histórica para registrar una captación también considera
    participaciones como paciente adicional. Para generar una comisión, en
    cambio, sólo cuentan las citas donde ``paciente`` es el principal.
    """
    return (
        Cita.objects.filter(
            paciente=paciente,
            estatus=Cita.ESTATUS_SI_ASISTIO,
        )
        .select_related("paciente")
        .order_by("fecha", "hora", "id")
        .first()
    )


def _cita_es_anterior_a_captacion(cita, captacion):
    fecha_captacion = timezone.localtime(
        captacion.fecha_captacion
    ).date()

    return cita.fecha < fecha_captacion


def _resultado(captacion, estado, *, cita=None, detalle="", comision=None):
    return ResultadoGeneracionComision(
        estado=estado,
        captacion_id=captacion.pk,
        cita=cita,
        detalle=detalle,
        comision=comision,
    )


@transaction.atomic
def evaluar_y_generar_comision(captacion, *, usuario=None):
    captacion = (
        Captacion.objects.select_for_update()
        .select_related("paciente", "captador")
        .get(pk=captacion.pk)
    )
    existente = ComisionCaptacion.objects.filter(captacion=captacion).first()
    if existente is not None:
        return _resultado(
            captacion,
            "ya_existia",
            cita=existente.cita_generadora,
            comision=existente,
        )
    if captacion.estado != Captacion.ESTADO_APROBADA:
        return _resultado(captacion, "captacion_no_aprobada")
    if captacion.porcentaje_comision is None:
        return _resultado(
            captacion,
            "datos_inconsistentes",
            detalle="Captación aprobada sin porcentaje autorizado.",
        )
    if captacion.porcentaje_comision == 0:
        return _resultado(
            captacion,
            "sin_comision",
            detalle="Captación configurada sin comisión.",
        )

    cita = _primera_cita_asistida(captacion.paciente)
    if cita is None:
        return _resultado(captacion, "sin_cita_asistida")
    if _cita_es_anterior_a_captacion(cita, captacion):
        return _resultado(
            captacion,
            "datos_inconsistentes",
            cita=cita,
            detalle="Existe una asistencia anterior a la captación.",
        )
    cobro = (
        CobroCita.objects.select_for_update()
        .filter(cita=cita)
        .first()
    )
    if cobro is None or cobro.total_confirmado < cobro.importe_esperado:
        return _resultado(captacion, "cita_sin_pago", cita=cita)
    base = cobro.importe_esperado
    if base <= Decimal("0.00"):
        return _resultado(captacion, "importe_servicio_invalido", cita=cita)

    monto = calcular_monto_comision(
        base_calculo=base,
        porcentaje=captacion.porcentaje_comision,
    )
    comision = ComisionCaptacion.objects.create(
        captacion=captacion,
        cita_generadora=cita,
        captador_nombre_snapshot=captacion.captador_nombre_snapshot,
        paciente_nombre_snapshot=captacion.paciente.nombre,
        porcentaje_aplicado=captacion.porcentaje_comision,
        base_calculo=base,
        monto_calculado=monto,
        moneda="MXN",
        estado=ComisionCaptacion.ESTADO_PENDIENTE_PAGO,
    )
    EventoCaptacion.objects.create(
        captacion=captacion,
        accion=EventoCaptacion.ACCION_COMISION_GENERADA,
        usuario=usuario,
        estado_anterior=captacion.estado,
        estado_nuevo=captacion.estado,
        porcentaje_comision=captacion.porcentaje_comision,
        motivo=(
            f"Comisión {comision.pk}; cita {cita.pk}; base {base}; "
            f"monto {monto}."
        ),
    )
    return _resultado(
        captacion,
        "generada",
        cita=cita,
        comision=comision,
    )


def generar_comision_captacion_si_corresponde(*, cita, usuario=None):
    """Evalúa la captación del paciente principal tras confirmar un pago."""
    if cita is None or cita.paciente_id is None:
        return None

    captacion = (
        Captacion.objects.filter(paciente_id=cita.paciente_id)
        .first()
    )
    if captacion is None:
        return None

    return evaluar_y_generar_comision(
        captacion,
        usuario=usuario,
    )


def reconciliar_comisiones_pendientes(*, captacion_id=None, usuario=None):
    captaciones = Captacion.objects.filter(estado=Captacion.ESTADO_APROBADA)
    if captacion_id is not None:
        captaciones = captaciones.filter(pk=captacion_id)
    resumen = ResumenReconciliacionComisiones()
    for captacion in captaciones.order_by("id").iterator():
        try:
            resultado = evaluar_y_generar_comision(
                captacion,
                usuario=usuario,
            )
        except Exception as error:
            resultado = _resultado(
                captacion,
                "error",
                detalle=str(error),
            )
        resumen.agregar(resultado)
    return resumen


def _resultado_reconciliacion_estado(comision, estado, detalle=""):
    return ResultadoReconciliacionEstadoComision(
        estado=estado,
        comision_id=comision.pk,
        detalle=detalle,
    )


def _registrar_evento_estado_comision(
    comision,
    *,
    accion,
    usuario,
    motivo,
):
    EventoCaptacion.objects.create(
        captacion=comision.captacion,
        accion=accion,
        usuario=usuario,
        estado_anterior=comision.captacion.estado,
        estado_nuevo=comision.captacion.estado,
        porcentaje_comision=comision.porcentaje_aplicado,
        motivo=(
            f"Comisión {comision.pk}; cita {comision.cita_generadora_id}; "
            f"{motivo}"
        ),
    )


@transaction.atomic
def reconciliar_estado_comision(comision, *, usuario=None):
    comision = (
        ComisionCaptacion.objects.select_for_update()
        .select_related("captacion", "cita_generadora")
        .get(pk=comision.pk)
    )
    estados_reconciliables = {
        ComisionCaptacion.ESTADO_PENDIENTE_PAGO,
        ComisionCaptacion.ESTADO_SUSPENDIDA,
    }
    if comision.estado not in estados_reconciliables:
        return _resultado_reconciliacion_estado(
            comision,
            "estado_no_reconciliable",
        )

    tiene_pago_vigente = cita_tiene_movimiento_confirmado(
        comision.cita_generadora
    )
    if (
        comision.estado == ComisionCaptacion.ESTADO_PENDIENTE_PAGO
        and not tiene_pago_vigente
    ):
        comision.estado = ComisionCaptacion.ESTADO_SUSPENDIDA
        comision.save(update_fields=["estado"])
        _registrar_evento_estado_comision(
            comision,
            accion=EventoCaptacion.ACCION_COMISION_SUSPENDIDA,
            usuario=usuario,
            motivo=(
                "Cita generadora sin pagos confirmados positivos vigentes. "
                "Origen: reconciliación explícita de comisiones."
            ),
        )
        return _resultado_reconciliacion_estado(comision, "suspendida")

    if (
        comision.estado == ComisionCaptacion.ESTADO_SUSPENDIDA
        and tiene_pago_vigente
    ):
        comision.estado = ComisionCaptacion.ESTADO_PENDIENTE_PAGO
        comision.save(update_fields=["estado"])
        _registrar_evento_estado_comision(
            comision,
            accion=EventoCaptacion.ACCION_COMISION_REACTIVADA,
            usuario=usuario,
            motivo=(
                "Cita generadora vuelve a contar con pago confirmado "
                "positivo vigente. Origen: reconciliación explícita de "
                "comisiones."
            ),
        )
        return _resultado_reconciliacion_estado(comision, "reactivada")

    return _resultado_reconciliacion_estado(comision, "sin_cambios")


def reconciliar_comisiones_generadas(*, comision_id=None, usuario=None):
    comisiones = ComisionCaptacion.objects.filter(
        estado__in=(
            ComisionCaptacion.ESTADO_PENDIENTE_PAGO,
            ComisionCaptacion.ESTADO_SUSPENDIDA,
        )
    )
    if comision_id is not None:
        comisiones = comisiones.filter(pk=comision_id)

    resumen = ResumenReconciliacionEstadosComision()
    for comision in comisiones.order_by("id").iterator():
        try:
            resultado = reconciliar_estado_comision(
                comision,
                usuario=usuario,
            )
        except Exception as error:
            resultado = _resultado_reconciliacion_estado(
                comision,
                "error",
                detalle=str(error),
            )
        resumen.agregar(resultado)
    return resumen


def _ids_comisiones(comisiones):
    ids = []
    for comision in comisiones:
        identificador = getattr(comision, "pk", comision)
        if not identificador:
            raise OperacionLiquidacionError(
                "comision_inexistente",
                "La selección contiene una comisión inexistente.",
            )
        ids.append(int(identificador))
    if not ids:
        raise OperacionLiquidacionError(
            "seleccion_vacia",
            "Selecciona al menos una comisión.",
        )
    if len(ids) != len(set(ids)):
        raise OperacionLiquidacionError(
            "seleccion_duplicada",
            "La selección contiene comisiones duplicadas.",
        )
    return sorted(ids)


def _validar_captador_liquidable(captador):
    if not captador.activo:
        raise OperacionLiquidacionError(
            "captador_inactivo",
            "El captador está inactivo.",
        )
    if not captador_es_elegible_para_liquidacion(captador):
        raise OperacionLiquidacionError(
            "captador_no_elegible",
            (
                "Las comisiones de terapeutas se procesarán mediante "
                "CorteSemanal en Fase 8."
            ),
        )


def _bloquear_y_validar_comisiones(*, ids, captador):
    ids_bloqueados = list(
        ComisionCaptacion.objects.select_for_update()
        .filter(pk__in=ids)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    comisiones = list(
        ComisionCaptacion.objects
        .select_related(
            "captacion__captador__usuario",
            "captacion__captador__empresa",
        )
        .filter(pk__in=ids_bloqueados)
        .order_by("pk")
    )
    if len(comisiones) != len(ids):
        raise OperacionLiquidacionError(
            "comision_inexistente",
            "Una o más comisiones seleccionadas ya no existen.",
        )
    if any(comision.captacion.captador_id != captador.pk for comision in comisiones):
        raise OperacionLiquidacionError(
            "captadores_mezclados",
            "Todas las comisiones deben pertenecer al mismo captador.",
        )
    if any(
        comision.estado != ComisionCaptacion.ESTADO_PENDIENTE_PAGO
        for comision in comisiones
    ):
        raise OperacionLiquidacionError(
            "comision_no_disponible",
            "Una o más comisiones no están pendientes de pago.",
        )
    if LineaLiquidacionComision.objects.filter(
        comision_id__in=ids,
        activa=True,
    ).exists():
        raise OperacionLiquidacionError(
            "comision_no_disponible",
            "Una o más comisiones ya están reservadas.",
        )
    return comisiones


def _total_comisiones(comisiones):
    return sum(
        (comision.monto_calculado for comision in comisiones),
        Decimal("0.00"),
    )


def _registrar_evento_liquidacion(
    liquidacion,
    *,
    accion,
    usuario,
    detalle,
):
    return EventoLiquidacion.objects.create(
        liquidacion=liquidacion,
        accion=accion,
        usuario=usuario,
        detalle=detalle,
    )


def _crear_lineas(liquidacion, comisiones, usuario):
    try:
        return LineaLiquidacionComision.objects.bulk_create(
            [
                LineaLiquidacionComision(
                    liquidacion=liquidacion,
                    comision=comision,
                    agregada_por=usuario,
                )
                for comision in comisiones
            ]
        )
    except IntegrityError as error:
        raise OperacionLiquidacionError(
            "comision_no_disponible",
            "Una comisión fue reservada por otra operación concurrente.",
        ) from error


@transaction.atomic
def crear_borrador_liquidacion(*, captador, comisiones, usuario):
    ids = _ids_comisiones(comisiones)
    captador_bloqueado = Captador.objects.select_for_update().get(pk=captador.pk)
    captador = (
        Captador.objects
        .select_related("usuario", "empresa")
        .get(pk=captador_bloqueado.pk)
    )
    _validar_captador_liquidable(captador)
    comisiones = _bloquear_y_validar_comisiones(
        ids=ids,
        captador=captador,
    )

    liquidacion = LiquidacionComisiones.objects.create(
        captador=captador,
        estado=LiquidacionComisiones.ESTADO_BORRADOR,
        beneficiario_nombre_snapshot=captador.nombre_display,
        creada_por=usuario,
    )
    _crear_lineas(liquidacion, comisiones, usuario)
    detalle = {
        "captador_id": captador.pk,
        "cantidad_comisiones": len(ids),
        "comision_ids": ids,
        "total_provisional": str(_total_comisiones(comisiones)),
        "origen": "panel_comisiones",
    }
    _registrar_evento_liquidacion(
        liquidacion,
        accion=EventoLiquidacion.ACCION_LIQUIDACION_CREADA,
        usuario=usuario,
        detalle=detalle,
    )
    _registrar_evento_liquidacion(
        liquidacion,
        accion=EventoLiquidacion.ACCION_COMISION_AGREGADA,
        usuario=usuario,
        detalle=detalle,
    )
    return liquidacion


def _bloquear_borrador(liquidacion):
    liquidacion_bloqueada = (
        LiquidacionComisiones.objects.select_for_update().get(pk=liquidacion.pk)
    )
    liquidacion = (
        LiquidacionComisiones.objects
        .select_related("captador__usuario", "captador__empresa")
        .get(pk=liquidacion_bloqueada.pk)
    )
    if liquidacion.estado != LiquidacionComisiones.ESTADO_BORRADOR:
        raise OperacionLiquidacionError(
            "borrador_inmutable",
            "La liquidación ya no es un borrador modificable.",
        )
    return liquidacion


@transaction.atomic
def agregar_comisiones_borrador(*, liquidacion, comisiones, usuario):
    liquidacion = _bloquear_borrador(liquidacion)
    _validar_captador_liquidable(liquidacion.captador)
    ids = _ids_comisiones(comisiones)
    comisiones = _bloquear_y_validar_comisiones(
        ids=ids,
        captador=liquidacion.captador,
    )
    _crear_lineas(liquidacion, comisiones, usuario)
    _registrar_evento_liquidacion(
        liquidacion,
        accion=EventoLiquidacion.ACCION_COMISION_AGREGADA,
        usuario=usuario,
        detalle={
            "cantidad_comisiones": len(ids),
            "comision_ids": ids,
            "total_agregado": str(_total_comisiones(comisiones)),
            "origen": "detalle_borrador",
        },
    )
    return liquidacion


@transaction.atomic
def retirar_comision_borrador(*, liquidacion, comision, usuario, motivo):
    motivo = (motivo or "").strip()
    if not motivo:
        raise OperacionLiquidacionError(
            "motivo_obligatorio",
            "Indica el motivo del retiro.",
        )
    liquidacion = _bloquear_borrador(liquidacion)
    try:
        linea = (
            LineaLiquidacionComision.objects.select_for_update()
            .select_related("comision")
            .get(
                liquidacion=liquidacion,
                comision=comision,
                activa=True,
            )
        )
    except LineaLiquidacionComision.DoesNotExist as error:
        raise OperacionLiquidacionError(
            "linea_no_activa",
            "La comisión no tiene una línea activa en este borrador.",
        ) from error

    linea.activa = False
    linea.retirada_en = timezone.now()
    linea.retirada_por = usuario
    linea.motivo_retiro = motivo
    linea.save(
        update_fields=[
            "activa",
            "retirada_en",
            "retirada_por",
            "motivo_retiro",
        ]
    )
    _registrar_evento_liquidacion(
        liquidacion,
        accion=EventoLiquidacion.ACCION_COMISION_RETIRADA,
        usuario=usuario,
        detalle={
            "comision_id": linea.comision_id,
            "monto_historico": str(linea.comision.monto_calculado),
            "motivo": motivo,
        },
    )
    return linea


@transaction.atomic
def cancelar_borrador_liquidacion(*, liquidacion, usuario, motivo):
    motivo = (motivo or "").strip()
    if not motivo:
        raise OperacionLiquidacionError(
            "motivo_obligatorio",
            "Indica el motivo de cancelación.",
        )
    liquidacion = _bloquear_borrador(liquidacion)
    lineas = list(
        LineaLiquidacionComision.objects.select_for_update()
        .filter(liquidacion=liquidacion, activa=True)
        .order_by("comision_id", "id")
    )
    ahora = timezone.now()
    motivo_linea = f"Liquidación borrador cancelada: {motivo}"
    for linea in lineas:
        linea.activa = False
        linea.retirada_en = ahora
        linea.retirada_por = usuario
        linea.motivo_retiro = motivo_linea
    LineaLiquidacionComision.objects.bulk_update(
        lineas,
        ["activa", "retirada_en", "retirada_por", "motivo_retiro"],
    )

    liquidacion.estado = LiquidacionComisiones.ESTADO_CANCELADA
    liquidacion.cancelada_en = ahora
    liquidacion.cancelada_por = usuario
    liquidacion.motivo_cancelacion = motivo
    liquidacion.save(
        update_fields=[
            "estado",
            "cancelada_en",
            "cancelada_por",
            "motivo_cancelacion",
        ]
    )
    _registrar_evento_liquidacion(
        liquidacion,
        accion=EventoLiquidacion.ACCION_BORRADOR_CANCELADO,
        usuario=usuario,
        detalle={
            "cantidad_lineas_liberadas": len(lineas),
            "comision_ids": [linea.comision_id for linea in lineas],
            "motivo": motivo,
        },
    )
    return liquidacion


def total_provisional_liquidacion(liquidacion):
    total = liquidacion.lineas.filter(activa=True).aggregate(
        total=Sum("comision__monto_calculado")
    )["total"]
    return total or Decimal("0.00")


def borrador_tiene_comisiones_no_elegibles(liquidacion):
    return liquidacion.lineas.filter(activa=True).exclude(
        comision__estado=ComisionCaptacion.ESTADO_PENDIENTE_PAGO
    ).exists()


@transaction.atomic
def confirmar_pago_liquidacion(
    *,
    liquidacion,
    metodo_pago,
    referencia,
    usuario,
):
    if not usuario or not usuario.has_perm("ventas.pay_liquidacion"):
        raise OperacionLiquidacionError(
            "permiso_denegado",
            "El usuario no tiene permiso para registrar pagos de liquidaciones.",
        )
    metodos_validos = {
        LiquidacionComisiones.METODO_EFECTIVO,
        LiquidacionComisiones.METODO_TRANSFERENCIA,
    }
    if metodo_pago not in metodos_validos:
        raise OperacionLiquidacionError(
            "metodo_invalido",
            "Selecciona un método de pago válido.",
        )
    referencia = (referencia or "").strip()
    if not referencia:
        raise OperacionLiquidacionError(
            "referencia_obligatoria",
            "La referencia del pago es obligatoria.",
        )

    liquidacion = _bloquear_borrador(liquidacion)
    _validar_captador_liquidable(liquidacion.captador)
    lineas = list(
        LineaLiquidacionComision.objects.select_for_update()
        .filter(liquidacion=liquidacion, activa=True)
        .order_by("comision_id", "id")
    )
    if not lineas:
        raise OperacionLiquidacionError(
            "liquidacion_sin_lineas",
            "La liquidación no contiene comisiones activas.",
        )

    comision_ids = [linea.comision_id for linea in lineas]
    comisiones = list(
        ComisionCaptacion.objects.select_for_update()
        .select_related("captacion")
        .filter(pk__in=comision_ids)
        .order_by("pk")
    )
    if len(comisiones) != len(comision_ids):
        raise OperacionLiquidacionError(
            "comision_no_elegible",
            "Una obligación incluida ya no existe.",
        )
    comisiones_por_id = {comision.pk: comision for comision in comisiones}
    for linea in lineas:
        comision = comisiones_por_id[linea.comision_id]
        if comision.captacion.captador_id != liquidacion.captador_id:
            raise OperacionLiquidacionError(
                "captadores_mezclados",
                "La liquidación contiene una comisión de otro captador.",
            )
        if comision.estado != ComisionCaptacion.ESTADO_PENDIENTE_PAGO:
            raise OperacionLiquidacionError(
                "comision_no_elegible",
                "La liquidación contiene comisiones actualmente no elegibles.",
            )

    total = Decimal("0.00")
    for linea in lineas:
        monto = comisiones_por_id[linea.comision_id].monto_calculado
        linea.monto_liquidado_snapshot = monto
        total += monto
    LineaLiquidacionComision.objects.bulk_update(
        lineas,
        ["monto_liquidado_snapshot"],
    )

    liquidacion.estado = LiquidacionComisiones.ESTADO_PAGADA
    liquidacion.monto_total_snapshot = total
    liquidacion.metodo_pago = metodo_pago
    liquidacion.referencia = referencia
    liquidacion.pagada_en = timezone.now()
    liquidacion.pagada_por = usuario
    liquidacion.save(
        update_fields=[
            "estado",
            "monto_total_snapshot",
            "metodo_pago",
            "referencia",
            "pagada_en",
            "pagada_por",
        ]
    )
    _registrar_evento_liquidacion(
        liquidacion,
        accion=EventoLiquidacion.ACCION_LIQUIDACION_PAGADA,
        usuario=usuario,
        detalle={
            "cantidad_comisiones": len(comision_ids),
            "comision_ids": comision_ids,
            "monto_total": str(total),
            "metodo_pago": metodo_pago,
            "referencia": referencia,
            "beneficiario": liquidacion.beneficiario_nombre_snapshot,
        },
    )
    return liquidacion
