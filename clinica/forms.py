from django import forms
from .models import Paciente, Cita
from django.core.exceptions import ValidationError
from datetime import timedelta
from .models import Cita
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
    class Meta:
        model = Cita
        fields = [
            'paciente', 'fecha', 'hora', 'division', 
            'consultorio', 'servicio', 'terapeuta', 
            'costo', 'metodo_pago', 'estatus', 
            'folio_fiscal', 'notas'
        ]
        
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'hora': forms.TimeInput(format='%H:%M', attrs={'type': 'time', 'class': 'form-control'}),
            'notas': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'paciente': forms.Select(attrs={'class': 'form-select select2-paciente'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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

    ##def clean(self):
        ##cleaned_data = super().clean()
        
        # Validaciones restrictivas eliminadas. 
        # El sistema ahora permite agendar y empalmar citas sin bloqueos.
        
        ##return cleaned_data