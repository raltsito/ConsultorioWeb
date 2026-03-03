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
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre completo', 'autocomplete': 'name'}),
            'fecha_nacimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'WhatsApp'}),
            'identidad_contacto': forms.Select(attrs={'class': 'form-select'}),
            'servicio_inicial': forms.Select(attrs={'class': 'form-select'}),
            
            'consentimiento_firmado': forms.FileInput(attrs={'class': 'form-control'}),
            'estudio_socioeconomico': forms.FileInput(attrs={'class': 'form-control'}),
            'apertura_expediente': forms.FileInput(attrs={'class': 'form-control'}),
            'resumen_clinico': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Notas privadas del terapeuta...'}),
            'enlace_resultados': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            
            'pacientes_relacionados': forms.SelectMultiple(attrs={
                'class': 'form-control select2-multiple',
                'style': 'width: 100%',
                'multiple': 'multiple'
            }), 
        }
    
    def clean_nombre(self):
        """Asegurar que el nombre se guarde correctamente con UTF-8"""
        nombre = self.cleaned_data.get('nombre', '')
        if nombre:
            # Conversiones precisas de caracteres corruptos
            conversiones = {
                'Ã¡': 'á', 'Ã©': 'é', 'Ã­': 'í', 'Ã³': 'ó', 'Ãš': 'ú', 'Ã¼': 'ü', 'Ã±': 'ñ',
                'Ã': 'Á', 'Ã©': 'É', 'Ã­': 'Í', 'Ã³': 'Ó', 'ÃŠ': 'Ú', 'Ã': 'Ñ',
                'Ý': 'í', 'ý': 'y', '┴': 'á', '┬': 'á', 'Á': 'á', '·': 'i', 'ß': 'a', '¾': 'ó',
                'º': '', 'ª': '', 'Â': '', 'Ã': '', 'â€™': "'",
            }
            conversiones_ord = sorted(conversiones.items(), key=lambda x: len(x[0]), reverse=True)
            for corrupto, correcto in conversiones_ord:
                nombre = nombre.replace(corrupto, correcto)
            
            # Garantizar UTF-8
            try:
                nombre = nombre.encode('utf-8').decode('utf-8')
            except (UnicodeDecodeError, UnicodeEncodeError):
                try:
                    nombre = nombre.encode('latin1').decode('utf-8')
                except:
                    pass
        
        return ' '.join(nombre.split()).strip() if nombre else ''

class CitaForm(forms.ModelForm):
    pacientes = forms.ModelMultipleChoiceField(
        queryset=Paciente.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Seleccionar Pacientes"
    )
    
    class Meta:
        model = Cita
        fields = [
            'pacientes', 'fecha', 'hora', 'division', 
            'consultorio', 'servicio', 'terapeuta', 
            'costo', 'metodo_pago', 'estatus', 
            'folio_fiscal', 'notas'
        ]
        
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'hora': forms.TimeInput(format='%H:%M', attrs={'type': 'time', 'class': 'form-control'}),
            'notas': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
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