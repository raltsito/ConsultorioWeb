import unicodedata
import uuid
from datetime import date, datetime
from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

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


class PerfilCatalogo(models.Model):
    TITULO_CHOICES = [('Licenciatura', 'Licenciatura'), ('Maestría', 'Maestría')]

    terapeuta   = models.OneToOneField(
        'Terapeuta', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='perfil_catalogo'
    )
    nombre      = models.CharField(max_length=200)
    titulo      = models.CharField(max_length=20, choices=TITULO_CHOICES, default='Licenciatura')
    cedula      = models.CharField(max_length=200, blank=True, default='Sin cédula registrada')
    preparacion = models.TextField(blank=True)
    formacion   = models.TextField(blank=True)
    activo      = models.BooleanField(default=True)

    class Meta:
        verbose_name        = 'Perfil Catálogo'
        verbose_name_plural = 'Perfiles Catálogo'
        ordering            = ['nombre']

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


class Host(models.Model):
    usuario = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='perfil_host'
    )
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Host"
        verbose_name_plural = "Hosts"


class Consultoria(models.Model):
    usuario = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='perfil_consultoria'
    )
    nombre = models.CharField(max_length=100)
    divisiones = models.ManyToManyField(
        'Division',
        blank=True,
        related_name='consultorias',
        help_text='Divisiones a las que esta consultoria tiene acceso.',
    )
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Consultoria"
        verbose_name_plural = "Consultorias"


class DireccionComercial(models.Model):
    usuario = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='perfil_direccion_comercial'
    )
    nombre = models.CharField(max_length=100)
    divisiones = models.ManyToManyField(
        'Division',
        blank=True,
        related_name='direcciones_comerciales',
        help_text='Divisiones a las que este perfil de dirección comercial tiene acceso.',
    )
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Dirección Comercial"
        verbose_name_plural = "Dirección Comercial"


class LiderOperacionesClinicas(models.Model):
    usuario = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='perfil_lider_operaciones_clinicas'
    )
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Líder de Operaciones Clínicas"
        verbose_name_plural = "Líderes de Operaciones Clínicas"


class SupervisorSeguimiento(models.Model):
    usuario = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='perfil_supervisor_seguimiento'
    )
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Supervisor de Seguimiento"
        verbose_name_plural = "Supervisores de Seguimiento"


class HostChecklistTask(models.Model):
    titulo = models.CharField(max_length=140)
    subtitulo = models.CharField(max_length=180, blank=True)
    etiqueta = models.CharField(max_length=40, blank=True)
    urgente = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)
    hosts = models.ManyToManyField(
        Host,
        blank=True,
        related_name='tareas_checklist',
        help_text='Dejalo vacio para que aplique a todos los hosts.',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titulo

    class Meta:
        verbose_name = "Tarea de Checklist Host"
        verbose_name_plural = "Tareas de Checklist Host"
        ordering = ['orden', 'id']


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
                errores['hora_fin'] = (
                    'Indica hora de inicio y hora final para un bloqueo parcial.'
                )
            else:
                inicio = datetime.combine(self.fecha_inicio, self.hora_inicio)
                fecha_fin = self.fecha_fin if self.fecha_fin else self.fecha_inicio
                fin = datetime.combine(fecha_fin, self.hora_fin)
                if fin <= inicio:
                    errores['hora_fin'] = (
                        'La fecha y hora final deben ser posteriores a la fecha y hora inicial.'
                    )

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
            inicio = datetime.combine(self.fecha_inicio, self.hora_inicio)
            fecha_fin = self.fecha_fin if self.fecha_fin else self.fecha_inicio
            fin = datetime.combine(fecha_fin, self.hora_fin)
            fecha_hora_consulta = datetime.combine(fecha_obj, hora_obj)
            return inicio <= fecha_hora_consulta < fin
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
    activo = models.BooleanField(default=False)

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

    # Dar de alta un paciente
    dado_de_alta = models.BooleanField(
        default = False,
        verbose_name = "Dado de alta"
    )
    fecha_alta = models.DateTimeField(
        null = True,
        blank = True
    )

    # Dar suspensión a un paciente
    estado = models.CharField(
        max_length=20,
        default="Activo"
    )
    fecha_suspension = models.DateTimeField(
        null=True,
        blank=True
    )
    motivo_suspension = models.TextField(
        null=True,
        blank=True
    )
    suspendido_por = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )


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

    division = models.ForeignKey(
        'Division', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pacientes', verbose_name='División'
    )

    # Relaciones
    pacientes_relacionados = models.ManyToManyField('self', blank=True, symmetrical=True)
    enlace_resultados = models.URLField(blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    dado_de_alta = models.BooleanField(default=False, verbose_name="Dado de alta")
    fecha_alta = models.DateTimeField(null=True, blank=True)

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


class RecursoPropio(models.Model):
    """Formatos y archivos propios del consultorio, accesibles desde el portal médico."""
    nombre       = models.CharField(max_length=200, verbose_name='Nombre del recurso')
    descripcion  = models.CharField(max_length=400, blank=True, verbose_name='Descripción')
    nombre_archivo = models.CharField(max_length=255)
    tipo_mime    = models.CharField(max_length=100, blank=True)
    contenido    = models.BinaryField()
    subido_por   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='recursos_propios')
    creado_en    = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = 'Recurso Propio'
        verbose_name_plural = 'Recursos Propios'
        ordering = ['nombre']


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
        ESTATUS_INCIDENCIA,
    )

    TIPO_NUEVO = 'N'
    TIPO_REFERIDO = 'R'
    TIPO_SEGUIMIENTO = 'S'
    TIPO_CRISIS = 'C'

    TIPO_PACIENTE_CHOICES = [
        (TIPO_NUEVO, 'Nuevo'),
        (TIPO_REFERIDO, 'Referido'),
        (TIPO_SEGUIMIENTO, 'Seguimiento'),
        (TIPO_CRISIS, 'Crisis'),
    ]

    PAGO_CHOICES = [
        ('Debito', 'Débito'),
        ('Credito', 'Crédito'),
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
    expediente_grupal = models.ForeignKey(
        'ExpedienteGrupal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='citas',
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
    sin_bono = models.BooleanField(
        default=False,
        help_text="Si True, la cita se paga al terapeuta pero no suma para el cálculo de bonos adicionales.",
    )
    tiene_descuento = models.BooleanField(
        null=True, blank=True,
        help_text="Indica si el paciente tiene descuento / estudio socioeconómico activo al momento de la cita."
    )

    # Marcas de envío de recordatorios/encuesta por WhatsApp (evitan reenvíos del cron)
    recordatorio_5d_enviado_en = models.DateTimeField(null=True, blank=True)
    recordatorio_3d_enviado_en = models.DateTimeField(null=True, blank=True)
    recordatorio_1d_enviado_en = models.DateTimeField(null=True, blank=True)
    encuesta_enviada_en = models.DateTimeField(null=True, blank=True)

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


class MensajeWhatsApp(models.Model):
    TIPO_RECORDATORIO_5D = 'recordatorio_5d'
    TIPO_RECORDATORIO_3D = 'recordatorio_3d'
    TIPO_CONFIRMACION_1D = 'confirmacion_1d'
    TIPO_ENCUESTA = 'encuesta'
    TIPO_REACTIVACION = 'reactivacion'

    TIPO_CHOICES = [
        (TIPO_RECORDATORIO_5D, 'Recordatorio 5 días'),
        (TIPO_RECORDATORIO_3D, 'Recordatorio 3 días'),
        (TIPO_CONFIRMACION_1D, 'Confirmación 1 día'),
        (TIPO_ENCUESTA, 'Encuesta conformidad'),
        (TIPO_REACTIVACION, 'Reactivación seguimiento'),
    ]
    ORIGEN_CHOICES = [
        ('automatico', 'Automático'),
        ('manual', 'Manual'),
    ]

    cita = models.ForeignKey(
        'Cita', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='mensajes_whatsapp',
    )
    paciente = models.ForeignKey(
        'Paciente', on_delete=models.CASCADE,
        related_name='mensajes_whatsapp',
    )
    telefono = models.CharField(max_length=20)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    origen = models.CharField(max_length=10, choices=ORIGEN_CHOICES, default='automatico')
    texto = models.TextField(blank=True)
    enviado_en = models.DateTimeField(auto_now_add=True)
    exitoso = models.BooleanField(default=False)
    respuesta_api = models.JSONField(null=True, blank=True)
    enviado_por = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
    )

    def __str__(self):
        return f"{self.get_tipo_display()} a {self.paciente} ({self.enviado_en:%d/%m/%Y %H:%M})"

    class Meta:
        verbose_name = 'Mensaje WhatsApp'
        verbose_name_plural = 'Mensajes WhatsApp'
        ordering = ['-enviado_en']


class MensajeWhatsAppEntrante(models.Model):
    """
    Mensajes que los pacientes responden al número de WhatsApp Cloud API (el que
    envía recordatorios/confirmaciones automáticos), capturados vía webhook.
    Distinto del número que el personal usa para chats manuales (app normal).
    """
    wa_message_id = models.CharField(max_length=100, unique=True)
    wa_id = models.CharField(max_length=20, verbose_name='Número (formato Meta)')
    paciente = models.ForeignKey(
        'Paciente', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='mensajes_whatsapp_recibidos',
    )
    # Los alumnos de Academia no son Pacientes: si el wa_id no corresponde a un
    # Paciente se intenta contra ContactoAcademia (campañas masivas).
    contacto_academia = models.ForeignKey(
        'ContactoAcademia', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='mensajes_recibidos',
    )
    texto = models.TextField(blank=True)
    recibido_en = models.DateTimeField(auto_now_add=True)
    atendido = models.BooleanField(default=False)
    atendido_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    atendido_en = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.wa_id}: {self.texto[:40]}"

    class Meta:
        verbose_name = 'Mensaje WhatsApp recibido'
        verbose_name_plural = 'Mensajes WhatsApp recibidos'
        ordering = ['-recibido_en']


class MensajeWhatsAppDemo(models.Model):
    """
    Envíos de plantillas WhatsApp a números sueltos con fines de demo/venta
    (prospectos, no ligados a un Paciente). Panel exclusivo de is_superuser
    (ver clinica.views.demos_whatsapp).
    """
    campana = models.CharField(max_length=50, help_text='Prospecto/cliente de la demo, ej. "dorothea"')
    tipo = models.CharField(max_length=50, help_text='Clave de la plantilla de Meta enviada')
    telefono = models.CharField(max_length=20)
    nombre_contacto = models.CharField(max_length=150, blank=True)
    texto = models.TextField(blank=True)
    enviado_en = models.DateTimeField(auto_now_add=True)
    exitoso = models.BooleanField(default=False)
    respuesta_api = models.JSONField(null=True, blank=True)
    enviado_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"[{self.campana}] {self.tipo} a {self.telefono} ({self.enviado_en:%d/%m/%Y %H:%M})"

    class Meta:
        verbose_name = 'Mensaje WhatsApp Demo'
        verbose_name_plural = 'Mensajes WhatsApp Demo'
        ordering = ['-enviado_en']


class ConfiguracionWhatsApp(models.Model):
    """Configuración global (registro único) del módulo de WhatsApp."""
    automatizacion_activa = models.BooleanField(
        default=True,
        help_text='Si está desactivado, el cron diario no envía recordatorios, '
                   'confirmaciones ni encuestas; solo queda disponible el envío manual.',
    )

    def __str__(self):
        return 'Automatización activa' if self.automatizacion_activa else 'Automatización desactivada'

    @classmethod
    def get_actual(cls):
        config, _ = cls.objects.get_or_create(pk=1)
        return config

    class Meta:
        verbose_name = 'Configuración WhatsApp'
        verbose_name_plural = 'Configuración WhatsApp'


class ContactoAcademia(models.Model):
    """
    Alumno de Academia (diplomados), destinatario de campañas masivas de
    WhatsApp. No es un Paciente: son dos bases distintas que solo comparten el
    número de WhatsApp desde el que se envía.

    Único por teléfono: en el Excel de origen una misma persona aparece varias
    veces si se inscribió a más de un diplomado (ver InscripcionAcademia), y
    enviarle la misma campaña 2-3 veces sería spam.
    """
    telefono = models.CharField(
        max_length=10, unique=True, db_index=True,
        help_text='10 dígitos, sin lada de país (mismo formato que Paciente.telefono).',
    )
    nombre = models.CharField(max_length=200)
    correo = models.EmailField(blank=True)
    suscrito = models.BooleanField(
        default=True,
        help_text='Si es False, el contacto pidió la baja y se excluye de toda campaña.',
    )
    baja_en = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombre} ({self.telefono})"

    class Meta:
        verbose_name = 'Contacto Academia'
        verbose_name_plural = 'Contactos Academia'
        ordering = ['nombre']


class InscripcionAcademia(models.Model):
    """Inscripción de un ContactoAcademia a un diplomado (una fila del Excel de origen)."""
    ESTATUS_ACTIVO = 'activo'
    ESTATUS_INACTIVO = 'inactivo'
    ESTATUS_POR_CONFIRMAR = 'por_confirmar'
    ESTATUS_CHOICES = [
        (ESTATUS_ACTIVO, 'Activo'),
        (ESTATUS_INACTIVO, 'Inactivo'),
        (ESTATUS_POR_CONFIRMAR, 'Por confirmar'),
    ]

    contacto = models.ForeignKey(
        ContactoAcademia, on_delete=models.CASCADE, related_name='inscripciones',
    )
    diplomado = models.CharField(max_length=120)
    anio_fuente = models.IntegerField()
    estatus = models.CharField(max_length=20, choices=ESTATUS_CHOICES, default=ESTATUS_ACTIVO)
    matricula = models.CharField(max_length=50, blank=True)
    fecha_inscripcion = models.DateField(null=True, blank=True)
    observaciones = models.TextField(blank=True)
    fila_origen = models.IntegerField(
        null=True, blank=True,
        help_text='Columna "Fila en archivo original" del Excel, para rastrear el dato.',
    )

    def __str__(self):
        return f"{self.contacto.nombre} — {self.diplomado} ({self.anio_fuente})"

    class Meta:
        verbose_name = 'Inscripción Academia'
        verbose_name_plural = 'Inscripciones Academia'
        ordering = ['-anio_fuente', 'diplomado']
        unique_together = [('contacto', 'diplomado', 'anio_fuente')]


class CampanaMasiva(models.Model):
    """Un envío masivo de una plantilla de WhatsApp a contactos de Academia."""
    ESTADO_BORRADOR = 'borrador'
    ESTADO_ENVIANDO = 'enviando'
    ESTADO_ENVIADA = 'enviada'
    ESTADO_PAUSADA = 'pausada'
    ESTADO_CHOICES = [
        (ESTADO_BORRADOR, 'Borrador'),
        (ESTADO_ENVIANDO, 'Enviando'),
        (ESTADO_ENVIADA, 'Enviada'),
        (ESTADO_PAUSADA, 'Pausada'),
    ]

    nombre = models.CharField(max_length=150)
    plantilla_meta = models.CharField(
        max_length=120, help_text='Nombre exacto de la plantilla aprobada en Meta.',
    )
    idioma = models.CharField(max_length=10, default='es_MX')
    texto_render = models.TextField(
        blank=True,
        help_text='Copia del cuerpo de la plantilla al momento de crear la campaña.',
    )
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_BORRADOR)
    creada_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    creada_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} ({self.get_estado_display()}, {self.creada_en:%d/%m/%Y})"

    class Meta:
        verbose_name = 'Campaña masiva'
        verbose_name_plural = 'Campañas masivas'
        ordering = ['-creada_en']


class EnvioMasivo(models.Model):
    """Un mensaje individual dentro de una CampanaMasiva, con su estado de entrega."""
    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_ENVIADO = 'enviado'
    ESTADO_ENTREGADO = 'entregado'
    ESTADO_LEIDO = 'leido'
    ESTADO_FALLIDO = 'fallido'
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_ENVIADO, 'Enviado'),
        (ESTADO_ENTREGADO, 'Entregado'),
        (ESTADO_LEIDO, 'Leído'),
        (ESTADO_FALLIDO, 'Fallido'),
    ]

    campana = models.ForeignKey(CampanaMasiva, on_delete=models.CASCADE, related_name='envios')
    contacto = models.ForeignKey(ContactoAcademia, on_delete=models.CASCADE, related_name='envios')
    telefono = models.CharField(max_length=20)
    wa_message_id = models.CharField(
        max_length=100, blank=True, db_index=True,
        help_text='ID que devuelve Meta al enviar; correlaciona los webhooks de estado.',
    )
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE)
    error_codigo = models.CharField(max_length=20, blank=True)
    error_mensaje = models.TextField(blank=True)
    respuesta_api = models.JSONField(null=True, blank=True)
    enviado_en = models.DateTimeField(null=True, blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.contacto.nombre} — {self.get_estado_display()}"

    class Meta:
        verbose_name = 'Envío masivo'
        verbose_name_plural = 'Envíos masivos'
        ordering = ['contacto__nombre']
        # Blindaje anti doble envío: un contacto solo puede recibir una campaña una vez.
        unique_together = [('campana', 'contacto')]


class RespuestaMasiva(models.Model):
    """
    Texto libre que el personal le contesta a un alumno desde la bandeja de
    Mensajes Masivos. Solo se puede dentro de la ventana de 24 h que abre la
    respuesta del alumno (regla de Meta), por eso no es una plantilla.
    """
    contacto = models.ForeignKey(
        ContactoAcademia, on_delete=models.CASCADE, related_name='respuestas_enviadas',
    )
    texto = models.TextField()
    enviado_en = models.DateTimeField(auto_now_add=True)
    exitoso = models.BooleanField(default=False)
    respuesta_api = models.JSONField(null=True, blank=True)
    enviado_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"A {self.contacto.nombre} ({self.enviado_en:%d/%m/%Y %H:%M})"

    class Meta:
        verbose_name = 'Respuesta a alumno'
        verbose_name_plural = 'Respuestas a alumnos'
        ordering = ['enviado_en']


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

    CONFIRMACION_ACEPTADO = 'aceptado'
    CONFIRMACION_INCIDENCIA = 'incidencia'
    CONFIRMACION_CHOICES = [
        ('aceptado', 'Aceptado por terapeuta'),
        ('incidencia', 'Incidencia reportada'),
    ]
    confirmacion_terapeuta = models.CharField(
        max_length=20, choices=CONFIRMACION_CHOICES, null=True, blank=True,
    )
    confirmacion_terapeuta_en = models.DateTimeField(null=True, blank=True)

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
    TIPO_EXPOSITOR = 'expositor'

    TIPO_CHOICES = [
        (TIPO_SESION, 'Sesión'),
        (TIPO_BONO_UMBRAL, 'Bono por volumen'),
        (TIPO_BONO_POR_PACIENTE, 'Bono por paciente'),
        (TIPO_PENALIZACION, 'Penalización inasistencia'),
        (TIPO_EXPOSITOR, 'Horas Expositor'),
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


class ExpedienteGrupal(models.Model):
    TIPO_PAREJA = 'pareja'
    TIPO_FAMILIA = 'familia'
    TIPO_CHOICES = [
        (TIPO_PAREJA, 'Pareja'),
        (TIPO_FAMILIA, 'Familia'),
    ]

    expediente_no   = models.CharField(max_length=50, unique=True, blank=True, verbose_name='No. de Expediente')
    tipo            = models.CharField(max_length=20, choices=TIPO_CHOICES, default=TIPO_PAREJA)
    nombre          = models.CharField(max_length=300, blank=True, verbose_name='Nombre del Expediente')
    pacientes       = models.ManyToManyField('Paciente', related_name='expedientes_grupales', blank=True)
    division        = models.ForeignKey('Division', on_delete=models.SET_NULL, null=True, blank=True)
    motivo_consulta = models.TextField(blank=True, verbose_name='Motivo de consulta')
    fecha_apertura  = models.DateField(auto_now_add=True)
    creado_en       = models.DateTimeField(auto_now_add=True)

    def generar_nombre(self):
        nombres = list(self.pacientes.values_list('nombre', flat=True))
        if not nombres:
            return ''
        tipo_label = 'Pareja' if self.tipo == self.TIPO_PAREJA else 'Familia'
        if len(nombres) == 1:
            return f"{tipo_label} {nombres[0]}"
        if len(nombres) == 2:
            return f"{tipo_label} {nombres[0]} y {nombres[1]}"
        return f"{tipo_label} {', '.join(nombres[:-1])} y {nombres[-1]}"

    def _siguiente_numero(self):
        from django.db.models import Max
        año = date.today().year
        prefijo = f'EG-{año}-'
        ultimo = (
            ExpedienteGrupal.objects
            .filter(expediente_no__startswith=prefijo)
            .aggregate(max_no=Max('expediente_no'))['max_no']
        )
        if ultimo:
            try:
                seq = int(ultimo.split('-')[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        return f'{prefijo}{seq:04d}'

    def save(self, *args, **kwargs):
        if not self.expediente_no:
            self.expediente_no = self._siguiente_numero()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre or self.expediente_no

    class Meta:
        verbose_name = 'Expediente Grupal'
        verbose_name_plural = 'Expedientes Grupales'
        ordering = ['-fecha_apertura']


class AperturaExpedienteGrupal(models.Model):
    ESTADO_CIVIL_CHOICES = [
        ('', '---------'),
        ('soltero', 'Soltero(a)'),
        ('casado', 'Casado(a)'),
        ('divorciado', 'Divorciado(a)'),
        ('viudo', 'Viudo(a)'),
        ('union_libre', 'Unión libre'),
        ('otro', 'Otro'),
    ]

    expediente = models.OneToOneField(
        'ExpedienteGrupal',
        on_delete=models.CASCADE,
        related_name='apertura',
    )
    division            = models.ForeignKey('Division', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='División')
    motivo_consulta     = models.TextField(blank=True, verbose_name='Motivo de consulta')
    calle               = models.CharField(max_length=200, blank=True, verbose_name='Calle')
    num_exterior        = models.CharField(max_length=20, blank=True, verbose_name='Núm.')
    colonia             = models.CharField(max_length=150, blank=True, verbose_name='Col.')
    religion            = models.CharField(max_length=100, blank=True, verbose_name='Religión')
    vive_con            = models.CharField(max_length=200, blank=True, verbose_name='Vive con')
    tiene_hijos         = models.BooleanField(default=False, verbose_name='Tiene hijos')
    num_hijos           = models.PositiveIntegerField(null=True, blank=True, verbose_name='No. de Hijos')
    hijo_1              = models.CharField(max_length=200, blank=True, verbose_name='Hijo 1')
    hijo_2              = models.CharField(max_length=200, blank=True, verbose_name='Hijo 2')
    hijo_3              = models.CharField(max_length=200, blank=True, verbose_name='Hijo 3')
    hijo_4              = models.CharField(max_length=200, blank=True, verbose_name='Hijo 4')
    emergencia_contacto = models.CharField(max_length=200, blank=True, verbose_name='En caso de emergencia llamar a')
    emergencia_telefono = models.CharField(max_length=30, blank=True, verbose_name='Teléfono de emergencia')
    como_se_entero      = models.CharField(max_length=200, blank=True, verbose_name='¿Cómo se enteraron de nosotros?')
    creado_en           = models.DateTimeField(auto_now_add=True)
    actualizado_en      = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Apertura grupal – {self.expediente}'

    class Meta:
        verbose_name = 'Apertura de Expediente Grupal'
        verbose_name_plural = 'Aperturas de Expediente Grupal'


class NotaExpedienteGrupal(models.Model):
    expediente = models.ForeignKey(
        'ExpedienteGrupal',
        on_delete=models.CASCADE,
        related_name='notas',
    )
    terapeuta = models.ForeignKey(
        'Terapeuta',
        on_delete=models.SET_NULL,
        null=True,
        related_name='notas_expedientes_grupales',
    )
    contenido  = models.TextField(verbose_name='Nota')
    creado_en  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Nota de {self.terapeuta} — {self.expediente} ({self.creado_en:%d/%m/%Y})"

    class Meta:
        verbose_name = 'Nota de Expediente Grupal'
        verbose_name_plural = 'Notas de Expediente Grupal'
        ordering = ['-creado_en']


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

    # Antecedentes médicos
    tiene_enfermedad        = models.BooleanField(default=False, verbose_name='¿Tiene alguna enfermedad?')
    cual_enfermedad         = models.CharField(max_length=300, blank=True, verbose_name='¿Cuál enfermedad?')

    # Antecedentes psiquiátricos
    tx_psiquiatrico         = models.BooleanField(default=False, verbose_name='¿Está o ha estado en tratamiento psiquiátrico?')
    tx_psiquiatrico_hace_cuanto = models.CharField(max_length=100, blank=True, verbose_name='¿Hace cuánto? (Tx psiquiátrico)')
    tx_psiquiatrico_motivo  = models.TextField(blank=True, verbose_name='Motivo del tratamiento psiquiátrico')
    tx_psiquiatrico_medicamento = models.CharField(max_length=300, blank=True, verbose_name='Medicamento(s)')

    # Terapia previa
    ha_tomado_terapia       = models.BooleanField(default=False, verbose_name='¿Ha tomado terapia anteriormente?')
    terapia_hace_cuanto     = models.CharField(max_length=100, blank=True, verbose_name='¿Hace cuánto? (Terapia)')
    terapia_duracion        = models.CharField(max_length=100, blank=True, verbose_name='¿Cuánto duró la terapia?')
    terapia_motivo          = models.TextField(blank=True, verbose_name='Motivo de la terapia anterior')

    # Sustancias
    fuma                    = models.BooleanField(default=False, verbose_name='¿Fuma?')
    consume_alcohol         = models.BooleanField(default=False, verbose_name='¿Consume alcohol?')
    consume_otras_sustancias = models.BooleanField(default=False, verbose_name='¿Consume o ha consumido otras sustancias?')
    cuales_sustancias       = models.CharField(max_length=300, blank=True, verbose_name='¿Cuáles sustancias?')

    # Hábitos
    comidas_al_dia          = models.PositiveIntegerField(null=True, blank=True, verbose_name='Comidas al día')
    horas_sueno             = models.PositiveIntegerField(null=True, blank=True, verbose_name='Horas de sueño al día')
    actividad_fisica        = models.BooleanField(default=False, verbose_name='¿Realiza actividad física?')
    cual_actividad_fisica   = models.CharField(max_length=200, blank=True, verbose_name='¿Cuál actividad física?')

    # Ideación/intento suicida
    intento_suicida         = models.BooleanField(default=False, verbose_name='¿Ha intentado quitarse la vida?')
    intento_suicida_hace_cuanto = models.CharField(max_length=100, blank=True, verbose_name='¿Hace cuánto? (Intento)')
    intento_suicida_que_hizo = models.TextField(blank=True, verbose_name='¿Qué hizo?')
    intento_suicida_motivo  = models.TextField(blank=True, verbose_name='¿Por qué?')

    # Vida sexual
    vida_sexual_activa      = models.BooleanField(default=False, verbose_name='¿Tiene vida sexual activa?')

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
    respuesta = models.TextField(blank=True, default='')
    respuesta_fecha = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"[{self.get_tipo_display()}] {self.titulo} — {self.terapeuta}"

    class Meta:
        verbose_name = "Reporte / Incidente"
        verbose_name_plural = "Reportes e Incidentes"
        ordering = ['-fecha_creacion']


class NotificacionTerapeuta(models.Model):
    TIPO_CITA_ACEPTADA        = 'cita_aceptada'
    TIPO_CITA_RECHAZADA       = 'cita_rechazada'
    TIPO_CITA_MODIFICADA      = 'cita_modificada'
    TIPO_REAGENDO_APROBADO    = 'reagendo_aprobado'
    TIPO_REAGENDO_RECHAZADO   = 'reagendo_rechazado'
    TIPO_RESPUESTA_INCIDENTE  = 'respuesta_incidente'
    TIPO_EXPOSITOR_ACEPTADO   = 'expositor_aceptado'
    TIPO_EXPOSITOR_RECHAZADO  = 'expositor_rechazado'

    TIPO_CHOICES = [
        (TIPO_CITA_ACEPTADA,        'Cita aceptada'),
        (TIPO_CITA_RECHAZADA,       'Cita rechazada'),
        (TIPO_CITA_MODIFICADA,      'Cita modificada'),
        (TIPO_REAGENDO_APROBADO,    'Reagendo aprobado'),
        (TIPO_REAGENDO_RECHAZADO,   'Reagendo rechazado'),
        (TIPO_RESPUESTA_INCIDENTE,  'Respuesta a reporte'),
        (TIPO_EXPOSITOR_ACEPTADO,   'Horas expositor aceptadas'),
        (TIPO_EXPOSITOR_RECHAZADO,  'Horas expositor rechazadas'),
    ]

    terapeuta  = models.ForeignKey('Terapeuta', on_delete=models.CASCADE, related_name='notificaciones')
    tipo       = models.CharField(max_length=30, choices=TIPO_CHOICES)
    mensaje    = models.TextField()
    leida      = models.BooleanField(default=False)
    creada_en  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notificación de Terapeuta"
        verbose_name_plural = "Notificaciones de Terapeutas"
        ordering = ['-creada_en']

    def __str__(self):
        return f"[{self.get_tipo_display()}] {self.terapeuta} — {'leída' if self.leida else 'nueva'}"


class SolicitudHorasExpositor(models.Model):
    ESTADO_PENDIENTE  = 'pendiente'
    ESTADO_ACEPTADA   = 'aceptada'
    ESTADO_RECHAZADA  = 'rechazada'

    ESTADO_CHOICES = [
        ('pendiente',  'Pendiente'),
        ('aceptada',   'Aceptada'),
        ('rechazada',  'Rechazada'),
    ]

    terapeuta  = models.ForeignKey('Terapeuta', on_delete=models.CASCADE, related_name='solicitudes_expositor')
    horas      = models.PositiveIntegerField(verbose_name='Número de horas')
    lugar      = models.CharField(max_length=200, verbose_name='Lugar / Evento')
    notas      = models.TextField(verbose_name='Descripción de la actividad')
    estado     = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    creado_en  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Solicitud de Horas Expositor"
        verbose_name_plural = "Solicitudes de Horas Expositor"
        ordering = ['-creado_en']

    def __str__(self):
        return f'{self.terapeuta} — {self.horas}h ({self.get_estado_display()})'


class NotaRecepcion(models.Model):
    texto      = models.TextField()
    creado_por = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, related_name='notas_recepcion'
    )
    creado_en  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Nota de Recepción"
        verbose_name_plural = "Notas de Recepción"
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.creado_por} — {self.creado_en:%d/%m/%Y}"


class ReaccionNota(models.Model):
    nota    = models.ForeignKey(NotaRecepcion, on_delete=models.CASCADE, related_name='reacciones')
    usuario = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='reacciones_notas')
    emoji   = models.CharField(max_length=10)

    class Meta:
        unique_together = ('nota', 'usuario', 'emoji')


class ComentarioNota(models.Model):
    nota       = models.ForeignKey(NotaRecepcion, on_delete=models.CASCADE, related_name='comentarios')
    creado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='comentarios_notas')
    texto      = models.TextField()
    creado_en  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['creado_en']


class RegistroActividad(models.Model):
    ACCION_CITA_CREADA          = 'cita_creada'
    ACCION_CITA_EDITADA         = 'cita_editada'
    ACCION_CITA_ELIMINADA       = 'cita_eliminada'
    ACCION_CITA_CHECKOUT        = 'cita_checkout'
    ACCION_DISPONIB_AGREGADA    = 'disponib_agregada'
    ACCION_DISPONIB_ELIMINADA   = 'disponib_eliminada'
    ACCION_BLOQUEO_CREADO       = 'bloqueo_creado'
    ACCION_BLOQUEO_ELIMINADO    = 'bloqueo_eliminado'
    ACCION_SOLICITUD_ACEPTADA   = 'solicitud_aceptada'
    ACCION_SOLICITUD_RECHAZADA  = 'solicitud_rechazada'
    ACCION_REAGENDO_SOLICITADO  = 'reagendo_solicitado'
    ACCION_REAGENDO_APROBADO    = 'reagendo_aprobado'
    ACCION_REAGENDO_RECHAZADO   = 'reagendo_rechazado'
    ACCION_PACIENTE_REGISTRADO  = 'paciente_registrado'
    ACCION_PACIENTE_EDITADO     = 'paciente_editado'
    ACCION_PACIENTE_ELIMINADO   = 'paciente_eliminado'
    ACCION_NOMINA_APROBADA      = 'nomina_aprobada'
    ACCION_EXPOSITOR_RESPONDIDO = 'expositor_respondido'
    ACCION_INCIDENTE_REPORTADO  = 'incidente_reportado'
    ACCION_INCIDENTE_RESPONDIDO = 'incidente_respondido'
    ACCION_INSTRUMENTO_ENVIADO  = 'instrumento_enviado'

    ACCION_CHOICES = [
        (ACCION_CITA_CREADA,          'Cita agendada'),
        (ACCION_CITA_EDITADA,         'Cita editada'),
        (ACCION_CITA_ELIMINADA,       'Cita eliminada'),
        (ACCION_CITA_CHECKOUT,        'Sesión cerrada'),
        (ACCION_DISPONIB_AGREGADA,    'Disponibilidad agregada'),
        (ACCION_DISPONIB_ELIMINADA,   'Disponibilidad eliminada'),
        (ACCION_BLOQUEO_CREADO,       'Bloqueo de agenda creado'),
        (ACCION_BLOQUEO_ELIMINADO,    'Bloqueo de agenda eliminado'),
        (ACCION_SOLICITUD_ACEPTADA,   'Solicitud aceptada'),
        (ACCION_SOLICITUD_RECHAZADA,  'Solicitud rechazada'),
        (ACCION_REAGENDO_SOLICITADO,  'Reagendo solicitado'),
        (ACCION_REAGENDO_APROBADO,    'Reagendo aprobado'),
        (ACCION_REAGENDO_RECHAZADO,   'Reagendo rechazado'),
        (ACCION_PACIENTE_REGISTRADO,  'Paciente registrado'),
        (ACCION_PACIENTE_EDITADO,     'Paciente editado'),
        (ACCION_PACIENTE_ELIMINADO,   'Paciente eliminado'),
        (ACCION_NOMINA_APROBADA,      'Nómina aprobada'),
        (ACCION_EXPOSITOR_RESPONDIDO, 'Horas expositor respondidas'),
        (ACCION_INCIDENTE_REPORTADO,  'Incidente reportado'),
        (ACCION_INCIDENTE_RESPONDIDO, 'Incidente respondido'),
        (ACCION_INSTRUMENTO_ENVIADO,  'Instrumento enviado a paciente'),
    ]

    CAT_CITA           = 'cita'
    CAT_DISPONIBILIDAD = 'disponibilidad'
    CAT_REAGENDO       = 'reagendo'
    CAT_PACIENTE       = 'paciente'
    CAT_NOMINA         = 'nomina'
    CAT_SOLICITUD      = 'solicitud'
    CAT_INCIDENTE      = 'incidente'
    CAT_INSTRUMENTO    = 'instrumento'

    CAT_CHOICES = [
        (CAT_CITA,           'Cita'),
        (CAT_DISPONIBILIDAD, 'Disponibilidad'),
        (CAT_REAGENDO,       'Reagendo'),
        (CAT_PACIENTE,       'Paciente'),
        (CAT_NOMINA,         'Nómina'),
        (CAT_SOLICITUD,      'Solicitud'),
        (CAT_INCIDENTE,      'Incidente'),
        (CAT_INSTRUMENTO,    'Instrumento'),
    ]

    _ICONO_MAP = {
        'cita_creada':          'bi-calendar-plus-fill',
        'cita_editada':         'bi-pencil-fill',
        'cita_eliminada':       'bi-calendar-x-fill',
        'cita_checkout':        'bi-clipboard-check-fill',
        'disponib_agregada':    'bi-clock-fill',
        'disponib_eliminada':   'bi-clock-history',
        'bloqueo_creado':       'bi-slash-circle-fill',
        'bloqueo_eliminado':    'bi-unlock-fill',
        'solicitud_aceptada':   'bi-check-circle-fill',
        'solicitud_rechazada':  'bi-x-circle-fill',
        'reagendo_solicitado':  'bi-arrow-repeat',
        'reagendo_aprobado':    'bi-check2-circle',
        'reagendo_rechazado':   'bi-x-circle',
        'paciente_registrado':  'bi-person-plus-fill',
        'paciente_editado':     'bi-person-gear',
        'paciente_eliminado':   'bi-person-x-fill',
        'nomina_aprobada':      'bi-cash-coin',
        'expositor_respondido': 'bi-mortarboard-fill',
        'incidente_reportado':  'bi-exclamation-triangle-fill',
        'incidente_respondido': 'bi-chat-right-dots-fill',
        'instrumento_enviado':  'bi-clipboard2-pulse-fill',
    }

    usuario            = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='registros_actividad')
    accion             = models.CharField(max_length=40, choices=ACCION_CHOICES, db_index=True)
    categoria          = models.CharField(max_length=20, choices=CAT_CHOICES, db_index=True)
    descripcion        = models.TextField()
    terapeuta_afectado = models.ForeignKey('Terapeuta', on_delete=models.SET_NULL, null=True, blank=True, related_name='registros_actividad')
    paciente_afectado  = models.ForeignKey('Paciente', on_delete=models.SET_NULL, null=True, blank=True, related_name='registros_actividad')
    ip_address         = models.GenericIPAddressField(null=True, blank=True)
    timestamp          = models.DateTimeField(default=timezone.now, db_index=True)
    es_retroactivo     = models.BooleanField(default=False)

    @property
    def icono(self):
        return self._ICONO_MAP.get(self.accion, 'bi-activity')

    def __str__(self):
        u = self.usuario.username if self.usuario else 'Sistema'
        return f"[{self.get_categoria_display()}] {u} — {self.get_accion_display()} ({self.timestamp:%d/%m/%Y %H:%M})"

    class Meta:
        verbose_name        = 'Registro de Actividad'
        verbose_name_plural = 'Registro de Actividades'
        ordering            = ['-timestamp']


# ───────────────────────── MÓDULO INSTRUMENTOS ─────────────────────────
# Encuestas/evaluaciones clínicas que el terapeuta aplica al paciente.
# Cada instrumento define su propio cuestionario y su propio baremo de
# puntuación (la fórmula de cálculo vive en clinica/services_instrumentos.py,
# identificada por el campo `clave` de cada Instrumento).

class Instrumento(models.Model):
    nombre = models.CharField(max_length=150, verbose_name="Nombre del instrumento")
    clave = models.SlugField(
        max_length=50, unique=True,
        help_text="Identificador interno usado por el motor de puntuación (ej. 'preconsulta', 'scid_ii')."
    )
    descripcion = models.TextField(blank=True, verbose_name="Descripción / para qué sirve")
    instrucciones = models.TextField(
        blank=True,
        verbose_name="Instrucciones para el paciente",
        help_text="Texto que ve el paciente antes de empezar a responder."
    )
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Instrumento"
        verbose_name_plural = "Instrumentos"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class PreguntaInstrumento(models.Model):
    TIPO_OPCION_UNICA    = 'opcion_unica'
    TIPO_OPCION_MULTIPLE = 'opcion_multiple'
    TIPO_ESCALA          = 'escala'
    TIPO_SI_NO           = 'si_no'
    TIPO_TEXTO_LIBRE     = 'texto_libre'
    TIPO_IMAGEN_UNICA    = 'imagen_unica'

    TIPO_CHOICES = [
        (TIPO_OPCION_UNICA,    'Opción única'),
        (TIPO_OPCION_MULTIPLE, 'Opción múltiple'),
        (TIPO_ESCALA,          'Escala numérica / Likert'),
        (TIPO_SI_NO,           'Sí / No'),
        (TIPO_TEXTO_LIBRE,     'Texto libre'),
        (TIPO_IMAGEN_UNICA,    'Imagen + opción única'),
    ]

    instrumento = models.ForeignKey(Instrumento, on_delete=models.CASCADE, related_name='preguntas')
    orden = models.PositiveIntegerField(default=0)
    texto = models.TextField(verbose_name="Enunciado de la pregunta")
    clave = models.CharField(
        max_length=50, blank=True,
        help_text="Identificador interno del reactivo para el motor de puntuación (ej. 'item_1')."
    )
    tipo_respuesta = models.CharField(max_length=20, choices=TIPO_CHOICES, default=TIPO_OPCION_UNICA)
    opciones = models.JSONField(
        blank=True, null=True,
        help_text="Opciones de respuesta como lista de objetos {valor, etiqueta}. Aplica a opción única/múltiple/escala."
    )
    imagen = models.CharField(
        max_length=400, blank=True, default='',
        help_text="Ruta relativa a static para la imagen de la pregunta (e.g. 'instrumentos/raven/1.png')."
    )
    titulo_grupo = models.CharField(
        max_length=600, blank=True, default='',
        help_text="Encabezado de grupo para preguntas que se renderizan en bloque (e.g. ítem Allport S2)."
    )
    requerida = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Pregunta de Instrumento"
        verbose_name_plural = "Preguntas de Instrumento"
        ordering = ['instrumento', 'orden', 'id']

    def __str__(self):
        return f"{self.instrumento} #{self.orden}: {self.texto[:60]}"


class EnvioInstrumento(models.Model):
    """Una aplicación concreta de un Instrumento a un Paciente, identificada
    por un token único que arma el link público que se le comparte al paciente."""

    ESTADO_PENDIENTE  = 'pendiente'
    ESTADO_RESPONDIDO = 'respondido'
    ESTADO_CANCELADO  = 'cancelado'

    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE,  'Pendiente'),
        (ESTADO_RESPONDIDO, 'Respondido'),
        (ESTADO_CANCELADO,  'Cancelado'),
    ]

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    instrumento = models.ForeignKey(Instrumento, on_delete=models.PROTECT, related_name='envios')
    paciente = models.ForeignKey('Paciente', on_delete=models.CASCADE, related_name='instrumentos_enviados')
    generado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='instrumentos_generados'
    )
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE, db_index=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    respondido_en = models.DateTimeField(null=True, blank=True)

    # Resultado calculado automáticamente con el baremo propio del instrumento
    puntaje_total = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    interpretacion = models.TextField(
        blank=True,
        verbose_name="Interpretación automática",
        help_text="Texto de interpretación generado por el motor de puntuación a partir del baremo del instrumento."
    )
    resultado_detalle = models.JSONField(
        blank=True, null=True,
        verbose_name="Detalle del resultado",
        help_text="Desglose del cálculo (subescalas, rangos, semáforos, etc.) que respalda la interpretación automática."
    )

    class Meta:
        verbose_name = "Aplicación de Instrumento"
        verbose_name_plural = "Aplicaciones de Instrumento"
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.instrumento} → {self.paciente} ({self.get_estado_display()})"


class RespuestaInstrumento(models.Model):
    envio = models.ForeignKey(EnvioInstrumento, on_delete=models.CASCADE, related_name='respuestas')
    pregunta = models.ForeignKey(PreguntaInstrumento, on_delete=models.CASCADE, related_name='respuestas')
    valor = models.TextField(blank=True, verbose_name="Respuesta cruda (texto u opción elegida)")
    valor_numerico = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name="Valor numérico",
        help_text="Equivalente numérico de la respuesta, usado por el motor de puntuación."
    )

    class Meta:
        verbose_name = "Respuesta de Instrumento"
        verbose_name_plural = "Respuestas de Instrumento"
        unique_together = ('envio', 'pregunta')
        ordering = ['envio', 'pregunta__orden']

    def __str__(self):
        return f"{self.envio} — {self.pregunta}: {self.valor[:40]}"
