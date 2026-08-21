import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


def generar_token_captacion():
    """Token URL-safe con 192 bits de entropía."""
    return secrets.token_urlsafe(24)


class Captador(models.Model):
    TIPO_INTERNO = "interno"
    TIPO_EMPRESA = "empresa"
    TIPO_EXTERNO = "externo"
    TIPO_CHOICES = [
        (TIPO_INTERNO, "Usuario interno"),
        (TIPO_EMPRESA, "Empresa existente"),
        (TIPO_EXTERNO, "Organización externa"),
    ]

    ORG_EMPRESA = "empresa"
    ORG_ESCUELA = "escuela"
    ORG_UNIVERSIDAD = "universidad"
    ORG_ORGANIZACION = "organizacion"
    ORG_OTRO = "otro"
    ORGANIZACION_CHOICES = [
        (ORG_EMPRESA, "Empresa"),
        (ORG_ESCUELA, "Escuela"),
        (ORG_UNIVERSIDAD, "Universidad"),
        (ORG_ORGANIZACION, "Organización"),
        (ORG_OTRO, "Otro"),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="captador_ventas",
    )
    empresa = models.OneToOneField(
        "clinica.Empresa",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="captador_ventas",
    )
    nombre_externo = models.CharField(max_length=200, blank=True)
    tipo_organizacion = models.CharField(
        max_length=20, choices=ORGANIZACION_CHOICES, blank=True
    )
    contacto = models.CharField(max_length=150, blank=True)
    correo = models.EmailField(blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="captadores_creados",
    )
    desactivado_en = models.DateTimeField(null=True, blank=True)
    desactivado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="captadores_desactivados",
    )
    motivo_desactivacion = models.TextField(blank=True)

    class Meta:
        ordering = ["tipo", "id"]
        permissions = [
            ("manage_captadores", "Puede administrar captadores"),
            ("view_codigo_propio", "Puede consultar su propio código de captación"),
            ("validate_codigo", "Puede validar códigos de captación"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        tipo="interno",
                        usuario__isnull=False,
                        empresa__isnull=True,
                        nombre_externo="",
                        tipo_organizacion="",
                    )
                    | Q(
                        tipo="empresa",
                        usuario__isnull=True,
                        empresa__isnull=False,
                        nombre_externo="",
                        tipo_organizacion="",
                    )
                    | (
                        Q(
                            tipo="externo",
                            usuario__isnull=True,
                            empresa__isnull=True,
                        )
                        & ~Q(nombre_externo="")
                        & ~Q(tipo_organizacion="")
                    )
                ),
                name="ventas_captador_identidad_coherente",
            ),
        ]

    @property
    def nombre_display(self):
        if self.usuario_id:
            nombre = self.usuario.get_full_name().strip()
            return nombre or self.usuario.username
        if self.empresa_id:
            return self.empresa.nombre
        return self.nombre_externo

    @property
    def contacto_display(self):
        if self.tipo == self.TIPO_INTERNO and self.usuario_id:
            return self.usuario.email or "—"
        if self.tipo == self.TIPO_EMPRESA:
            return self.contacto or self.correo or self.telefono or "—"
        return self.contacto or self.correo or self.telefono or "—"

    @property
    def clasificacion_display(self):
        if self.tipo == self.TIPO_EXTERNO:
            return self.get_tipo_organizacion_display()
        if self.tipo == self.TIPO_EMPRESA:
            return "Empresa"
        return "Usuario interno"

    @property
    def codigo_activo(self):
        return self.codigos.filter(activo=True).first()

    def clean(self):
        errores = {}
        if self.tipo == self.TIPO_INTERNO:
            if not self.usuario_id:
                errores["usuario"] = "Selecciona un usuario interno."
            if self.empresa_id or self.nombre_externo or self.tipo_organizacion:
                errores["tipo"] = (
                    "Un captador interno solo puede vincularse a un usuario."
                )
        elif self.tipo == self.TIPO_EMPRESA:
            if not self.empresa_id:
                errores["empresa"] = "Selecciona una empresa existente."
            if self.usuario_id or self.nombre_externo or self.tipo_organizacion:
                errores["tipo"] = (
                    "Este captador solo puede vincularse a una empresa."
                )
        elif self.tipo == self.TIPO_EXTERNO:
            if not self.nombre_externo:
                errores["nombre_externo"] = "Indica el nombre de la organización."
            if not self.tipo_organizacion:
                errores["tipo_organizacion"] = "Selecciona el tipo de organización."
            if self.usuario_id or self.empresa_id:
                errores["tipo"] = (
                    "Una organización externa no vincula usuario ni empresa."
                )
        else:
            errores["tipo"] = "Selecciona un tipo de captador válido."
        if errores:
            raise ValidationError(errores)

    def __str__(self):
        return self.nombre_display


class CodigoCaptacion(models.Model):
    captador = models.ForeignKey(
        Captador, on_delete=models.PROTECT, related_name="codigos"
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        editable=False,
        default=generar_token_captacion,
    )
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    revocado_en = models.DateTimeField(null=True, blank=True)
    motivo_revocacion = models.TextField(blank=True)

    class Meta:
        ordering = ["-activo", "-creado_en"]
        constraints = [
            models.UniqueConstraint(
                fields=["captador"],
                condition=Q(activo=True),
                name="ventas_un_codigo_activo_por_captador",
            )
        ]

    def __str__(self):
        return f"Código de {self.captador}"


class EventoCaptador(models.Model):
    ACCION_CREADO = "creado"
    ACCION_EDITADO = "editado"
    ACCION_DESACTIVADO = "desactivado"
    ACCION_REACTIVADO = "reactivado"
    ACCION_CHOICES = [
        (ACCION_CREADO, "Creado"),
        (ACCION_EDITADO, "Editado"),
        (ACCION_DESACTIVADO, "Desactivado"),
        (ACCION_REACTIVADO, "Reactivado"),
    ]

    captador = models.ForeignKey(
        Captador, on_delete=models.PROTECT, related_name="eventos"
    )
    accion = models.CharField(max_length=20, choices=ACCION_CHOICES)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    detalle = models.CharField(max_length=255, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.captador} — {self.get_accion_display()}"


class Captacion(models.Model):
    ESTADO_PENDIENTE = "pendiente"
    ESTADO_APROBADA = "aprobada"
    ESTADO_RECHAZADA = "rechazada"
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_APROBADA, "Aprobada"),
        (ESTADO_RECHAZADA, "Rechazada"),
    ]

    paciente = models.OneToOneField(
        "clinica.Paciente", on_delete=models.PROTECT, related_name="captacion_ventas"
    )
    captador = models.ForeignKey(
        Captador, on_delete=models.PROTECT, related_name="captaciones"
    )
    codigo = models.ForeignKey(
        CodigoCaptacion, on_delete=models.PROTECT, related_name="captaciones"
    )
    fecha_captacion = models.DateTimeField(auto_now_add=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="captaciones_registradas",
    )
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE
    )
    canal = models.CharField(max_length=50, blank=True)
    captador_nombre_snapshot = models.CharField(max_length=200)
    captador_tipo_snapshot = models.CharField(max_length=100)
    porcentaje_comision = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    decidido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="captaciones_decididas",
    )
    decidido_en = models.DateTimeField(null=True, blank=True)
    motivo_rechazo = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_captacion", "-id"]
        permissions = [
            ("view_captaciones", "Puede consultar captaciones"),
            ("register_captacion", "Puede registrar captaciones"),
            ("review_captacion", "Puede aprobar o rechazar captaciones"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(porcentaje_comision__isnull=True)
                    | Q(porcentaje_comision__gte=1, porcentaje_comision__lte=10)
                ),
                name="ventas_captacion_porcentaje_1_10",
            ),
        ]

    def clean(self):
        if self.codigo_id and self.captador_id:
            codigo_captador_id = getattr(self.codigo, "captador_id", None)
            if codigo_captador_id != self.captador_id:
                raise ValidationError(
                    {"codigo": "El código no pertenece al captador seleccionado."}
                )

    def __str__(self):
        return f"{self.paciente} ← {self.captador_nombre_snapshot}"


class IntentoCaptacionRechazado(models.Model):
    MOTIVO_ATENCION_PREVIA = "atencion_previa"
    MOTIVO_YA_CAPTADO = "ya_captado"
    MOTIVO_CHOICES = [
        (MOTIVO_ATENCION_PREVIA, "Atención previa"),
        (MOTIVO_YA_CAPTADO, "Ya cuenta con captación"),
    ]

    paciente = models.ForeignKey(
        "clinica.Paciente",
        on_delete=models.PROTECT,
        related_name="intentos_captacion_rechazados",
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="intentos_captacion_rechazados",
    )
    motivo = models.CharField(max_length=30, choices=MOTIVO_CHOICES)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en", "-id"]

    def __str__(self):
        return f"{self.paciente} — {self.get_motivo_display()}"


class EventoCaptacion(models.Model):
    ACCION_APROBADA = "captacion_aprobada"
    ACCION_RECHAZADA = "captacion_rechazada"
    ACCION_COMISION_GENERADA = "comision_generada"
    ACCION_COMISION_SUSPENDIDA = "comision_suspendida"
    ACCION_COMISION_REACTIVADA = "comision_reactivada"
    ACCION_CHOICES = [
        (ACCION_APROBADA, "Captación aprobada"),
        (ACCION_RECHAZADA, "Captación rechazada"),
        (ACCION_COMISION_GENERADA, "Comisión generada"),
        (ACCION_COMISION_SUSPENDIDA, "Comisión suspendida"),
        (ACCION_COMISION_REACTIVADA, "Comisión reactivada"),
    ]

    captacion = models.ForeignKey(
        Captacion,
        on_delete=models.PROTECT,
        related_name="eventos",
    )
    accion = models.CharField(max_length=30, choices=ACCION_CHOICES)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eventos_captacion",
    )
    estado_anterior = models.CharField(max_length=20, choices=Captacion.ESTADO_CHOICES)
    estado_nuevo = models.CharField(max_length=20, choices=Captacion.ESTADO_CHOICES)
    porcentaje_comision = models.PositiveSmallIntegerField(null=True, blank=True)
    motivo = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en", "-id"]

    def __str__(self):
        return f"Captación {self.captacion_id} — {self.get_accion_display()}"


class ComisionCaptacion(models.Model):
    ESTADO_PENDIENTE_PAGO = "pendiente_pago"
    ESTADO_SUSPENDIDA = "suspendida"
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE_PAGO, "Pendiente de pago"),
        (ESTADO_SUSPENDIDA, "Suspendida"),
    ]

    captacion = models.OneToOneField(
        Captacion,
        on_delete=models.PROTECT,
        related_name="comision",
    )
    cita_generadora = models.OneToOneField(
        "clinica.Cita",
        on_delete=models.PROTECT,
        related_name="comision_captacion_generada",
    )
    captador_nombre_snapshot = models.CharField(max_length=200)
    paciente_nombre_snapshot = models.CharField(max_length=200)
    porcentaje_aplicado = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    base_calculo = models.DecimalField(max_digits=12, decimal_places=2)
    monto_calculado = models.DecimalField(max_digits=12, decimal_places=2)
    moneda = models.CharField(max_length=3, default="MXN")
    generada_en = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default=ESTADO_PENDIENTE_PAGO,
    )

    class Meta:
        ordering = ["-generada_en", "-id"]
        verbose_name = "Comisión de captación"
        verbose_name_plural = "Comisiones de captación"
        permissions = [
            (
                "view_comisiones_captacion",
                "Puede consultar obligaciones por comisiones de captación",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    porcentaje_aplicado__gte=1,
                    porcentaje_aplicado__lte=10,
                ),
                name="ventas_comision_porcentaje_1_10",
            ),
            models.CheckConstraint(
                condition=Q(base_calculo__gte=0),
                name="ventas_comision_base_no_negativa",
            ),
            models.CheckConstraint(
                condition=Q(monto_calculado__gte=0),
                name="ventas_comision_monto_no_negativo",
            ),
        ]

    def __str__(self):
        return f"Comisión de captación {self.captacion_id}"


class LiquidacionComisiones(models.Model):
    """Borrador inerte que agrupa comisiones de un solo captador."""

    ESTADO_BORRADOR = "borrador"
    ESTADO_CANCELADA = "cancelada"
    ESTADO_PAGADA = "pagada"
    ESTADO_CHOICES = [
        (ESTADO_BORRADOR, "Borrador"),
        (ESTADO_CANCELADA, "Cancelada"),
        (ESTADO_PAGADA, "Pagada"),
    ]

    METODO_EFECTIVO = "efectivo"
    METODO_TRANSFERENCIA = "transferencia"
    METODO_PAGO_CHOICES = [
        (METODO_EFECTIVO, "Efectivo"),
        (METODO_TRANSFERENCIA, "Transferencia"),
    ]

    captador = models.ForeignKey(
        Captador,
        on_delete=models.PROTECT,
        related_name="liquidaciones_comisiones",
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default=ESTADO_BORRADOR,
    )
    beneficiario_nombre_snapshot = models.CharField(max_length=200)
    creada_en = models.DateTimeField(auto_now_add=True)
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="liquidaciones_comisiones_creadas",
    )
    cancelada_en = models.DateTimeField(null=True, blank=True)
    cancelada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="liquidaciones_comisiones_canceladas",
    )
    motivo_cancelacion = models.TextField(blank=True)
    monto_total_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    metodo_pago = models.CharField(
        max_length=20,
        choices=METODO_PAGO_CHOICES,
        blank=True,
    )
    referencia = models.CharField(max_length=200, blank=True)
    pagada_en = models.DateTimeField(null=True, blank=True)
    pagada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="liquidaciones_comisiones_pagadas",
    )

    class Meta:
        ordering = ["-creada_en", "-id"]
        verbose_name = "Liquidación de comisiones"
        verbose_name_plural = "Liquidaciones de comisiones"
        permissions = [
            ("view_liquidaciones", "Puede consultar liquidaciones"),
            ("create_liquidacion", "Puede crear liquidaciones"),
            (
                "change_draft_liquidacion",
                "Puede modificar borradores de liquidación",
            ),
            (
                "cancel_draft_liquidacion",
                "Puede cancelar borradores de liquidación",
            ),
            ("pay_liquidacion", "Puede registrar pagos de liquidaciones"),
        ]
        indexes = [
            models.Index(
                fields=["captador", "estado"],
                name="ventas_liq_capt_estado_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Liquidación {self.pk or 'nueva'} — "
            f"{self.beneficiario_nombre_snapshot}"
        )

    def clean(self):
        super().clean()
        tiene_datos_cancelacion = bool(
            self.cancelada_en
            or self.cancelada_por_id
            or self.motivo_cancelacion
        )
        if self.estado == self.ESTADO_BORRADOR and tiene_datos_cancelacion:
            raise ValidationError(
                "Un borrador activo no puede contener datos de cancelación."
            )
        if self.estado == self.ESTADO_CANCELADA:
            if not self.cancelada_en or not self.motivo_cancelacion.strip():
                raise ValidationError(
                    "Una liquidación cancelada requiere fecha y motivo."
                )
        tiene_datos_pago = bool(
            self.monto_total_snapshot is not None
            or self.metodo_pago
            or self.referencia
            or self.pagada_en
            or self.pagada_por_id
        )
        if self.estado != self.ESTADO_PAGADA and tiene_datos_pago:
            raise ValidationError(
                "Sólo una liquidación pagada puede contener evidencia de pago."
            )
        if self.estado == self.ESTADO_PAGADA:
            if tiene_datos_cancelacion:
                raise ValidationError(
                    "Una liquidación pagada no puede estar cancelada."
                )
            if (
                self.monto_total_snapshot is None
                or not self.metodo_pago
                or not self.referencia.strip()
                or not self.pagada_en
            ):
                raise ValidationError(
                    "Una liquidación pagada requiere evidencia completa."
                )


class LineaLiquidacionComision(models.Model):
    """Asociación histórica entre un borrador y una comisión."""

    liquidacion = models.ForeignKey(
        LiquidacionComisiones,
        on_delete=models.PROTECT,
        related_name="lineas",
    )
    comision = models.ForeignKey(
        ComisionCaptacion,
        on_delete=models.PROTECT,
        related_name="lineas_liquidacion",
    )
    activa = models.BooleanField(default=True)
    agregada_en = models.DateTimeField(auto_now_add=True)
    agregada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lineas_liquidacion_agregadas",
    )
    retirada_en = models.DateTimeField(null=True, blank=True)
    retirada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lineas_liquidacion_retiradas",
    )
    motivo_retiro = models.TextField(blank=True)
    monto_liquidado_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["liquidacion_id", "agregada_en", "id"]
        verbose_name = "Línea de liquidación de comisión"
        verbose_name_plural = "Líneas de liquidación de comisiones"
        constraints = [
            models.UniqueConstraint(
                fields=["comision"],
                condition=Q(activa=True),
                name="ventas_una_linea_activa_comision",
            ),
        ]
        indexes = [
            models.Index(
                fields=["liquidacion", "activa"],
                name="ventas_linea_liq_activa_idx",
            ),
            models.Index(
                fields=["comision", "activa"],
                name="ventas_linea_com_activa_idx",
            ),
        ]

    def clean(self):
        super().clean()
        if self.activa:
            if self.retirada_en or self.retirada_por_id or self.motivo_retiro:
                raise ValidationError(
                    "Una línea activa no puede contener datos de retiro."
                )
        elif not self.retirada_en or not self.motivo_retiro.strip():
            raise ValidationError(
                "Una línea retirada requiere fecha y motivo de retiro."
            )

        if not self.liquidacion_id or not self.comision_id:
            return

        if self.liquidacion.estado == LiquidacionComisiones.ESTADO_PAGADA:
            if not self.activa or self.monto_liquidado_snapshot is None:
                raise ValidationError(
                    "Las líneas de una liquidación pagada deben permanecer "
                    "activas y tener monto congelado."
                )
        elif self.monto_liquidado_snapshot is not None:
            raise ValidationError(
                "Sólo las líneas pagadas pueden tener monto congelado."
            )

        captador_liquidacion_id = self.liquidacion.captador_id
        captador_comision_id = self.comision.captacion.captador_id
        if captador_liquidacion_id != captador_comision_id:
            raise ValidationError(
                {
                    "comision": (
                        "La comisión debe pertenecer al mismo captador "
                        "que la liquidación."
                    )
                }
            )

        if self.comision.estado == ComisionCaptacion.ESTADO_SUSPENDIDA:
            raise ValidationError(
                {"comision": "Una comisión suspendida no puede liquidarse."}
            )

        # Fase 7C deberá ejecutar esta validación dentro de una operación
        # transaccional que reserve las comisiones seleccionadas.

    def __str__(self):
        return f"Línea {self.pk or 'nueva'} de liquidación {self.liquidacion_id}"


class EventoLiquidacion(models.Model):
    """Registro inerte para la futura auditoría de liquidaciones."""

    ACCION_LIQUIDACION_CREADA = "liquidacion_creada"
    ACCION_COMISION_AGREGADA = "comision_agregada"
    ACCION_COMISION_RETIRADA = "comision_retirada"
    ACCION_BORRADOR_CANCELADO = "borrador_cancelado"
    ACCION_LIQUIDACION_PAGADA = "liquidacion_pagada"
    ACCION_CHOICES = [
        (ACCION_LIQUIDACION_CREADA, "Liquidación creada"),
        (ACCION_COMISION_AGREGADA, "Comisión agregada"),
        (ACCION_COMISION_RETIRADA, "Comisión retirada"),
        (ACCION_BORRADOR_CANCELADO, "Borrador cancelado"),
        (ACCION_LIQUIDACION_PAGADA, "Liquidación pagada"),
    ]

    liquidacion = models.ForeignKey(
        LiquidacionComisiones,
        on_delete=models.PROTECT,
        related_name="eventos",
    )
    accion = models.CharField(max_length=30, choices=ACCION_CHOICES)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eventos_liquidacion",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    detalle = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-creado_en", "-id"]
        verbose_name = "Evento de liquidación"
        verbose_name_plural = "Eventos de liquidación"
        indexes = [
            models.Index(
                fields=["liquidacion", "creado_en"],
                name="ventas_evento_liq_fecha_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Liquidación {self.liquidacion_id} — "
            f"{self.get_accion_display()}"
        )
