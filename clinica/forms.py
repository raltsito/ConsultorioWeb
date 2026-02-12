from django import forms
from .models import Paciente, Cita
from django.core.exceptions import ValidationError
from datetime import timedelta

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
        
        # AQUÍ ESTÁ LA MAGIA DE LOS INPUTS 📅⏰
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'hora': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'notas': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            # Al paciente le ponemos una clase especial para detectarlo con JS luego
            'paciente': forms.Select(attrs={'class': 'form-select select2-paciente'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Bucle para poner estilos Bootstrap a lo que falte
        for field_name, field in self.fields.items():
            # Si ya tiene clase (como fecha o hora), la respetamos, si no, agregamos form-control
            if 'class' not in field.widget.attrs:
                 field.widget.attrs['class'] = 'form-control'

    from django import forms
from django.core.exceptions import ValidationError
from datetime import timedelta
from .models import Cita

class CitaForm(forms.ModelForm):
    # ... (Tu código Meta y widgets anterior se queda igual) ...
    class Meta:
        model = Cita
        fields = ['paciente', 'fecha', 'hora', 'division', 'consultorio', 'servicio', 'terapeuta', 'costo', 'metodo_pago', 'estatus', 'folio_fiscal', 'notas']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'hora': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'notas': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'paciente': forms.Select(attrs={'class': 'form-select select2-paciente'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        
        # Obtenemos los datos que el usuario intenta guardar
        fecha = cleaned_data.get('fecha')
        hora = cleaned_data.get('hora')
        consultorio = cleaned_data.get('consultorio')
        terapeuta = cleaned_data.get('terapeuta')
        paciente = cleaned_data.get('paciente')
        cita_id = self.instance.id # ID de la cita (si estamos editando)

        if not (fecha and hora and consultorio and terapeuta and paciente):
            return # Si faltan datos básicos, dejamos que Django lance sus propios errores

        # ---------------------------------------------------------
        # REGLA 1: DISPONIBILIDAD FÍSICA (El Consultorio) 🏢
        # ---------------------------------------------------------
        # Buscamos citas en el MISMO consultorio, MISMA fecha y hora
        choque_consultorio = Cita.objects.filter(
            consultorio=consultorio, 
            fecha=fecha, 
            hora=hora,
            estatus='programada' # Solo nos importan las activas
        ).exclude(id=cita_id) # Excluimos la cita actual si se está editando

        if choque_consultorio.exists():
            # Error específico al campo 'consultorio'
            self.add_error('consultorio', f"El consultorio {consultorio} ya está ocupado a esa hora.")

        # ---------------------------------------------------------
        # REGLA 2: DISPONIBILIDAD HUMANA (El Terapeuta) 👨‍⚕️
        # ---------------------------------------------------------
        # El terapeuta no puede estar en dos lugares a la vez
        choque_terapeuta = Cita.objects.filter(
            terapeuta=terapeuta,
            fecha=fecha,
            hora=hora,
            estatus='programada'
        ).exclude(id=cita_id)

        if choque_terapeuta.exists():
            self.add_error('terapeuta', f"El terapeuta {terapeuta} ya tiene otra cita agendada a esta hora.")

        # ---------------------------------------------------------
        # REGLA 3: FRECUENCIA DEL PACIENTE (Regla de la Semana) 📅
        # ---------------------------------------------------------
        # Verificar citas del paciente en un rango de +/- 6 días
        
        # Rango de fechas prohibidas (1 semana antes y 1 semana después)
        fecha_inicio = fecha - timedelta(days=6)
        fecha_fin = fecha + timedelta(days=6)

        citas_cercanas = Cita.objects.filter(
            paciente=paciente,
            fecha__range=[fecha_inicio, fecha_fin],
            estatus='programada'
        ).exclude(id=cita_id)

        if citas_cercanas.exists():
            citas_str = ", ".join([f"{c.fecha} ({c.terapeuta})" for c in citas_cercanas])
            # Esta es una regla estricta. Si quieres que sea solo advertencia, avísame.
            raise ValidationError(
                f"El paciente {paciente} ya tiene citas cercanas: {citas_str}. "
                "La política no permite citas en la misma semana."
            )
        
        return cleaned_data