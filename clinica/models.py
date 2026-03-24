import unicodedata
from datetime import date
from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User

def quitar_tildes(texto):
    if not texto:
        return ""
   
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto))
                   if unicodedata.category(c) != 'Mn').lower()

class Terapeuta(models.Model):
    # El puente hacia el sistema de login de Django
    usuario = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='perfil_terapeuta')
    
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True) 

    def __str__(self):
        return self.nombre


class BloqueoAgendaTerapeuta(models.Model):
    TIPO_TEMPORAL = 'temporal'
    TIPO_PERMANENTE = 'permanente'
    ALCANCE_FECHA = 'fecha'
    ALCANCE_DIA_SEMANA = 'dia_semana'

    TIPO_CHOICES = [
        (TIPO_TEMPORAL, 'Temporal'),
        (TIPO_PERMANENTE, 'Permanente'),
    ]
    ALCANCE_CHOICES = [
        (ALCANCE_FECHA, 'Fecha específica'),
        (ALCANCE_DIA_SEMANA, 'Día semanal'),
    ]
    DIAS_SEMANA = [
        (0, 'Lunes'),
        (1, 'Martes'),
        (2, 'Miércoles'),
        (3, 'Jueves'),
        (4, 'Viernes'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]

    terapeuta = models.ForeignKey(
        'Terapeuta',
        on_delete=models.CASCADE,
        related_name='bloqueos_agenda',
    )
    tipo_bloqueo = models.CharField(max_length=20, choices=TIPO_CHOICES, default=TIPO_TEMPORAL)
    alcance = models.CharField(max_length=20, choices=ALCANCE_CHOICES, default=ALCANCE_FECHA)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    dia_semana = models.IntegerField(choices=DIAS_SEMANA, null=True, blank=True)
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fin = models.TimeField(null=True, blank=True)
    motivo = models.CharField(max_length=255, blank=True)
    activo = models.BooleanField(default=True)
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bloqueos_terapeutas_creados',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    def clean(self):
        errores = {}

        if self.fecha_inicio and self.fecha_inicio < date.today():
            errores['fecha_inicio'] = 'Solo puedes bloquear fechas actuales o futuras.'

        if self.alcance == self.ALCANCE_DIA_SEMANA and self.dia_semana is None:
            errores['dia_semana'] = 'Selecciona el día semanal a bloquear.'

        if self.alcance == self.ALCANCE_FECHA:
            self.dia_semana = None

        if self.tipo_bloqueo == self.TIPO_TEMPORAL:
            if not self.fecha_fin:
                errores['fecha_fin'] = 'Indica la fecha final del bloqueo temporal.'
            elif self.fecha_fin < self.fecha_inicio:
                errores['fecha_fin'] = 'La fecha final no puede ser anterior a la inicial.'
        else:
            self.fecha_fin = None

        if self.hora_inicio or self.hora_fin:
            if not self.hora_inicio or not self.hora_fin:
                errores['hora_fin'] = 'Indica hora de inicio y hora final para un bloqueo parcial.'
            elif self.hora_fin <= self.hora_inicio:
                errores['hora_fin'] = 'La hora final debe ser posterior a la inicial.'

        if errores:
            raise ValidationError(errores)

    def aplica_en_fecha(self, fecha_obj):
        if not self.activo or not fecha_obj or fecha_obj < self.fecha_inicio:
            return False
        if self.alcance == self.ALCANCE_DIA_SEMANA and fecha_obj.weekday() != self.dia_semana:
            return False
        if self.tipo_bloqueo == self.TIPO_PERMANENTE:
            return True
        return bool(self.fecha_fin and self.fecha_inicio <= fecha_obj <= self.fecha_fin)

    def bloquea_fecha_hora(self, fecha_obj, hora_obj=None):
        if not self.aplica_en_fecha(fecha_obj):
            return False
        if self.hora_inicio and self.hora_fin and hora_obj:
            return self.hora_inicio <= hora_obj < self.hora_fin
        return True

    def es_bloqueo_parcial(self):
        return bool(self.hora_inicio and self.hora_fin)

    def alcance_display(self):
        if self.alcance == self.ALCANCE_DIA_SEMANA and self.dia_semana is not None:
            return self.get_dia_semana_display()
        return 'Fecha específica'

    def rango_display(self):
        sufijo_hora = ''
        if self.es_bloqueo_parcial():
            sufijo_hora = f" | {self.hora_inicio:%H:%M} a {self.hora_fin:%H:%M}"

        if self.alcance == self.ALCANCE_DIA_SEMANA and self.dia_semana is not None:
            dia = self.get_dia_semana_display()
            if self.tipo_bloqueo == self.TIPO_PERMANENTE:
                return f"Todos los {dia.lower()} desde {self.fecha_inicio:%d/%m/%Y}{sufijo_hora}"
            if self.fecha_fin:
                return f"Todos los {dia.lower()} del {self.fecha_inicio:%d/%m/%Y} al {self.fecha_fin:%d/%m/%Y}{sufijo_hora}"
            return f"Todos los {dia.lower()} desde {self.fecha_inicio:%d/%m/%Y}{sufijo_hora}"

        if self.tipo_bloqueo == self.TIPO_PERMANENTE:
            return f"Desde {self.fecha_inicio:%d/%m/%Y} en adelante{sufijo_hora}"
        if self.fecha_fin:
            return f"Del {self.fecha_inicio:%d/%m/%Y} al {self.fecha_fin:%d/%m/%Y}{sufijo_hora}"
        return f"Desde {self.fecha_inicio:%d/%m/%Y}{sufijo_hora}"

    def mensaje_bloqueo(self):
        base = f"El terapeuta bloqueó esta disponibilidad ({self.rango_display()})."
        if self.motivo:
            return f"{base} Motivo: {self.motivo}"
        return base

    def __str__(self):
        return f"{self.terapeuta} | {self.get_tipo_bloqueo_display()} | {self.rango_display()}"

    class Meta:
        verbose_name = "Bloqueo de Agenda del Terapeuta"
        verbose_name_plural = "Bloqueos de Agenda de Terapeutas"
        ordering = ['fecha_inicio', '-creado_en']

class Consultorio(models.Model):
    nombre = models.CharField(max_length=100)
    
    def __str__(self):
        return self.nombre

class Division(models.Model):
    nombre = models.CharField(max_length=100)
    
    def __str__(self):
        return self.nombre

class Servicio(models.Model):
    nombre = models.CharField(max_length=100)
    
    def __str__(self):
        return self.nombre



class Paciente(models.Model):
    TIPO_CONTACTO_CHOICES = [
        ('propio', 'Propio'),
        ('madre', 'Madre'),
        ('padre', 'Padre'),
        ('pareja', 'Pareja'),
        ('otro', 'Otro'),
    ]

    SEXO_CHOICES = [
        ('Femenino', 'Femenino'),
        ('Masculino', 'Masculino'),
    ]

    # Datos Generales
    usuario = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='perfil_paciente')
    nombre = models.CharField(max_length=200, verbose_name="Nombre Completo")
    fecha_nacimiento = models.DateField(verbose_name="Fecha de Nacimiento")
    
    # EL CAMPO SECRETO
    nombre_normalizado = models.CharField(max_length=200, blank=True, editable=False)
    
    sexo = models.CharField(
        max_length=20, 
        choices=SEXO_CHOICES, 
        default='Femenino',
        verbose_name="Sexo"
    )

    telefono = models.CharField(max_length=20, verbose_name="Teléfono (WhatsApp)")
    identidad_contacto = models.CharField(max_length=20, choices=TIPO_CONTACTO_CHOICES, default='propio')
    
    # Ojo: Asegúrate de tener el modelo Servicio importado o definido antes si usas esto, 
    # si no, pon 'Servicio' entre comillas como string.
    servicio_inicial = models.ForeignKey('Servicio', on_delete=models.SET_NULL, null=True, verbose_name="Servicio Inicial")

    # Documentación
    consentimiento_firmado = models.FileField(upload_to='documentos/', blank=True, null=True)
    estudio_socioeconomico = models.FileField(upload_to='documentos/', blank=True, null=True)
    apertura_expediente = models.FileField(upload_to='documentos/', blank=True, null=True)
    resumen_clinico = models.TextField(blank=True, null=True)
    
    # Relaciones
    pacientes_relacionados = models.ManyToManyField('self', blank=True, symmetrical=True)
    enlace_resultados = models.URLField(blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    
    # --- LA MAGIA (INDENTACIÓN CORRECTA) ---
    def save(self, *args, **kwargs):
        # Antes de guardar, llenamos el campo normalizado automáticamente
        self.nombre_normalizado = quitar_tildes(self.nombre)
        super(Paciente, self).save(*args, **kwargs)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Paciente"
        verbose_name_plural = "Pacientes"


class Cita(models.Model):
    ESTATUS_CONFIRMADA = 'confirmada'
    ESTATUS_SIN_CONFIRMAR = 'sin_confirmar'
    ESTATUS_REAGENDO = 'reagendo'
    ESTATUS_CANCELO = 'cancelo'
    ESTATUS_SI_ASISTIO = 'si_asistio'
    ESTATUS_NO_ASISTIO = 'no_asistio'
    ESTATUS_INCIDENCIA = 'incidencia'

    ESTATUS_CHOICES = [
        (ESTATUS_CONFIRMADA, 'Confirmada'),
        (ESTATUS_SIN_CONFIRMAR, 'Sin confirmar'),
        (ESTATUS_REAGENDO, 'Reagendo'),
        (ESTATUS_CANCELO, 'Cancelo'),
        (ESTATUS_SI_ASISTIO, 'Si asistio'),
        (ESTATUS_NO_ASISTIO, 'No asistio'),
        (ESTATUS_INCIDENCIA, 'Incidencia'),
    ]

    ESTATUS_ACTIVOS = (
        ESTATUS_CONFIRMADA,
        ESTATUS_SIN_CONFIRMAR,
        ESTATUS_REAGENDO,
        ESTATUS_INCIDENCIA,
    )

    TIPO_NUEVO = 'N'
    TIPO_REFERIDO = 'R'
    TIPO_SEGUIMIENTO = 'S'

    TIPO_PACIENTE_CHOICES = [
        (TIPO_NUEVO, 'Nuevo'),
        (TIPO_REFERIDO, 'Referido'),
        (TIPO_SEGUIMIENTO, 'Seguimiento'),
    ]

    PAGO_CHOICES = [
        ('Terminal', 'Terminal'),
        ('Transferencia', 'Transferencia'),
        ('Efectivo', 'Efectivo'),
        ('Pase', 'Pase'),
    ]

    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='citas')
    pacientes_adicionales = models.ManyToManyField(
        Paciente,
        blank=True,
        related_name='citas_como_adicional',
    )
    fecha = models.DateField()
    hora = models.TimeField()
    tipo_paciente = models.CharField(
        max_length=1,
        choices=TIPO_PACIENTE_CHOICES,
        default=TIPO_SEGUIMIENTO,
    )
    
 
    division = models.ForeignKey(Division, on_delete=models.SET_NULL, null=True)
    consultorio = models.ForeignKey(Consultorio, on_delete=models.SET_NULL, null=True)
    servicio = models.ForeignKey(Servicio, on_delete=models.SET_NULL, null=True)
    terapeuta = models.ForeignKey(Terapeuta, on_delete=models.SET_NULL, null=True)
    
    costo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    metodo_pago = models.CharField(
        max_length=50,
        choices=PAGO_CHOICES,
        null=True,
        blank=True,
    )
    estatus = models.CharField(
        max_length=20,
        choices=ESTATUS_CHOICES,
        default=ESTATUS_SIN_CONFIRMAR,
    )
    
    folio_fiscal = models.CharField(max_length=100, blank=True, null=True)
    notas = models.TextField(blank=True, null=True)

    @property
    def es_finalizable(self):
        """True si la cita puede ser cerrada por el terapeuta (aún no tiene resultado final)."""
        return self.estatus in (
            self.ESTATUS_SIN_CONFIRMAR,
            self.ESTATUS_CONFIRMADA,
            self.ESTATUS_REAGENDO,
            self.ESTATUS_INCIDENCIA,
        )

    def pacientes_display(self):
        nombres = [self.paciente.nombre] if self.paciente_id else []
        nombres.extend(self.pacientes_adicionales.values_list('nombre', flat=True))
        return ", ".join(nombres)

    def pacientes_display_natural(self):
        nombres = [self.paciente.nombre] if self.paciente_id else []
        nombres.extend(list(self.pacientes_adicionales.values_list('nombre', flat=True)))
        if not nombres:
            return ""
        if len(nombres) == 1:
            return nombres[0]
        if len(nombres) == 2:
            return f"{nombres[0]} y {nombres[1]}"
        return f"{', '.join(nombres[:-1])} y {nombres[-1]}"

    def titulo_cita(self):
        pacientes = self.pacientes_display_natural()
        return f"Cita de {pacientes}" if pacientes else "Cita"

    def __str__(self):
        return f"{self.pacientes_display()} - {self.fecha}"

    class Meta:
        verbose_name = "Cita"
        verbose_name_plural = "Citas"
        ordering = ['-fecha', '-hora']

    # En clinica/models.py

class Horario(models.Model):
    DIAS_SEMANA = [
        (0, 'Lunes'),
        (1, 'Martes'),
        (2, 'Miércoles'),
        (3, 'Jueves'),
        (4, 'Viernes'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]

    terapeuta = models.ForeignKey('Terapeuta', on_delete=models.CASCADE)
    dia = models.IntegerField(choices=DIAS_SEMANA)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    
    # Opcional: Si un terapeuta solo trabaja en cierta sede en ese horario
    # consultorio = models.ForeignKey('Consultorio', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.terapeuta} - {self.get_dia_display()} ({self.hora_inicio} - {self.hora_fin})"
    

class SolicitudCita(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('aceptada', 'Aceptada'),
        ('rechazada', 'Rechazada'),
    ]

    paciente_nombre = models.CharField(max_length=150)
    telefono = models.CharField(max_length=20)

    fecha_deseada = models.DateField()
    hora_deseada = models.TimeField(null=True, blank=True)
    terapeuta = models.ForeignKey('Terapeuta', on_delete=models.SET_NULL, null=True, blank=True)
    notas_paciente = models.TextField(blank=True, null=True, help_text="Mensaje original del paciente")

    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    motivo_rechazo = models.TextField(blank=True, null=True, help_text="Razón enviada al paciente si se rechaza")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.paciente_nombre} - {self.fecha_deseada} ({self.get_estado_display()})"


# =============================================================================
# MÓDULO DE NÓMINA — Sprint 1
# =============================================================================

class TabuladorGeneral(models.Model):
    """
    Categorías base del tabulador (perfiles 0–11).
    Se aplica a terapeutas que NO tienen una ReglaTerapeuta individual definida,
    o se usa como referencia categórica en la ReglaTerapeuta.
    """
    numero = models.IntegerField(unique=True, help_text="Número de categoría (0 al 11).")
    descripcion = models.TextField(help_text="Perfil de formación que corresponde a esta categoría.")
    pago_base = models.DecimalField(max_digits=8, decimal_places=2,
                                    help_text="Monto fijo por sesión en consultorio INTRA.")
    pago_consultorio_propio = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Monto alternativo si la sesión es en consultorio del terapeuta (cats. 6 y 11)."
    )
    # Bono por volumen semanal (ej: $400 por cada 5 pacientes)
    bono_monto = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                     help_text="Monto del bono al alcanzar el umbral de pacientes.")
    bono_umbral_pacientes = models.IntegerField(
        null=True, blank=True,
        help_text="Número de pacientes semanales necesarios para activar el bono (repetible)."
    )

    def __str__(self):
        return f"Categoría {self.numero} — ${self.pago_base}"

    class Meta:
        verbose_name = "Tabulador General"
        verbose_name_plural = "Tabulador General"
        ordering = ['numero']


class ReglaTerapeuta(models.Model):
    """
    Reglas individuales de pago por terapeuta.
    Cuando existen, sus valores REEMPLAZAN al TabuladorGeneral para ese terapeuta.

    Lógica de resolución de pago por sesión (en orden de prioridad):
      1. Si la cita es de pareja/familiar y pago_pareja no es nulo → pago_pareja
      2. Si pago_individual no es nulo → pago_individual
      3. Si pago_por_sesion no es nulo → pago_por_sesion
      4. Fallback → tabulador_base.pago_base
    """
    terapeuta = models.OneToOneField(
        'Terapeuta', on_delete=models.CASCADE, related_name='regla_pago'
    )
    tabulador_base = models.ForeignKey(
        TabuladorGeneral, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Categoría del tabulador general como referencia. Opcional si se usan montos individualizados."
    )

    # --- Pagos por sesión ---
    pago_por_sesion = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Monto único para cualquier tipo de sesión. Usar cuando el terapeuta cobra igual sin importar modalidad."
    )
    pago_individual = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Pago para sesiones individuales cuando hay tarifa diferenciada por modalidad."
    )
    pago_pareja = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Pago para sesiones de pareja o familiar cuando hay tarifa diferenciada."
    )
    pago_consultorio_propio = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Monto cuando la cita se realiza en el consultorio propio del terapeuta (médicos)."
    )

    # --- Bono por volumen (umbral, repetible) ---
    # Ej: $100 por cada 5 pacientes → si atiende 10 cobra 2 × $100
    bono_umbral_monto = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Monto del bono que se paga por cada vez que se alcanza el umbral de pacientes."
    )
    bono_umbral_pacientes = models.IntegerField(
        null=True, blank=True,
        help_text="Cantidad de pacientes para activar el bono de volumen (ej: 5 → bono por cada 5 pacientes)."
    )

    # --- Bono por paciente individual (tipo supervisor) ---
    # Ej: +$25 adicionales por CADA paciente atendido en el periodo
    bono_por_paciente = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Bono fijo adicional por cada paciente atendido en el corte (ej: bono supervisor de $25/paciente)."
    )

    notas = models.TextField(
        blank=True,
        help_text="Observaciones operativas (ej: 'reportar hora extra en evaluaciones')."
    )

    def __str__(self):
        return f"Regla de pago — {self.terapeuta}"

    class Meta:
        verbose_name = "Regla de Pago (Terapeuta)"
        verbose_name_plural = "Reglas de Pago (Terapeutas)"


class CorteSemanal(models.Model):
    """
    Nómina semanal de un terapeuta. Agrupa todas las citas con estatus si_asistio
    de lunes a domingo para calcular el pago total del periodo.

    El cálculo se ejecuta desde clinica/services.py y almacena un snapshot
    de los montos en este modelo (no se recalcula en cada acceso).
    """
    ESTATUS_BORRADOR = 'borrador'
    ESTATUS_APROBADO = 'aprobado'
    ESTATUS_PAGADO = 'pagado'

    ESTATUS_CHOICES = [
        (ESTATUS_BORRADOR, 'Borrador'),
        (ESTATUS_APROBADO, 'Aprobado'),
        (ESTATUS_PAGADO, 'Pagado'),
    ]

    terapeuta = models.ForeignKey(
        'Terapeuta', on_delete=models.PROTECT, related_name='cortes_semanales'
    )
    fecha_inicio = models.DateField(help_text="Lunes de la semana del corte.")
    fecha_fin = models.DateField(help_text="Domingo de la semana del corte.")

    # Totales calculados — snapshot generado por el motor de cálculo
    total_sesiones = models.IntegerField(default=0)
    subtotal_sesiones = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                            help_text="Suma de pagos por sesión (sin bonos).")
    total_bonos = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                      help_text="Suma de todos los bonos del periodo.")
    total_pago = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                     help_text="Total a pagar: subtotal_sesiones + total_bonos.")

    estatus = models.CharField(max_length=20, choices=ESTATUS_CHOICES, default=ESTATUS_BORRADOR)
    aprobado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cortes_aprobados'
    )
    aprobado_en = models.DateTimeField(null=True, blank=True)

    notas = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.terapeuta} | {self.fecha_inicio} al {self.fecha_fin}"

    class Meta:
        verbose_name = "Corte Semanal"
        verbose_name_plural = "Cortes Semanales"
        unique_together = [('terapeuta', 'fecha_inicio')]
        ordering = ['-fecha_inicio', 'terapeuta']


class LineaNomina(models.Model):
    """
    Detalle línea por línea de un CorteSemanal. Sirve como audit trail del cálculo.
    Hay una línea por cita (tipo='sesion') y líneas adicionales para cada bono aplicado.
    """
    TIPO_SESION = 'sesion'
    TIPO_BONO_UMBRAL = 'bono_umbral'
    TIPO_BONO_POR_PACIENTE = 'bono_por_paciente'

    TIPO_CHOICES = [
        (TIPO_SESION, 'Sesión'),
        (TIPO_BONO_UMBRAL, 'Bono por volumen'),
        (TIPO_BONO_POR_PACIENTE, 'Bono por paciente'),
    ]

    corte = models.ForeignKey(CorteSemanal, on_delete=models.CASCADE, related_name='lineas')
    cita = models.ForeignKey(
        'Cita', on_delete=models.PROTECT, null=True, blank=True,
        help_text="Nulo únicamente en líneas de bono global (bono de volumen)."
    )
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, default=TIPO_SESION)
    concepto = models.CharField(max_length=200, help_text="Descripción legible del concepto calculado.")
    monto = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self):
        return f"{self.corte} | {self.concepto}: ${self.monto}"

    class Meta:
        verbose_name = "Línea de Nómina"
        verbose_name_plural = "Líneas de Nómina"


class BonoExtra(models.Model):
    """
    Pagos manuales esporádicos ligados a un CorteSemanal.
    Usados para conceptos que no encajan en las reglas automáticas del tabulador,
    como horas adicionales de elaboración de informes de evaluación.
    Se suman al total_pago del CorteSemanal al momento de aprobarlo.
    """
    corte = models.ForeignKey(CorteSemanal, on_delete=models.CASCADE, related_name='bonos_extra')
    cita = models.ForeignKey(
        'Cita', on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Cita relacionada al bono, si aplica (ej. la evaluación que generó la hora extra)."
    )
    concepto = models.CharField(max_length=200, help_text="Descripción del pago manual (ej. 'Hora de elaboración de informe — evaluación neuropsicológica').")
    monto = models.DecimalField(max_digits=8, decimal_places=2)
    registrado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bonos_extra_registrados',
        help_text="Staff o admin que autorizó este pago."
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.corte} | {self.concepto}: ${self.monto}"

    class Meta:
        verbose_name = "Bono Extra"
        verbose_name_plural = "Bonos Extra"


def obtener_bloqueos_terapeuta_en_fecha(terapeuta_id, fecha_obj):
    if not terapeuta_id or not fecha_obj:
        return BloqueoAgendaTerapeuta.objects.none()

    return (
        BloqueoAgendaTerapeuta.objects.filter(
            terapeuta_id=terapeuta_id,
            activo=True,
            fecha_inicio__lte=fecha_obj,
        )
        .filter(
            models.Q(tipo_bloqueo=BloqueoAgendaTerapeuta.TIPO_PERMANENTE) |
            models.Q(
                tipo_bloqueo=BloqueoAgendaTerapeuta.TIPO_TEMPORAL,
                fecha_fin__gte=fecha_obj,
            )
        )
        .order_by('alcance', 'dia_semana', 'hora_inicio', 'fecha_inicio')
    )


def obtener_bloqueo_terapeuta_en_fecha(terapeuta_id, fecha_obj, hora_obj=None):
    for bloqueo in obtener_bloqueos_terapeuta_en_fecha(terapeuta_id, fecha_obj):
        if bloqueo.bloquea_fecha_hora(fecha_obj, hora_obj):
            return bloqueo
    return None
