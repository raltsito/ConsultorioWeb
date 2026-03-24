from django import forms
from django.core.exceptions import ValidationError

from .models import (
    BloqueoAgendaTerapeuta,
    Cita,
    NotaTerapeutaPaciente,
    Paciente,
    ReglaTerapeuta,
    TabuladorGeneral,
    obtener_bloqueo_terapeuta_en_fecha,
)


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
            'fecha_nacimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
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
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
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
