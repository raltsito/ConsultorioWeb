from django import forms
from django.contrib.auth import get_user_model

from clinica.models import Empresa, Paciente

from .models import Captador, ComisionCaptacion, LiquidacionComisiones
from .queries import comisiones_disponibles_para_liquidacion
from .services import buscar_codigo_captacion, evaluar_elegibilidad_captacion


class CaptadorForm(forms.ModelForm):
    class Meta:
        model = Captador
        fields = [
            "tipo",
            "usuario",
            "empresa",
            "nombre_externo",
            "tipo_organizacion",
            "contacto",
            "correo",
            "telefono",
        ]
        widgets = {
            "tipo": forms.Select(attrs={"class": "form-select", "data-captador-tipo": ""}),
            "usuario": forms.Select(attrs={"class": "form-select"}),
            "empresa": forms.Select(attrs={"class": "form-select"}),
            "nombre_externo": forms.TextInput(attrs={"class": "form-control"}),
            "tipo_organizacion": forms.Select(attrs={"class": "form-select"}),
            "contacto": forms.TextInput(attrs={"class": "form-control"}),
            "correo": forms.EmailInput(attrs={"class": "form-control"}),
            "telefono": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        self.fields["usuario"].queryset = User.objects.filter(
            is_active=True
        ).order_by("username")
        self.fields["empresa"].queryset = Empresa.objects.filter(
            activo=True
        ).order_by("nombre")
        self.fields["usuario"].required = False
        self.fields["empresa"].required = False
        self.fields["tipo_organizacion"].required = False

    def clean(self):
        datos = super().clean()
        tipo = datos.get("tipo")
        if tipo == Captador.TIPO_INTERNO:
            datos["empresa"] = None
            datos["nombre_externo"] = ""
            datos["tipo_organizacion"] = ""
        elif tipo == Captador.TIPO_EMPRESA:
            datos["usuario"] = None
            datos["nombre_externo"] = ""
            datos["tipo_organizacion"] = ""
        elif tipo == Captador.TIPO_EXTERNO:
            datos["usuario"] = None
            datos["empresa"] = None
        return datos


class CaptadorEditarForm(forms.ModelForm):
    class Meta:
        model = Captador
        fields = ["contacto", "correo", "telefono"]
        widgets = {
            "contacto": forms.TextInput(attrs={"class": "form-control"}),
            "correo": forms.EmailInput(attrs={"class": "form-control"}),
            "telefono": forms.TextInput(attrs={"class": "form-control"}),
        }


class DesactivarCaptadorForm(forms.Form):
    motivo = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )


class ValidarCodigoForm(forms.Form):
    codigo = forms.CharField(
        max_length=64,
        strip=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "off",
                "placeholder": "Código de captación",
            }
        ),
    )


class CaptacionForm(forms.Form):
    paciente = forms.ModelChoiceField(
        queryset=Paciente.objects.none(),
        widget=forms.Select(attrs={"class": "form-select select2-paciente"}),
        label="Paciente",
    )
    codigo = forms.CharField(
        max_length=64,
        strip=True,
        label="Código de captación",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "off",
                "placeholder": "Introduce el código del QR",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["paciente"].queryset = Paciente.objects.order_by("nombre")
        self.codigo_validado = None

    def clean_paciente(self):
        paciente = self.cleaned_data["paciente"]
        resultado = evaluar_elegibilidad_captacion(paciente)
        if not resultado.elegible:
            raise forms.ValidationError(resultado.mensaje)
        return paciente

    def clean_codigo(self):
        token = self.cleaned_data["codigo"]
        codigo, estado = buscar_codigo_captacion(token)
        if estado == "inactivo":
            raise forms.ValidationError(
                "Este captador está inactivo y no puede generar nuevas captaciones."
            )
        if estado != "valido":
            raise forms.ValidationError("Código de captación no válido.")
        self.codigo_validado = codigo
        return token


class AprobarCaptacionForm(forms.Form):
    porcentaje_comision = forms.IntegerField(
        min_value=1,
        max_value=10,
        label="Porcentaje de comisión",
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "min": 1,
                "max": 10,
                "step": 1,
            }
        ),
    )


class RechazarCaptacionForm(forms.Form):
    motivo_rechazo = forms.CharField(
        required=True,
        strip=True,
        label="Motivo del rechazo",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
            }
        ),
    )


class SeleccionComisionesLiquidacionForm(forms.Form):
    comisiones = forms.ModelMultipleChoiceField(
        queryset=ComisionCaptacion.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        error_messages={
            "required": "Selecciona al menos una comisión.",
            "invalid_choice": "Una comisión seleccionada ya no está disponible.",
        },
    )

    def __init__(self, *args, captador=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["comisiones"].queryset = (
            comisiones_disponibles_para_liquidacion(captador=captador)
        )


class MotivoRetiroComisionForm(forms.Form):
    motivo = forms.CharField(
        strip=True,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )


class CancelarBorradorLiquidacionForm(forms.Form):
    motivo = forms.CharField(
        strip=True,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )


class RegistrarPagoLiquidacionForm(forms.Form):
    metodo_pago = forms.ChoiceField(
        choices=LiquidacionComisiones.METODO_PAGO_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Método de pago",
    )
    referencia = forms.CharField(
        max_length=200,
        strip=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="Referencia",
    )
