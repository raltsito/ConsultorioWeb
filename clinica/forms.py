from django import forms
from django.core.exceptions import ValidationError

from .models import (
    AperturaExpediente,
    BloqueoAgendaTerapeuta,
    Cita,
    DocumentoPaciente,
    Horario,
    NotaTerapeutaPaciente,
    Paciente,
    ReglaTerapeuta,
    ReporteSesion,
    TabuladorGeneral,
    obtener_bloqueo_terapeuta_en_fecha,
)
from .models import Terapeuta, Consultorio, Division, Servicio


class CheckoutCitaForm(forms.Form):
    """
    Formulario de cierre de sesión para el portal del terapeuta.
    Actualiza la Cita (estatus, metodo_pago, costo) y opcionalmente
    crea una SolicitudCita de seguimiento.
    """
    estatus = forms.ChoiceField(
        choices=[
            ('si_asistio',  'Sí asistió'),
            ('no_asistio',  'No asistió'),
            ('cancelo',     'Canceló'),
            ('incidencia',  'Incidencia'),
        ],
        widget=forms.HiddenInput(),
        label='Resultado de la sesión',
    )
    metodo_pago = forms.ChoiceField(
        choices=[('', '— Sin pago —')] + Cita.PAGO_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Método de Pago',
    )
    costo = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
        }),
        label='Monto cobrado al paciente ($)',
    )
    solicitar_siguiente = forms.BooleanField(required=False, label='Solicitar próxima cita')
    siguiente_fecha = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Fecha propuesta',
    )
    siguiente_hora = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        label='Hora propuesta',
    )
    notas_recepcion = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Ej: Necesita consultorio 1, prefiere las mañanas...',
        }),
        label='Comentarios para Recepción',
    )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('solicitar_siguiente') and not cleaned_data.get('siguiente_fecha'):
            self.add_error('siguiente_fecha', 'Indica la fecha propuesta para la próxima cita.')
        return cleaned_data


class ManualPortalForm(forms.Form):
    titulo = forms.CharField(
        required=False,
        max_length=120,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Manual del sistema',
        }),
        label='Titulo visible',
    )
    archivo = forms.FileField(
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
        label='Archivo del manual',
    )


class PacienteForm(forms.ModelForm):
    class Meta:
        model = Paciente
        fields = [
            'nombre', 'fecha_nacimiento', 'telefono', 'identidad_contacto', 
            'servicio_inicial','pacientes_relacionados', 'consentimiento_firmado', 'estudio_socioeconomico', 
            'apertura_expediente', 'resumen_clinico', 'enlace_resultados'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre completo'}),
            'fecha_nacimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'WhatsApp'}),
            'identidad_contacto': forms.Select(attrs={'class': 'form-select'}),
            'servicio_inicial': forms.Select(attrs={'class': 'form-select'}),
            
            'consentimiento_firmado': forms.FileInput(attrs={'class': 'form-control'}),
            'estudio_socioeconomico': forms.FileInput(attrs={'class': 'form-control'}),
            'apertura_expediente': forms.FileInput(attrs={'class': 'form-control'}),
            'resumen_clinico': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Notas privadas del terapeuta...'}),
            'enlace_resultados': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            
            # Aquí está la corrección: aseguramos las comas y llaves
            'pacientes_relacionados': forms.SelectMultiple(attrs={
                'class': 'form-control select2-multiple',
                'style': 'width: 100%',
                'multiple': 'multiple'
            }), 
        }

class CitaForm(forms.ModelForm):
    pacientes_extra = forms.ModelMultipleChoiceField(
        queryset=Paciente.objects.none(),
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                'class': 'form-select select2-pacientes-extra',
                'multiple': 'multiple',
            }
        ),
        label='Pacientes relacionados',
    )

    class Meta:
        model = Cita
        fields = [
            'paciente', 'fecha', 'hora', 'tipo_paciente', 'division', 
            'consultorio', 'servicio', 'terapeuta', 
            'costo', 'metodo_pago', 'estatus', 
            'folio_fiscal', 'notas'
        ]
        
        widgets = {
            'fecha': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'hora': forms.TimeInput(format='%H:%M', attrs={'type': 'time', 'class': 'form-control'}),
            'notas': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'paciente': forms.Select(attrs={'class': 'form-select select2-paciente'}),
            'tipo_paciente': forms.Select(attrs={'class': 'form-select'}),
            'metodo_pago': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['pacientes_extra'].queryset = Paciente.objects.order_by('nombre')
        if self.instance and self.instance.pk:
            self.fields['pacientes_extra'].initial = self.instance.pacientes_adicionales.all()

        # Bucle para estilos Bootstrap
        for field_name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                 field.widget.attrs['class'] = 'form-control'
        
        # Hacer TODOS los campos opcionales para flexibilidad máxima
        for field_name, field in self.fields.items():
            field.required = False
            # Remover atributos required del HTML
            if 'required' in field.widget.attrs:
                del field.widget.attrs['required']

    def clean_pacientes_extra(self):

        pacientes_extra = self.cleaned_data.get('pacientes_extra')
        paciente_principal = self.cleaned_data.get('paciente')
        if paciente_principal and pacientes_extra:
            pacientes_extra = pacientes_extra.exclude(pk=paciente_principal.pk)
        return pacientes_extra

    def clean(self):
        cleaned_data = super().clean()

        # Cuando la edición llega como POST parcial (por ejemplo, solo cambia estatus),
        # conservamos los valores actuales en los campos obligatorios del modelo.
        if self.instance and self.instance.pk:
            campos_obligatorios = [
                'paciente',
                'fecha',
                'hora',
                'tipo_paciente',
                'consultorio',
                'servicio',
                'terapeuta',
            ]
            for field_name in campos_obligatorios:
                if cleaned_data.get(field_name) in (None, ''):
                    cleaned_data[field_name] = getattr(self.instance, field_name)

        terapeuta = cleaned_data.get('terapeuta')
        fecha = cleaned_data.get('fecha')
        hora = cleaned_data.get('hora')

        if terapeuta and fecha:
            bloqueo = obtener_bloqueo_terapeuta_en_fecha(terapeuta.id, fecha, hora)
            if bloqueo:
                mensaje = bloqueo.mensaje_bloqueo()
                self.add_error('fecha', mensaje)
                self.add_error('terapeuta', 'Este terapeuta tiene esa fecha bloqueada.')
                if hora:
                    self.add_error('hora', 'La hora seleccionada cae dentro de un bloqueo del terapeuta.')
                raise ValidationError(mensaje)

            # Validar horario y consultorio solo al CREAR citas nuevas.
            # Si el terapeuta no tiene ningún horario configurado, se permite agendar sin restricción.
            es_nueva = not (self.instance and self.instance.pk)
            tiene_horarios = Horario.objects.filter(terapeuta=terapeuta).exists()
            if hora and es_nueva and tiene_horarios:
                _DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
                _SEDES = dict(Horario.SEDE_CHOICES)
                dia_semana = fecha.weekday()
                horarios_dia = list(Horario.objects.filter(terapeuta=terapeuta, dia=dia_semana))
                if not horarios_dia:
                    msg = f'{terapeuta.nombre} no tiene horario configurado los {_DIAS[dia_semana]}.'
                    self.add_error('fecha', msg)
                    self.add_error('hora', msg)
                    raise ValidationError(msg)
                horario_activo = next(
                    (h for h in horarios_dia if h.hora_inicio <= hora < h.hora_fin), None
                )
                if not horario_activo:
                    msg = (
                        f'Las {hora.strftime("%H:%M")} está fuera del horario de '
                        f'{terapeuta.nombre} los {_DIAS[dia_semana]}.'
                    )
                    self.add_error('hora', msg)
                    raise ValidationError(msg)

                # Validar que el consultorio coincida con la sede del horario activo
                consultorio = cleaned_data.get('consultorio')
                if horario_activo.sede and consultorio and consultorio.sede:
                    if consultorio.sede != horario_activo.sede:
                        sede_terapeuta = _SEDES.get(horario_activo.sede, horario_activo.sede)
                        sede_consultorio = _SEDES.get(consultorio.sede, consultorio.sede)
                        msg = (
                            f'{terapeuta.nombre} trabaja en {sede_terapeuta} a esa hora, '
                            f'pero el consultorio "{consultorio}" pertenece a {sede_consultorio}.'
                        )
                        self.add_error('consultorio', msg)
                        return cleaned_data  # add_error invalida el form; no duplicar en __all__

        return cleaned_data


class BloqueoAgendaTerapeutaForm(forms.ModelForm):
    class Meta:
        model = BloqueoAgendaTerapeuta
        fields = ['tipo_bloqueo', 'alcance', 'fecha_inicio', 'fecha_fin', 'dia_semana', 'hora_inicio', 'hora_fin', 'motivo']
        widgets = {
            'tipo_bloqueo': forms.Select(attrs={'class': 'form-select'}),
            'alcance': forms.Select(attrs={'class': 'form-select'}),
            'fecha_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'dia_semana': forms.Select(attrs={'class': 'form-select'}),
            'hora_inicio': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'hora_fin': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'motivo': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Ej. vacaciones, incapacidad, curso, bloqueo indefinido',
                }
            ),
        }
        labels = {
            'tipo_bloqueo': 'Tipo de bloqueo',
            'alcance': 'Aplicar a',
            'fecha_inicio': 'Fecha inicial',
            'fecha_fin': 'Fecha final',
            'dia_semana': 'Día semanal',
            'hora_inicio': 'Hora inicial',
            'hora_fin': 'Hora final',
            'motivo': 'Motivo',
        }


class NotaTerapeutaPacienteForm(forms.ModelForm):
    class Meta:
        model = NotaTerapeutaPaciente
        fields = ['notas']
        widgets = {
            'notas': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 8,
                    'placeholder': 'Escribe notas clínicas, seguimiento, acuerdos o recordatorios para este paciente.',
                }
            )
        }
        labels = {
            'notas': 'Notas del terapeuta',
        }


class DocumentoPacienteForm(forms.ModelForm):
    archivo = forms.FileField(
        label='Archivo',
        widget=forms.FileInput(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = DocumentoPaciente
        fields = ['tipo_documento', 'descripcion']
        widgets = {
            'tipo_documento': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Descripcion opcional del documento',
                }
            ),
        }
        labels = {
            'tipo_documento': 'Tipo de documento',
            'descripcion': 'Descripcion',
        }


# =============================================================================
# FORMULARIOS DE TABULADORES (Misión 2)
# =============================================================================

class TabuladorGeneralForm(forms.ModelForm):
    class Meta:
        model = TabuladorGeneral
        fields = [
            "descripcion",
            "pago_base",
            "pago_consultorio_propio",
            "bono_monto",
            "bono_umbral_pacientes",
        ]
        widgets = {
            "descripcion": forms.Textarea(attrs={
                "class": "form-control", "rows": 2,
            }),
            "pago_base": forms.NumberInput(attrs={
                "class": "form-control", "step": "0.01", "min": "0",
            }),
            "pago_consultorio_propio": forms.NumberInput(attrs={
                "class": "form-control", "step": "0.01", "min": "0",
            }),
            "bono_monto": forms.NumberInput(attrs={
                "class": "form-control", "step": "0.01", "min": "0",
            }),
            "bono_umbral_pacientes": forms.NumberInput(attrs={
                "class": "form-control", "min": "1", "step": "1",
            }),
        }
        labels = {
            "descripcion":             "Perfil / Descripción",
            "pago_base":               "Pago Base (consultorio INTRA)",
            "pago_consultorio_propio": "Pago Consultorio Propio",
            "bono_monto":              "Monto del Bono",
            "bono_umbral_pacientes":   "Meta de Pacientes para Bono",
        }


class ReglaTerapeutaForm(forms.ModelForm):
    class Meta:
        model = ReglaTerapeuta
        fields = [
            "pago_por_sesion",
            "pago_individual",
            "pago_pareja",
            "pago_consultorio_propio",
            "bono_umbral_monto",
            "bono_umbral_pacientes",
            "bono_por_paciente",
            "notas",
        ]
        widgets = {
            "pago_por_sesion": forms.NumberInput(attrs={
                "class": "form-control", "step": "0.01", "min": "0",
            }),
            "pago_individual": forms.NumberInput(attrs={
                "class": "form-control", "step": "0.01", "min": "0",
            }),
            "pago_pareja": forms.NumberInput(attrs={
                "class": "form-control", "step": "0.01", "min": "0",
            }),
            "pago_consultorio_propio": forms.NumberInput(attrs={
                "class": "form-control", "step": "0.01", "min": "0",
            }),
            "bono_umbral_monto": forms.NumberInput(attrs={
                "class": "form-control", "step": "0.01", "min": "0",
            }),
            "bono_umbral_pacientes": forms.NumberInput(attrs={
                "class": "form-control", "min": "1", "step": "1",
            }),
            "bono_por_paciente": forms.NumberInput(attrs={
                "class": "form-control", "step": "0.01", "min": "0",
            }),
            "notas": forms.Textarea(attrs={
                "class": "form-control", "rows": 2,
            }),
        }
        labels = {
            "pago_por_sesion":       "Pago por Sesión (tarifa plana)",
            "pago_individual":       "Pago Sesión Individual",
            "pago_pareja":           "Pago Sesión Pareja / Familiar",
            "pago_consultorio_propio": "Pago Consultorio Propio",
            "bono_umbral_monto":     "Monto del Bono (umbral)",
            "bono_umbral_pacientes": "Meta de Pacientes para Bono",
            "bono_por_paciente":     "Bono por Paciente (supervisor)",
            "notas":                 "Notas Operativas",
        }


_TEXTAREA = lambda placeholder, rows=4: forms.Textarea(attrs={
    'class': 'form-control', 'rows': rows, 'placeholder': placeholder,
})


class ReporteSesionForm(forms.ModelForm):
    class Meta:
        model = ReporteSesion
        fields = [
            'fecha',
            'hora_inicio',
            'hora_fin',
            'objetivo_sesion',
            'revision_tareas',
            'desarrollo_sesion',
            'tecnicas_utilizadas',
            'resultados_sesion',
            'tareas',
            'comentarios_finales',
        ]
        widgets = {
            'fecha': forms.DateInput(
                format='%Y-%m-%d',
                attrs={
                    'class': 'form-control',
                    'type': 'date',
                }
            ),
            'hora_inicio': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time',
            }),
            'hora_fin': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time',
            }),
            'objetivo_sesion':     _TEXTAREA('Describe el objetivo principal de la sesión...', 4),
            'revision_tareas':     _TEXTAREA('Revisión de tareas o actividades asignadas en la sesión anterior...', 4),
            'desarrollo_sesion':   _TEXTAREA('Describe el desarrollo y dinámica de la sesión...', 5),
            'tecnicas_utilizadas': _TEXTAREA('Técnicas, herramientas o enfoques utilizados...', 4),
            'resultados_sesion':   _TEXTAREA('Resultados obtenidos, avances y observaciones...', 4),
            'tareas':              _TEXTAREA('Tareas o actividades asignadas para la próxima sesión...', 3),
            'comentarios_finales': _TEXTAREA('Comentarios finales, observaciones del terapeuta...', 3),
        }
        labels = {
            'fecha':               'Fecha',
            'hora_inicio':         'Hora de inicio',
            'hora_fin':            'Hora de finalización',
            'objetivo_sesion':     'Objetivo de la sesión',
            'revision_tareas':     'Revisión de tareas',
            'desarrollo_sesion':   'Desarrollo de sesión',
            'tecnicas_utilizadas': 'Técnicas utilizadas',
            'resultados_sesion':   'Resultados de la sesión',
            'tareas':              'Tareas',
            'comentarios_finales': 'Comentarios Finales',
        }


class AperturaExpedienteForm(forms.ModelForm):
    nombre = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Nombre(s)',
    )
    fecha_nacimiento = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Fecha de Nacimiento',
    )
    telefono = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'WhatsApp'}),
        label='Celular',
    )

    VIVE_CON_CHOICES = [
        ('Padres',    'Padres'),
        ('Familiares','Familiares'),
        ('Solo(a)',   'Solo(a)'),
        ('Familia',   'Familia'),
        ('Esposo(a)', 'Esposo(a)'),
        ('Novio(a)',  'Novio(a)'),
        ('Cónyuge',  'Cónyuge'),
    ]

    vive_con_sel = forms.MultipleChoiceField(
        choices=VIVE_CON_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Vive con',
    )

    class Meta:
        model = AperturaExpediente
        exclude = ['paciente', 'documento', 'vive_con', 'creado_en', 'actualizado_en']
        widgets = {
            'expediente_no':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. 001'}),
            'apellido_paterno':     forms.HiddenInput(),
            'apellido_materno':     forms.HiddenInput(),
            'ocupacion':            forms.TextInput(attrs={'class': 'form-control'}),
            'lugar_de_trabajo':     forms.TextInput(attrs={'class': 'form-control'}),
            'cargo':                forms.TextInput(attrs={'class': 'form-control'}),
            'estado_civil':         forms.Select(attrs={'class': 'form-select'}),
            'calle':                forms.TextInput(attrs={'class': 'form-control'}),
            'num_exterior':         forms.TextInput(attrs={'class': 'form-control'}),
            'colonia':              forms.TextInput(attrs={'class': 'form-control'}),
            'division':             forms.Select(attrs={'class': 'form-select'}),
            'tiene_hijos':          forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'num_hijos':            forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'hijo_1':               forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre y edad'}),
            'hijo_2':               forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre y edad'}),
            'hijo_3':               forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre y edad'}),
            'hijo_4':               forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre y edad'}),
            'religion':             forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Opcional'}),
            'motivo_consulta':      forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'emergencia_contacto':  forms.TextInput(attrs={'class': 'form-control'}),
            'emergencia_telefono':  forms.TextInput(attrs={'class': 'form-control'}),
            'como_se_entero':       forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nombre'].label = 'Nombre completo'
        self.fields['apellido_paterno'].required = False
        self.fields['apellido_materno'].required = False
        if self.instance.pk and self.instance.paciente_id:
            self.fields['nombre'].initial = self.instance.paciente.nombre
            self.fields['fecha_nacimiento'].initial = self.instance.paciente.fecha_nacimiento
            self.fields['telefono'].initial = self.instance.paciente.telefono
        if self.instance.pk and self.instance.vive_con:
            self.fields['vive_con_sel'].initial = [
                v.strip() for v in self.instance.vive_con.split(',') if v.strip()
            ]

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.vive_con = ', '.join(self.cleaned_data.get('vive_con_sel', []))
        if commit:
            instance.save()
        return instance


# =============================================================================
# FORMULARIOS EMPRESA
# =============================================================================

class PacienteEmpresaForm(forms.ModelForm):
    """Formulario simplificado para que una Empresa registre nuevos pacientes."""
    class Meta:
        model = Paciente
        fields = ['nombre', 'fecha_nacimiento', 'sexo', 'telefono', 'identidad_contacto', 'servicio_inicial']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre completo'}),
            'fecha_nacimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'sexo': forms.Select(attrs={'class': 'form-select'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'WhatsApp'}),
            'identidad_contacto': forms.Select(attrs={'class': 'form-select'}),
            'servicio_inicial': forms.Select(attrs={'class': 'form-select'}),
        }


class CitaEmpresaForm(forms.ModelForm):
    """Formulario para que una Empresa agende citas directamente."""

    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa = empresa
        if empresa is not None:
            self.fields['paciente'].queryset = empresa.pacientes.all().order_by('nombre')
            if empresa.division:
                self.fields['division'].initial = empresa.division
                self.fields['division'].widget = forms.HiddenInput()

    def clean_division(self):
        # Si la empresa tiene división fija, siempre la usamos (ignorar lo que venga del POST)
        if self.empresa and self.empresa.division:
            return self.empresa.division
        return self.cleaned_data.get('division')

    class Meta:
        model = Cita
        fields = ['paciente', 'terapeuta', 'fecha', 'hora', 'tipo_paciente', 'consultorio', 'division', 'servicio']
        widgets = {
            'paciente': forms.Select(attrs={'class': 'form-select'}),
            'terapeuta': forms.Select(attrs={'class': 'form-select'}),
            'fecha': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'hora': forms.HiddenInput(),
            'tipo_paciente': forms.Select(attrs={'class': 'form-select'}),
            'consultorio': forms.Select(attrs={'class': 'form-select'}),
            'division': forms.Select(attrs={'class': 'form-select'}),
            'servicio': forms.Select(attrs={'class': 'form-select'}),
        }
