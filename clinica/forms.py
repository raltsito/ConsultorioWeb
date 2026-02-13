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
            # 👇 AGREGA EL FORMAT='%H:%M' AQUÍ
            'hora': forms.TimeInput(format='%H:%M', attrs={'type': 'time', 'class': 'form-control', 'step': '60'}),
            'notas': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'paciente': forms.Select(attrs={'class': 'form-select select2-paciente'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Bucle para estilos Bootstrap
        for field_name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                 field.widget.attrs['class'] = 'form-control'
        
        # 👇 AGREGA ESTO PARA FORZAR QUE SEAN OPCIONALES EN EL HTML
        self.fields['costo'].required = False
        self.fields['metodo_pago'].required = False

    def clean(self):
        cleaned_data = super().clean()
        
        # Obtenemos los datos del formulario
        fecha = cleaned_data.get('fecha')
        hora = cleaned_data.get('hora')
        consultorio = cleaned_data.get('consultorio')
        terapeuta = cleaned_data.get('terapeuta')
        paciente = cleaned_data.get('paciente')
        
        # 👇 ID DE LA CITA ACTUAL (Para excluirla si estamos editando)
        cita_id = self.instance.pk 

        if not (fecha and hora and consultorio and terapeuta and paciente):
            return # Si faltan datos obligatorios, dejamos que Django maneje sus errores

        # ---------------------------------------------------------
        # REGLA 1: DISPONIBILIDAD FÍSICA (El Consultorio) 🏢
        # ---------------------------------------------------------
        choque_consultorio = Cita.objects.filter(
            consultorio=consultorio, 
            fecha=fecha, 
            hora=hora,
            estatus='programada'
        ).exclude(pk=cita_id) # <--- EXCLUIMOS LA PROPIA CITA

        if choque_consultorio.exists():
            self.add_error('consultorio', f"El consultorio {consultorio} ya está ocupado a esa hora.")

        # ---------------------------------------------------------
        # REGLA 2: DISPONIBILIDAD HUMANA (El Terapeuta) 👨‍⚕️
        # ---------------------------------------------------------
        choque_terapeuta = Cita.objects.filter(
            terapeuta=terapeuta,
            fecha=fecha,
            hora=hora,
            estatus='programada'
        ).exclude(pk=cita_id) # <--- EXCLUIMOS LA PROPIA CITA

        if choque_terapeuta.exists():
            self.add_error('terapeuta', f"El terapeuta {terapeuta} ya tiene otra cita agendada a esta hora.")

        # ---------------------------------------------------------
        # REGLA 3: FRECUENCIA DEL PACIENTE (Regla de la Semana) 📅
        # ---------------------------------------------------------
        fecha_inicio = fecha - timedelta(days=6)
        fecha_fin = fecha + timedelta(days=6)

        citas_cercanas = Cita.objects.filter(
            paciente=paciente,
            fecha__range=[fecha_inicio, fecha_fin],
            estatus='programada'
        ).exclude(pk=cita_id) # <--- EXCLUIMOS LA PROPIA CITA

        if citas_cercanas.exists():
            # Construimos un string legible de las citas conflictivas
            citas_str = ", ".join([f"{c.fecha.strftime('%d/%m')}" for c in citas_cercanas])
            
            # NOTA: Si prefieres que esto sea solo una advertencia visual pero deje guardar,
            # comenta la línea 'raise ValidationError...'
            raise ValidationError(
                f"El paciente {paciente} ya tiene citas cercanas ({citas_str}). Política de 1 cita por semana."
            )
        
        return cleaned_data