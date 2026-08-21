from io import BytesIO
import logging

import qrcode
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from clinica.models import Paciente, Servicio

from .classification import clasificacion_captador_liquidacion
from .forms import (
    AprobarCaptacionForm,
    CaptacionForm,
    CaptadorEditarForm,
    CaptadorForm,
    DesactivarCaptadorForm,
    CancelarBorradorLiquidacionForm,
    MotivoRetiroComisionForm,
    RegistrarPagoLiquidacionForm,
    RechazarCaptacionForm,
    SeleccionComisionesLiquidacionForm,
    ValidarCodigoForm,
)
from .models import (
    Captacion,
    Captador,
    CodigoCaptacion,
    ComisionCaptacion,
    EventoCaptador,
    IntentoCaptacionRechazado,
    LiquidacionComisiones,
)
from .queries import (
    comisiones_disponibles_para_liquidacion,
    estado_derivado_comision,
    eventos_incidencia_liquidacion,
    lineas_con_incidencia,
    listar_liquidaciones,
    obtener_detalle_comision,
    obtener_liquidacion_detalle,
    obtener_resumen_liquidaciones,
    obtener_resumen_comisiones,
    listar_comisiones,
)
from .services import (
    CaptacionYaRevisadaError,
    OperacionLiquidacionError,
    agregar_comisiones_borrador,
    aprobar_captacion,
    cambiar_estado_captador,
    cancelar_borrador_liquidacion,
    confirmar_pago_liquidacion,
    crear_borrador_liquidacion,
    borrador_tiene_comisiones_no_elegibles,
    evaluar_elegibilidad_captacion,
    rechazar_captacion,
    registrar_captacion,
    retirar_comision_borrador,
    total_provisional_liquidacion,
)


logger = logging.getLogger(__name__)


def _puede_entrar_ventas(user):
    return any(
        user.has_perm(permission)
        for permission in (
            "ventas.manage_captadores",
            "ventas.validate_codigo",
            "ventas.view_codigo_propio",
            "ventas.view_captaciones",
            "ventas.register_captacion",
            "ventas.review_captacion",
            "ventas.view_comisiones_captacion",
            "ventas.view_liquidaciones",
            "ventas.create_liquidacion",
        )
    )


@login_required
def inicio(request):
    if not _puede_entrar_ventas(request.user):
        raise PermissionDenied
    return render(
        request,
        "ventas/inicio.html",
        {
            "puede_administrar": request.user.has_perm(
                "ventas.manage_captadores"
            ),
            "puede_validar": request.user.has_perm("ventas.validate_codigo")
            or request.user.has_perm("ventas.manage_captadores"),
            "puede_ver_captaciones": _puede_ver_captaciones(request.user),
            "tiene_qr_propio": hasattr(request.user, "captador_ventas")
            and request.user.has_perm("ventas.view_codigo_propio"),
            "puede_ver_comisiones": request.user.has_perm(
                "ventas.view_comisiones_captacion"
            ),
            "puede_ver_liquidaciones": request.user.has_perm(
                "ventas.view_liquidaciones"
            ),
        },
    )


@login_required
@permission_required("ventas.manage_captadores", raise_exception=True)
def captadores_lista(request):
    captadores = Captador.objects.select_related(
        "usuario", "empresa", "creado_por"
    ).prefetch_related("codigos").all()
    return render(request, "ventas/captadores_lista.html", {"captadores": captadores})


@login_required
@permission_required("ventas.manage_captadores", raise_exception=True)
def captador_nuevo(request):
    if request.method == "POST":
        form = CaptadorForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                captador = form.save(commit=False)
                captador.creado_por = request.user
                captador.save()
                EventoCaptador.objects.create(
                    captador=captador,
                    accion=EventoCaptador.ACCION_CREADO,
                    usuario=request.user,
                    detalle="Alta de captador.",
                )
            messages.success(request, "Captador creado y código generado correctamente.")
            return redirect("ventas:captador_detalle", pk=captador.pk)
    else:
        form = CaptadorForm()
    return render(request, "ventas/captador_form.html", {"form": form, "titulo": "Nuevo captador"})


@login_required
@permission_required("ventas.manage_captadores", raise_exception=True)
def captador_detalle(request, pk):
    captador = get_object_or_404(
        Captador.objects.select_related("usuario", "empresa", "creado_por", "desactivado_por"),
        pk=pk,
    )
    return render(request, "ventas/captador_detalle.html", {
        "captador": captador,
        "codigo": captador.codigo_activo,
        "desactivar_form": DesactivarCaptadorForm(),
    })


@login_required
@permission_required("ventas.manage_captadores", raise_exception=True)
def captador_editar(request, pk):
    captador = get_object_or_404(Captador, pk=pk)
    if request.method == "POST":
        form = CaptadorEditarForm(request.POST, instance=captador)
        if form.is_valid():
            form.save()
            EventoCaptador.objects.create(
                captador=captador,
                accion=EventoCaptador.ACCION_EDITADO,
                usuario=request.user,
                detalle="Información de contacto actualizada.",
            )
            messages.success(request, "Información actualizada.")
            return redirect("ventas:captador_detalle", pk=pk)
    else:
        form = CaptadorEditarForm(instance=captador)
    return render(request, "ventas/captador_form.html", {
        "form": form, "titulo": "Editar captador", "captador": captador
    })


@login_required
@permission_required("ventas.manage_captadores", raise_exception=True)
@require_POST
def captador_desactivar(request, pk):
    captador = get_object_or_404(Captador, pk=pk)
    form = DesactivarCaptadorForm(request.POST)
    if form.is_valid():
        cambiar_estado_captador(
            captador,
            activar=False,
            usuario=request.user,
            motivo=form.cleaned_data["motivo"],
        )
        messages.success(request, "Captador desactivado; su código e histórico se conservaron.")
    return redirect("ventas:captador_detalle", pk=pk)


@login_required
@permission_required("ventas.manage_captadores", raise_exception=True)
@require_POST
def captador_reactivar(request, pk):
    captador = get_object_or_404(Captador, pk=pk)
    cambiar_estado_captador(captador, activar=True, usuario=request.user)
    messages.success(request, "Captador reactivado con su mismo código.")
    return redirect("ventas:captador_detalle", pk=pk)


def _respuesta_qr(codigo, request):
    destino = request.build_absolute_uri(
        reverse("ventas:validar_token", kwargs={"token": codigo.token})
    )
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    qr.add_data(destino)
    qr.make(fit=True)
    imagen = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    imagen.save(buffer, format="PNG")
    return HttpResponse(buffer.getvalue(), content_type="image/png")


@login_required
def captador_qr(request, pk):
    captador = get_object_or_404(Captador, pk=pk)
    es_propio = captador.usuario_id == request.user.id
    if not request.user.has_perm("ventas.manage_captadores") and not (
        es_propio and request.user.has_perm("ventas.view_codigo_propio")
    ):
        raise PermissionDenied
    codigo = get_object_or_404(
        CodigoCaptacion,
        captador=captador,
        activo=True,
    )
    return _respuesta_qr(codigo, request)


@login_required
def mi_qr(request):
    if not request.user.has_perm("ventas.view_codigo_propio"):
        raise PermissionDenied
    captador = get_object_or_404(Captador, usuario=request.user)
    return render(request, "ventas/mi_qr.html", {
        "captador": captador,
        "codigo": captador.codigo_activo,
    })


@login_required
def validar_codigo(request):
    if not (
        request.user.has_perm("ventas.validate_codigo")
        or request.user.has_perm("ventas.manage_captadores")
    ):
        raise PermissionDenied
    resultado = None
    form = ValidarCodigoForm(request.GET or None)
    if form.is_valid():
        resultado = CodigoCaptacion.objects.select_related(
            "captador__usuario", "captador__empresa"
        ).filter(token=form.cleaned_data["codigo"], activo=True).first()
    return render(request, "ventas/validar_codigo.html", {"form": form, "resultado": resultado})


def validar_token(request, token):
    codigo = CodigoCaptacion.objects.select_related(
        "captador__usuario", "captador__empresa"
    ).filter(token=token, activo=True).first()
    if not codigo:
        return render(
            request,
            "ventas/validacion_publica.html",
            {"estado": "invalido"},
            status=404,
        )
    estado = "activo" if codigo.captador.activo else "inactivo"
    return render(request, "ventas/validacion_publica.html", {
        "estado": estado,
        "captador_nombre": codigo.captador.nombre_display if estado == "activo" else "",
    })


def _puede_ver_captaciones(user):
    return any(
        user.has_perm(permission)
        for permission in (
            "ventas.view_captaciones",
            "ventas.register_captacion",
            "ventas.review_captacion",
            "ventas.manage_captadores",
        )
    )


def _puede_registrar_captacion(user):
    return user.has_perm("ventas.register_captacion") or user.has_perm(
        "ventas.manage_captadores"
    )


@login_required
def captaciones_lista(request):
    if not _puede_ver_captaciones(request.user):
        raise PermissionDenied
    captaciones = Captacion.objects.select_related(
        "paciente", "captador", "codigo", "registrado_por"
    )
    estado = request.GET.get("estado", "").strip()
    captador_id = request.GET.get("captador", "").strip()
    tipo = request.GET.get("tipo", "").strip()
    fecha_desde = request.GET.get("fecha_desde", "").strip()
    fecha_hasta = request.GET.get("fecha_hasta", "").strip()
    q = request.GET.get("q", "").strip()
    if estado:
        captaciones = captaciones.filter(estado=estado)
    if captador_id.isdigit():
        captaciones = captaciones.filter(captador_id=captador_id)
    if tipo:
        captaciones = captaciones.filter(captador__tipo=tipo)
    if fecha_desde:
        captaciones = captaciones.filter(fecha_captacion__date__gte=fecha_desde)
    if fecha_hasta:
        captaciones = captaciones.filter(fecha_captacion__date__lte=fecha_hasta)
    if q:
        captaciones = captaciones.filter(
            Q(paciente__nombre__icontains=q)
            | Q(captador_nombre_snapshot__icontains=q)
        )

    resumen = Captacion.objects.aggregate(
        pendientes=Count(
            "id",
            filter=Q(estado=Captacion.ESTADO_PENDIENTE),
        ),
        aprobadas=Count(
            "id",
            filter=Q(estado=Captacion.ESTADO_APROBADA),
        ),
        rechazadas=Count(
            "id",
            filter=Q(estado=Captacion.ESTADO_RECHAZADA),
        ),
    )
    return render(request, "ventas/captaciones_lista.html", {
        "captaciones": captaciones,
        "captadores": Captador.objects.order_by("tipo", "id"),
        "tipos": Captador.TIPO_CHOICES,
        "estados": Captacion.ESTADO_CHOICES,
        "filtros": request.GET,
        "puede_registrar": _puede_registrar_captacion(request.user),
        "puede_revisar": request.user.has_perm("ventas.review_captacion"),
        "resumen": resumen,
    })


@login_required
def captacion_nueva(request):
    if not _puede_registrar_captacion(request.user):
        raise PermissionDenied
    confirmacion = False
    if request.method == "POST":
        form = CaptacionForm(request.POST)
        if form.is_valid():
            if request.POST.get("accion") == "registrar":
                try:
                    captacion = registrar_captacion(
                        paciente=form.cleaned_data["paciente"],
                        codigo=form.codigo_validado,
                        usuario=request.user,
                    )
                except ValueError as exc:
                    form.add_error(None, str(exc))
                    logger.info(
                        "Intento de captación rechazado usuario=%s paciente=%s motivo=%s",
                        request.user.pk,
                        form.cleaned_data["paciente"].pk,
                        exc,
                    )
                else:
                    messages.success(request, "Captación registrada con estado Pendiente.")
                    return redirect("ventas:captacion_detalle", pk=captacion.pk)
            else:
                confirmacion = True
        else:
            paciente_id = request.POST.get("paciente", "")
            if paciente_id.isdigit():
                paciente_intento = Paciente.objects.filter(pk=paciente_id).first()
                if paciente_intento:
                    elegibilidad = evaluar_elegibilidad_captacion(paciente_intento)
                    if elegibilidad.codigo in {
                        IntentoCaptacionRechazado.MOTIVO_ATENCION_PREVIA,
                        IntentoCaptacionRechazado.MOTIVO_YA_CAPTADO,
                    }:
                        IntentoCaptacionRechazado.objects.create(
                            paciente=paciente_intento,
                            registrado_por=request.user,
                            motivo=elegibilidad.codigo,
                        )
            paciente = form.cleaned_data.get("paciente")
            logger.info(
                "Intento de captación rechazado usuario=%s paciente=%s errores=%s",
                request.user.pk,
                paciente.pk if paciente else None,
                form.errors.as_json(),
            )
    else:
        form = CaptacionForm()
    return render(request, "ventas/captacion_form.html", {
        "form": form,
        "confirmacion": confirmacion,
        "codigo": form.codigo_validado,
    })


@login_required
def captacion_detalle(request, pk):
    if not _puede_ver_captaciones(request.user):
        raise PermissionDenied
    captacion = get_object_or_404(
        Captacion.objects.select_related(
            "paciente",
            "captador",
            "codigo",
            "registrado_por",
            "decidido_por",
        ),
        pk=pk,
    )
    puede_revisar = request.user.has_perm("ventas.review_captacion")
    return render(
        request,
        "ventas/captacion_detalle.html",
        {
            "captacion": captacion,
            "puede_revisar": puede_revisar,
            "aprobar_form": AprobarCaptacionForm(),
            "rechazar_form": RechazarCaptacionForm(),
        },
    )


@login_required
@permission_required("ventas.review_captacion", raise_exception=True)
@require_POST
def captacion_aprobar(request, pk):
    captacion = get_object_or_404(Captacion, pk=pk)
    form = AprobarCaptacionForm(request.POST)
    if not form.is_valid():
        messages.error(
            request,
            "Indica un porcentaje entero entre 1 y 10.",
        )
        return redirect("ventas:captacion_detalle", pk=pk)

    try:
        aprobar_captacion(
            captacion=captacion,
            porcentaje=form.cleaned_data["porcentaje_comision"],
            usuario=request.user,
        )
    except CaptacionYaRevisadaError as exc:
        messages.warning(request, str(exc))
    else:
        messages.success(request, "Captación aprobada correctamente.")
    return redirect("ventas:captacion_detalle", pk=pk)


@login_required
@permission_required("ventas.review_captacion", raise_exception=True)
@require_POST
def captacion_rechazar(request, pk):
    captacion = get_object_or_404(Captacion, pk=pk)
    form = RechazarCaptacionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "El motivo del rechazo es obligatorio.")
        return redirect("ventas:captacion_detalle", pk=pk)

    try:
        rechazar_captacion(
            captacion=captacion,
            motivo=form.cleaned_data["motivo_rechazo"],
            usuario=request.user,
        )
    except CaptacionYaRevisadaError as exc:
        messages.warning(request, str(exc))
    else:
        messages.success(request, "Captación rechazada correctamente.")
    return redirect("ventas:captacion_detalle", pk=pk)


@login_required
def elegibilidad_paciente(request, paciente_id):
    if not _puede_registrar_captacion(request.user):
        raise PermissionDenied
    paciente = get_object_or_404(Paciente, pk=paciente_id)
    resultado = evaluar_elegibilidad_captacion(paciente)
    return JsonResponse({
        "elegible": resultado.elegible,
        "codigo": resultado.codigo,
        "mensaje": resultado.mensaje,
    })


@login_required
@permission_required(
    "ventas.view_comisiones_captacion",
    raise_exception=True,
)
def comisiones_panel(request):
    filtros = {
        "estado": request.GET.get("estado", "").strip(),
        "fecha_desde": request.GET.get("fecha_desde", "").strip(),
        "fecha_hasta": request.GET.get("fecha_hasta", "").strip(),
        "captador_id": request.GET.get("captador", "").strip(),
        "paciente": request.GET.get("paciente", "").strip(),
        "tipo_captador": request.GET.get("tipo", "").strip(),
        "servicio_id": request.GET.get("servicio", "").strip(),
        "busqueda": request.GET.get("q", "").strip(),
    }
    comisiones = listar_comisiones(**filtros)
    pagina = Paginator(comisiones, 25).get_page(request.GET.get("page"))
    ids_disponibles = set(
        comisiones_disponibles_para_liquidacion().values_list("pk", flat=True)
    )
    for comision in pagina.object_list:
        comision.disponible_para_liquidacion = comision.pk in ids_disponibles
        comision.estado_visual = estado_derivado_comision(comision)
    parametros_paginacion = request.GET.copy()
    parametros_paginacion.pop("page", None)
    return render(
        request,
        "ventas/comisiones_panel.html",
        {
            "pagina": pagina,
            "resumen": obtener_resumen_comisiones(),
            "captadores": Captador.objects.select_related(
                "usuario",
                "usuario__perfil_terapeuta",
                "empresa",
            ).order_by("tipo", "id"),
            "servicios": Servicio.objects.order_by("nombre", "id"),
            "estados": ComisionCaptacion.ESTADO_CHOICES,
            "tipos_captador": Captador.TIPO_CHOICES,
            "filtros": request.GET,
            "parametros_paginacion": parametros_paginacion.urlencode(),
            "puede_crear_liquidacion": request.user.has_perm(
                "ventas.create_liquidacion"
            ),
        },
    )


@login_required
@permission_required(
    "ventas.view_comisiones_captacion",
    raise_exception=True,
)
def comision_detalle(request, pk):
    try:
        detalle = obtener_detalle_comision(pk)
    except ComisionCaptacion.DoesNotExist:
        detalle = None
    if detalle is None:
        raise Http404
    return render(
        request,
        "ventas/comision_detalle.html",
        {"detalle": detalle, "comision": detalle.comision},
    )


@login_required
@permission_required("ventas.create_liquidacion", raise_exception=True)
@require_POST
def liquidacion_crear(request):
    form = SeleccionComisionesLiquidacionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Selecciona comisiones disponibles.")
        return redirect("ventas:comisiones_panel")
    comisiones = list(form.cleaned_data["comisiones"])
    captador = comisiones[0].captacion.captador
    try:
        liquidacion = crear_borrador_liquidacion(
            captador=captador,
            comisiones=comisiones,
            usuario=request.user,
        )
    except OperacionLiquidacionError as error:
        messages.error(request, str(error))
        return redirect("ventas:comisiones_panel")
    messages.success(request, "El borrador de liquidación fue creado.")
    return redirect("ventas:liquidacion_detalle", pk=liquidacion.pk)


@login_required
@permission_required("ventas.view_liquidaciones", raise_exception=True)
def liquidacion_detalle(request, pk):
    liquidacion = get_object_or_404(
        LiquidacionComisiones,
        pk=pk,
    )
    liquidacion = obtener_liquidacion_detalle(liquidacion.pk)
    lineas_activas = liquidacion.lineas.filter(activa=True)
    lineas_retiradas = liquidacion.lineas.filter(activa=False)
    disponibles = comisiones_disponibles_para_liquidacion(
        captador=liquidacion.captador,
    )
    return render(
        request,
        "ventas/liquidacion_detalle.html",
        {
            "liquidacion": liquidacion,
            "lineas_activas": lineas_activas,
            "lineas_retiradas": lineas_retiradas,
            "eventos": liquidacion.eventos.all(),
            "total_provisional": total_provisional_liquidacion(liquidacion),
            "tiene_no_elegibles": borrador_tiene_comisiones_no_elegibles(
                liquidacion
            ),
            "form_agregar": SeleccionComisionesLiquidacionForm(
                captador=liquidacion.captador,
            ),
            "disponibles": disponibles,
            "form_retirar": MotivoRetiroComisionForm(),
            "form_cancelar": CancelarBorradorLiquidacionForm(),
            "clasificacion_captador": clasificacion_captador_liquidacion(
                liquidacion.captador
            ),
            "lineas_incidencia": lineas_con_incidencia(liquidacion),
            "eventos_incidencia": eventos_incidencia_liquidacion(liquidacion),
        },
    )


@login_required
@permission_required("ventas.view_liquidaciones", raise_exception=True)
def liquidaciones_panel(request):
    filtros = {
        "estado": request.GET.get("estado", "").strip(),
        "captador_id": request.GET.get("captador", "").strip(),
        "tipo_captador": request.GET.get("tipo", "").strip(),
        "creada_desde": request.GET.get("creada_desde", "").strip(),
        "creada_hasta": request.GET.get("creada_hasta", "").strip(),
        "pagada_desde": request.GET.get("pagada_desde", "").strip(),
        "pagada_hasta": request.GET.get("pagada_hasta", "").strip(),
        "metodo_pago": request.GET.get("metodo", "").strip(),
        "incidencia": request.GET.get("incidencia", "").strip(),
        "busqueda": request.GET.get("q", "").strip(),
    }
    liquidaciones = listar_liquidaciones(**filtros)
    pagina = Paginator(liquidaciones, 25).get_page(request.GET.get("page"))
    for liquidacion in pagina.object_list:
        liquidacion.clasificacion_panel = clasificacion_captador_liquidacion(
            liquidacion.captador
        )
    parametros_paginacion = request.GET.copy()
    parametros_paginacion.pop("page", None)
    return render(
        request,
        "ventas/liquidaciones_panel.html",
        {
            "pagina": pagina,
            "resumen": obtener_resumen_liquidaciones(),
            "captadores": Captador.objects.select_related(
                "usuario",
                "empresa",
            ).order_by("tipo", "id"),
            "estados": LiquidacionComisiones.ESTADO_CHOICES,
            "tipos_captador": Captador.TIPO_CHOICES,
            "metodos_pago": LiquidacionComisiones.METODO_PAGO_CHOICES,
            "filtros": request.GET,
            "parametros_paginacion": parametros_paginacion.urlencode(),
        },
    )


@login_required
@permission_required("ventas.change_draft_liquidacion", raise_exception=True)
@require_POST
def liquidacion_agregar(request, pk):
    liquidacion = get_object_or_404(LiquidacionComisiones, pk=pk)
    form = SeleccionComisionesLiquidacionForm(
        request.POST,
        captador=liquidacion.captador,
    )
    if form.is_valid():
        try:
            agregar_comisiones_borrador(
                liquidacion=liquidacion,
                comisiones=form.cleaned_data["comisiones"],
                usuario=request.user,
            )
        except OperacionLiquidacionError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Las comisiones fueron agregadas.")
    else:
        messages.error(request, "La selección contiene comisiones no disponibles.")
    return redirect("ventas:liquidacion_detalle", pk=pk)


@login_required
@permission_required("ventas.pay_liquidacion", raise_exception=True)
def liquidacion_registrar_pago(request, pk):
    liquidacion = get_object_or_404(LiquidacionComisiones, pk=pk)
    if liquidacion.estado != LiquidacionComisiones.ESTADO_BORRADOR:
        messages.error(request, "La liquidación ya no puede pagarse.")
        return redirect("ventas:liquidacion_detalle", pk=pk)
    if borrador_tiene_comisiones_no_elegibles(liquidacion):
        messages.error(
            request,
            "La liquidación contiene comisiones actualmente no elegibles.",
        )
        return redirect("ventas:liquidacion_detalle", pk=pk)

    form = RegistrarPagoLiquidacionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            confirmar_pago_liquidacion(
                liquidacion=liquidacion,
                metodo_pago=form.cleaned_data["metodo_pago"],
                referencia=form.cleaned_data["referencia"],
                usuario=request.user,
            )
        except OperacionLiquidacionError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "El pago de la liquidación fue registrado.")
            return redirect("ventas:liquidacion_detalle", pk=pk)
    return render(
        request,
        "ventas/liquidacion_registrar_pago.html",
        {
            "liquidacion": obtener_liquidacion_detalle(pk),
            "form": form,
            "total": total_provisional_liquidacion(liquidacion),
            "lineas": liquidacion.lineas.filter(activa=True).select_related(
                "comision"
            ),
        },
    )


@login_required
@permission_required("ventas.change_draft_liquidacion", raise_exception=True)
@require_POST
def liquidacion_retirar(request, pk, comision_id):
    liquidacion = get_object_or_404(LiquidacionComisiones, pk=pk)
    comision = get_object_or_404(ComisionCaptacion, pk=comision_id)
    form = MotivoRetiroComisionForm(request.POST)
    if form.is_valid():
        try:
            retirar_comision_borrador(
                liquidacion=liquidacion,
                comision=comision,
                usuario=request.user,
                motivo=form.cleaned_data["motivo"],
            )
        except OperacionLiquidacionError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "La comisión fue retirada.")
    else:
        messages.error(request, "El motivo del retiro es obligatorio.")
    return redirect("ventas:liquidacion_detalle", pk=pk)


@login_required
@permission_required("ventas.cancel_draft_liquidacion", raise_exception=True)
@require_POST
def liquidacion_cancelar(request, pk):
    liquidacion = get_object_or_404(LiquidacionComisiones, pk=pk)
    form = CancelarBorradorLiquidacionForm(request.POST)
    if form.is_valid():
        try:
            cancelar_borrador_liquidacion(
                liquidacion=liquidacion,
                usuario=request.user,
                motivo=form.cleaned_data["motivo"],
            )
        except OperacionLiquidacionError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "El borrador fue cancelado.")
    else:
        messages.error(request, "El motivo de cancelación es obligatorio.")
    return redirect("ventas:liquidacion_detalle", pk=pk)
