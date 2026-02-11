import unicodedata
from django.db import models

def quitar_tildes(texto):
    if not texto:
        return ""
   
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto))
                   if unicodedata.category(c) != 'Mn').lower()

class Terapeuta(models.Model):
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
    ESTATUS_CHOICES = [
        ('programada', 'Programada'),
        ('asistio', 'Asistió'),
        ('cancelada', 'Cancelada'),
        ('no_asistio', 'No Asistió'),
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
    fecha = models.DateField()
    hora = models.TimeField()
    
 
    division = models.ForeignKey(Division, on_delete=models.SET_NULL, null=True)
    consultorio = models.ForeignKey(Consultorio, on_delete=models.SET_NULL, null=True)
    servicio = models.ForeignKey(Servicio, on_delete=models.SET_NULL, null=True)
    terapeuta = models.ForeignKey(Terapeuta, on_delete=models.SET_NULL, null=True)
    
    costo = models.DecimalField(max_digits=10, decimal_places=2, default=500.00)
    metodo_pago = models.CharField(max_length=20, choices=PAGO_CHOICES, default='Pendiente')
    estatus = models.CharField(max_length=20, choices=ESTATUS_CHOICES, default='programada')
    
    folio_fiscal = models.CharField(max_length=100, blank=True, null=True)
    notas = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.paciente} - {self.fecha}"

    class Meta:
        verbose_name = "Cita"
        verbose_name_plural = "Citas"
        ordering = ['-fecha', '-hora']