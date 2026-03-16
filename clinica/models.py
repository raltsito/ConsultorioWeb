import unicodedata
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
        ('Efectivo', 'Efectivo'),
        ('Transferencia', 'Transferencia'),
        ('Terminal', 'Terminal'),
        ('Pase', 'Pase'),
        ('Gratuito', 'Gratuito'),
        ('Pendiente', 'Pendiente'),
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
    metodo_pago = models.CharField(max_length=50, null=True, blank=True)
    estatus = models.CharField(
        max_length=20,
        choices=ESTATUS_CHOICES,
        default=ESTATUS_SIN_CONFIRMAR,
    )
    
    folio_fiscal = models.CharField(max_length=100, blank=True, null=True)
    notas = models.TextField(blank=True, null=True)

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
