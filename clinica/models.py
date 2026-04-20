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


class Empresa(models.Model):
    usuario = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='perfil_empresa'
    )
    nombre = models.CharField(max_length=200)
    activo = models.BooleanField(default=True)
    division = models.ForeignKey(
        'Division', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='empresas'
    )

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"


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


class NotaTerapeutaPaciente(models.Model):
    terapeuta = models.ForeignKey(
        'Terapeuta',
        on_delete=models.CASCADE,
        related_name='notas_pacientes',
    )
    paciente = models.ForeignKey(
        'Paciente',
        on_delete=models.CASCADE,
        related_name='notas_terapeutas',
    )
    notas = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    @property
    def autor_display(self):
        return self.terapeuta.nombre if self.terapeuta_id else 'Sin terapeuta'

    def __str__(self):
        return f"Nota de {self.terapeuta} para {self.paciente} ({self.creado_en:%d/%m/%Y %H:%M})"

    class Meta:
        verbose_name = "Nota de Terapeuta por Paciente"
        verbose_name_plural = "Notas de Terapeutas por Paciente"
        ordering = ['-creado_en']


class DocumentoPaciente(models.Model):
    TIPO_CHOICES = [
        ('consentimiento', 'Consentimiento'),
        ('estudio', 'Estudio socioeconomico'),
        ('apertura', 'Apertura de expediente'),
        ('resultado', 'Resultado'),
        ('otro', 'Otro'),
    ]

    paciente = models.ForeignKey(
        'Paciente',
        on_delete=models.CASCADE,
        related_name='documentos_subidos',
    )
    terapeuta = models.ForeignKey(
        'Terapeuta',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documentos_pacientes_subidos',
    )
    subido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documentos_pacientes_subidos',
    )
    tipo_documento = models.CharField(max_length=20, choices=TIPO_CHOICES, default='otro')
    nombre_archivo = models.CharField(max_length=255, blank=True)
    tipo_mime = models.CharField(max_length=100, blank=True)
    contenido = models.BinaryField(blank=True)
    descripcion = models.CharField(max_length=255, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    @property
    def autor_display(self):
        if self.terapeuta_id:
            return self.terapeuta.nombre
        if self.subido_por_id:
            nombre = self.subido_por.get_full_name().strip()
            return nombre or self.subido_por.username
        return 'Usuario no identificado'

    def __str__(self):
        return f"{self.paciente} | {self.get_tipo_documento_display()} | {self.creado_en:%d/%m/%Y %H:%M}"

    class Meta:
        verbose_name = "Documento de Paciente"
        verbose_name_plural = "Documentos de Pacientes"
        ordering = ['-creado_en']

class Consultorio(models.Model):
    SEDE_CHOICES = [
        ('republica',      'República'),
        ('morelos',        'Morelos'),
        ('colinas',        'Colinas'),
        ('trabajo_social', 'Trabajo Social'),
        ('zoom',           'Zoom / Online'),
        ('externo',        'Externo'),
    ]

    nombre = models.CharField(max_length=100)
    sede   = models.CharField(max_length=20, choices=SEDE_CHOICES, null=True, blank=True)

    def __str__(self):
        return self.nombre

class Division(models.Model):
    nombre = models.CharField(max_length=100)
    
    def __str__(self):
        return self.nombre

class Servicio(models.Model):
    nombre = models.CharField(max_length=100)
    precio = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Precio estándar",
        help_text="Precio público del servicio. Se usa para calcular penalizaciones por inasistencia."
    )

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
    
    # Empresa que dio de alta a este paciente (opcional)
    empresa = models.ForeignKey(
        'Empresa', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pacientes'
    )

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


class PacienteTerapeutaAcceso(models.Model):
    terapeuta = models.ForeignKey(
        'Terapeuta',
        on_delete=models.CASCADE,
        related_name='pacientes_vinculados',
    )
    paciente = models.ForeignKey(
        'Paciente',
        on_delete=models.CASCADE,
        related_name='terapeutas_vinculados',
    )
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vinculos_terapeuta_paciente_creados',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.terapeuta} <-> {self.paciente}"

    class Meta:
        verbose_name = "Vinculo Terapeuta Paciente"
        verbose_name_plural = "Vinculos Terapeuta Paciente"
        unique_together = [('terapeuta', 'paciente')]
        ordering = ['-creado_en']


class AccesoDirectoPortal(models.Model):
    CLAVE_MANUAL_PORTAL_MEDICO = 'manual_portal_medico'

    CLAVE_CHOICES = [
        (CLAVE_MANUAL_PORTAL_MEDICO, 'Manual del sistema para portal medico'),
    ]

    clave = models.CharField(max_length=50, choices=CLAVE_CHOICES, unique=True)
    titulo = models.CharField(max_length=120, default='Manual del sistema')
    nombre_archivo = models.CharField(max_length=255, blank=True)
    tipo_mime = models.CharField(max_length=100, blank=True)
    contenido = models.BinaryField(blank=True)
    activo = models.BooleanField(default=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.get_clave_display()

    @property
    def tiene_archivo(self):
        return bool(self.contenido and self.nombre_archivo)

    class Meta:
        verbose_name = "Acceso directo"
        verbose_name_plural = "Accesos directos"


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
    tiene_descuento = models.BooleanField(
        null=True, blank=True,
        help_text="Indica si el paciente tiene descuento / estudio socioeconómico activo al momento de la cita."
    )

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

    SEDE_CHOICES = [
        ('republica',      'República'),
        ('morelos',        'Morelos'),
        ('colinas',        'Colinas'),
        ('trabajo_social', 'Trabajo Social'),
        ('zoom',           'Zoom / Online'),
        ('externo',        'Externo'),
    ]

    terapeuta   = models.ForeignKey('Terapeuta', on_delete=models.CASCADE)
    dia         = models.IntegerField(choices=DIAS_SEMANA)
    hora_inicio = models.TimeField()
    hora_fin    = models.TimeField()
    sede        = models.CharField(max_length=20, choices=SEDE_CHOICES, null=True, blank=True)

    def __str__(self):
        sede_label = dict(self.SEDE_CHOICES).get(self.sede, '') if self.sede else ''
        sede_str = f' @ {sede_label}' if sede_label else ''
        return f"{self.terapeuta} - {self.get_dia_display()} ({self.hora_inicio} - {self.hora_fin}){sede_str}"
    

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
    consultorio = models.ForeignKey('Consultorio', on_delete=models.SET_NULL, null=True, blank=True)
    notas_paciente = models.TextField(blank=True, null=True, help_text="Mensaje original del paciente")

    # Campos para solicitudes desde portal empresa
    paciente  = models.ForeignKey('Paciente', on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes')
    empresa   = models.ForeignKey('Empresa', on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes')
    division  = models.ForeignKey('Division', on_delete=models.SET_NULL, null=True, blank=True)
    servicio  = models.ForeignKey('Servicio', on_delete=models.SET_NULL, null=True, blank=True)

    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    motivo_rechazo = models.TextField(blank=True, null=True, help_text="Razón enviada al paciente si se rechaza")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.paciente_nombre} - {self.fecha_deseada} ({self.get_estado_display()})"


class SolicitudReagendo(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('aprobada', 'Aprobada'),
        ('rechazada', 'Rechazada'),
    ]

    cita = models.ForeignKey(
        'Cita',
        on_delete=models.CASCADE,
        related_name='solicitudes_reagendo',
    )
    terapeuta = models.ForeignKey(
        'Terapeuta',
        on_delete=models.CASCADE,
        related_name='solicitudes_reagendo',
    )
    fecha_propuesta = models.DateField()
    hora_propuesta = models.TimeField()
    motivo = models.TextField(blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    nota_recepcion = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reagendo de {self.terapeuta} para cita {self.cita_id} — {self.get_estado_display()}"

    class Meta:
        verbose_name = "Solicitud de Reagendo"
        verbose_name_plural = "Solicitudes de Reagendo"
        ordering = ['-creado_en']


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
    TIPO_PENALIZACION = 'penalizacion'

    TIPO_CHOICES = [
        (TIPO_SESION, 'Sesión'),
        (TIPO_BONO_UMBRAL, 'Bono por volumen'),
        (TIPO_BONO_POR_PACIENTE, 'Bono por paciente'),
        (TIPO_PENALIZACION, 'Penalización inasistencia'),
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


class ReporteSesion(models.Model):
    """
    Reporte clínico de una sesión, basado en el documento físico de INTRA.
    Los campos auto-calculados (fecha, terapeuta, paciente, # sesión) se
    pre-rellenan desde la BD; los campos de contenido los escribe el terapeuta.
    """
    paciente = models.ForeignKey(
        'Paciente',
        on_delete=models.CASCADE,
        related_name='reportes_sesion',
    )
    terapeuta = models.ForeignKey(
        'Terapeuta',
        on_delete=models.SET_NULL,
        null=True,
        related_name='reportes_sesion',
    )
    cita = models.ForeignKey(
        'Cita',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reporte_sesion',
    )
    fecha = models.DateField()
    numero_sesion = models.PositiveIntegerField(default=1, verbose_name='# De sesión')
    hora_inicio = models.TimeField(null=True, blank=True, verbose_name='Hora de inicio')
    hora_fin = models.TimeField(null=True, blank=True, verbose_name='Hora de finalización')

    objetivo_sesion = models.TextField(blank=True, verbose_name='Objetivo de la sesión')
    revision_tareas = models.TextField(blank=True, verbose_name='Revisión de tareas')
    desarrollo_sesion = models.TextField(blank=True, verbose_name='Desarrollo de sesión')
    tecnicas_utilizadas = models.TextField(blank=True, verbose_name='Técnicas utilizadas')
    resultados_sesion = models.TextField(blank=True, verbose_name='Resultados de la sesión')
    tareas = models.TextField(blank=True, verbose_name='Tareas')
    comentarios_finales = models.TextField(blank=True, verbose_name='Comentarios Finales')

    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Sesión #{self.numero_sesion} – {self.paciente} ({self.fecha:%d/%m/%Y})"

    class Meta:
        verbose_name = 'Reporte de Sesión'
        verbose_name_plural = 'Reportes de Sesión'
        ordering = ['-fecha', '-creado_en']


class AperturaExpediente(models.Model):
    """
    Formulario de apertura de expediente clínico (un solo registro por paciente).
    Al guardarse genera automáticamente un PDF que queda enlazado como DocumentoPaciente
    con tipo_documento='apertura'.
    """
    ESTADO_CIVIL_CHOICES = [
        ('', '---------'),
        ('soltero', 'Soltero(a)'),
        ('casado', 'Casado(a)'),
        ('divorciado', 'Divorciado(a)'),
        ('viudo', 'Viudo(a)'),
        ('union_libre', 'Unión libre'),
        ('otro', 'Otro'),
    ]

    paciente = models.OneToOneField(
        'Paciente',
        on_delete=models.CASCADE,
        related_name='apertura_expediente_obj',
    )
    documento = models.OneToOneField(
        'DocumentoPaciente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='apertura_origen',
    )

    expediente_no       = models.CharField(max_length=50, blank=True, verbose_name='Expediente No.')
    apellido_paterno    = models.CharField(max_length=100, verbose_name='Apellido Paterno')
    apellido_materno    = models.CharField(max_length=100, blank=True, verbose_name='Apellido Materno')
    ocupacion           = models.CharField(max_length=150, blank=True, verbose_name='Ocupación')
    lugar_de_trabajo    = models.CharField(max_length=200, blank=True, verbose_name='Lugar de Trabajo')
    cargo               = models.CharField(max_length=150, blank=True, verbose_name='Cargo que desempeña')
    estado_civil        = models.CharField(max_length=20, choices=ESTADO_CIVIL_CHOICES, blank=True, verbose_name='Estado Civil')
    calle               = models.CharField(max_length=200, blank=True, verbose_name='Calle')
    num_exterior        = models.CharField(max_length=20, blank=True, verbose_name='Núm.')
    colonia             = models.CharField(max_length=150, blank=True, verbose_name='Col.')
    division            = models.ForeignKey('Division', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='División')
    vive_con            = models.CharField(max_length=200, blank=True, verbose_name='Vive con')
    tiene_hijos         = models.BooleanField(default=False, verbose_name='Tiene hijos')
    num_hijos           = models.PositiveIntegerField(null=True, blank=True, verbose_name='No. de Hijos')
    hijo_1              = models.CharField(max_length=200, blank=True, verbose_name='Hijo 1')
    hijo_2              = models.CharField(max_length=200, blank=True, verbose_name='Hijo 2')
    hijo_3              = models.CharField(max_length=200, blank=True, verbose_name='Hijo 3')
    hijo_4              = models.CharField(max_length=200, blank=True, verbose_name='Hijo 4')
    religion            = models.CharField(max_length=100, blank=True, verbose_name='Religión')
    motivo_consulta     = models.TextField(blank=True, verbose_name='Motivo de consulta')
    emergencia_contacto = models.CharField(max_length=200, blank=True, verbose_name='En caso de emergencia llamar a')
    emergencia_telefono = models.CharField(max_length=30, blank=True, verbose_name='Teléfono de contacto de emergencia')
    como_se_entero      = models.CharField(max_length=200, blank=True, verbose_name='¿Cómo se enteró de nosotros?')

    creado_en      = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Apertura – {self.paciente}'

    class Meta:
        verbose_name = 'Apertura de Expediente'
        verbose_name_plural = 'Aperturas de Expediente'


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


class PenalizacionPaciente(models.Model):
    """
    Penalización por inasistencia. Se genera automáticamente cuando una cita
    se marca como 'no_asistio'. El monto es el 50% del precio estándar del servicio
    (o del costo registrado si el servicio no tiene precio configurado).
    Se cobra en la siguiente cita del paciente sumándose automáticamente al costo.
    """
    paciente = models.ForeignKey(
        'Paciente', on_delete=models.CASCADE, related_name='penalizaciones'
    )
    cita_origen = models.OneToOneField(
        'Cita', on_delete=models.CASCADE, related_name='penalizacion_generada',
        help_text="Cita de inasistencia que generó esta penalización."
    )
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    pagada = models.BooleanField(default=False)
    cita_cobro = models.ForeignKey(
        'Cita', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='penalizacion_cobrada',
        help_text="Cita en la que se cobró la penalización."
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        estado = "Pagada" if self.pagada else "Pendiente"
        return f"Penalización {estado} — {self.paciente} | ${self.monto} ({self.cita_origen.fecha})"

    class Meta:
        verbose_name = "Penalización por Inasistencia"
        verbose_name_plural = "Penalizaciones por Inasistencia"
        ordering = ['-fecha_creacion']


class ReporteIncidente(models.Model):
    TIPO_QUEJA = 'queja'
    TIPO_SUGERENCIA = 'sugerencia'
    TIPO_INCIDENTE = 'incidente'
    TIPO_CHOICES = [
        (TIPO_QUEJA, 'Queja'),
        (TIPO_SUGERENCIA, 'Sugerencia'),
        (TIPO_INCIDENTE, 'Incidente en consultorio'),
    ]

    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_REVISADO = 'revisado'
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_REVISADO, 'Revisado'),
    ]

    terapeuta = models.ForeignKey(
        Terapeuta, on_delete=models.CASCADE, related_name='reportes_incidente'
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.get_tipo_display()}] {self.titulo} — {self.terapeuta}"

    class Meta:
        verbose_name = "Reporte / Incidente"
        verbose_name_plural = "Reportes e Incidentes"
        ordering = ['-fecha_creacion']
