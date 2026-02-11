from django import forms
from .models import Paciente, Cita

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
        fields = ['fecha', 'hora', 'division', 'consultorio', 'servicio', 'terapeuta', 'costo', 'metodo_pago', 'estatus', 'folio_fiscal', 'notas']
        widgets = {
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'hora': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'division': forms.Select(attrs={'class': 'form-select'}),
            'consultorio': forms.Select(attrs={'class': 'form-select'}),
            'servicio': forms.Select(attrs={'class': 'form-select'}),
            'terapeuta': forms.Select(attrs={'class': 'form-select'}),
            'costo': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '500.00'}),
            'metodo_pago': forms.Select(attrs={'class': 'form-select'}),
            'estatus': forms.Select(attrs={'class': 'form-select'}),
            'folio_fiscal': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Opcional'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }