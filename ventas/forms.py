from django import forms
from django.contrib.auth import get_user_model

from clinica.models import Empresa, Paciente

from .models import (
    Captador,
    ComisionCaptacion,
    ConvenioEmpresa,
    LiquidacionComisiones,
)
from .queries import comisiones_disponibles_para_liquidacion
from .services import buscar_codigo_captacion, evaluar_elegibilidad_captacion


class CaptadorForm(forms.ModelForm):
    EMPRESA_NUEVA = "empresa_nueva"

    tipo = forms.ChoiceField(
        choices=[
            (Captador.TIPO_INTERNO, "Usuario interno"),
            (Captador.TIPO_EMPRESA, "Empresa existente"),
            (EMPRESA_NUEVA, "Empresa nueva"),
            (Captador.TIPO_EXTERNO, "Organización externa"),
        ],
        widget=forms.Select(
            attrs={"class": "form-select", "data-captador-tipo": ""}
        ),
    )
    empresa_nueva_nombre = forms.CharField(
        required=False,
        label="Nombre de la empresa",
        strip=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    # RECUPERACIÓN CAPTACIÓN / QR: configuración de comisión
    porcentaje_comision = forms.IntegerField(
        min_value=0,
        max_value=10,
        label="Porcentaje de comisión",
        help_text=(
            "0 % configura el código sin comisión; "
            "1–10 % configura una comisión."
        ),
        widget=forms.NumberInput(
            attrs={"class": "form-control", "min": 0, "max": 10, "step": 1}
        ),
    )

    class Meta:
        model = Captador
        fields = [
            "tipo",
            "usuario",
            "empresa",
            "empresa_nueva_nombre",
            "nombre_externo",
            "tipo_organizacion",
            "contacto",
            "correo",
            "telefono",
            "porcentaje_comision",
        ]
        widgets = {
            "usuario": forms.Select(attrs={"class": "form-select"}),
            "empresa": forms.Select(attrs={"class": "form-select"}),
            "nombre_externo": forms.TextInput(attrs={"class": "form-control"}),
            "tipo_organizacion": forms.Select(attrs={"class": "form-select"}),
            "contacto": forms.TextInput(attrs={"class": "form-control"}),
            "correo": forms.EmailInput(attrs={"class": "form-control"}),
            "telefono": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        datos = kwargs.get("data")
        datos_en_args = bool(args)
        if datos is None and datos_en_args:
            datos = args[0]
        if datos and datos.get("tipo") == self.EMPRESA_NUEVA:
            datos = datos.copy()
            datos["empresa"] = ""
            if datos_en_args:
                args = (datos, *args[1:])
            else:
                kwargs["data"] = datos
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
        self.empresa_nueva_solicitada = tipo == self.EMPRESA_NUEVA
        if self.empresa_nueva_solicitada:
            nombre = datos.get("empresa_nueva_nombre", "").strip()
            datos["tipo"] = Captador.TIPO_EMPRESA
            datos["empresa"] = None
            datos["usuario"] = None
            datos["nombre_externo"] = ""
            datos["tipo_organizacion"] = ""
            datos["empresa_nueva_nombre"] = nombre
            if not nombre:
                self.add_error(
                    "empresa_nueva_nombre",
                    "Indica el nombre de la empresa.",
                )
            elif Empresa.objects.filter(nombre__iexact=nombre).exists():
                self.add_error(
                    "empresa_nueva_nombre",
                    (
                        "Ya existe una empresa con este nombre. "
                        "Selecciona Empresa existente."
                    ),
                )
            return datos

        if tipo == Captador.TIPO_INTERNO:
            datos["empresa"] = None
            datos["empresa_nueva_nombre"] = ""
            datos["nombre_externo"] = ""
            datos["tipo_organizacion"] = ""
        elif tipo == Captador.TIPO_EMPRESA:
            datos["usuario"] = None
            datos["empresa_nueva_nombre"] = ""
            datos["nombre_externo"] = ""
            datos["tipo_organizacion"] = ""
        elif tipo == Captador.TIPO_EXTERNO:
            datos["usuario"] = None
            datos["empresa"] = None
            datos["empresa_nueva_nombre"] = ""
        return datos

    def _post_clean(self):
        super()._post_clean()
        if getattr(self, "empresa_nueva_solicitada", False):
            self._errors.pop("empresa", None)


class CaptadorEditarForm(forms.ModelForm):
    class Meta:
        model = Captador
        fields = ["contacto", "correo", "telefono"]
        widgets = {
            "contacto": forms.TextInput(attrs={"class": "form-control"}),
            "correo": forms.EmailInput(attrs={"class": "form-control"}),
            "telefono": forms.TextInput(attrs={"class": "form-control"}),
        }


class ConfigurarComisionCaptadorForm(forms.Form):
    # RECUPERACIÓN CAPTACIÓN / QR: configuración de comisión
    porcentaje_comision = forms.IntegerField(
        min_value=0,
        max_value=10,
        label="Porcentaje de comisión",
        help_text=(
            "0 % configura el código sin comisión; "
            "1–10 % configura una comisión."
        ),
        widget=forms.NumberInput(
            attrs={"class": "form-control", "min": 0, "max": 10, "step": 1}
        ),
    )


class DesactivarCaptadorForm(forms.Form):
    motivo = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )


class ConvenioEmpresaForm(forms.ModelForm):
    class Meta:
        model = ConvenioEmpresa
        fields = [
            "activo",
            "vigencia_desde",
            "vigencia_hasta",
            "modalidad",
            "quien_paga",
            "limite_consultas_mensual",
            "monto_mensual",
            "pase_requiere_identificador",
            "consultas_por_pase",
            "observaciones",
        ]

        labels = {
            "vigencia_desde": "Vigente desde",
            "vigencia_hasta": "Vigente hasta",
            "limite_consultas_mensual": "Consultas incluidas por mes",
            "monto_mensual": "Monto mensual acordado",
            "pase_requiere_identificador": (
                "¿Los pases utilizan folio o identificador?"
            ),
            "consultas_por_pase": "Consultas autorizadas por pase",
            "observaciones": "Observaciones",
        }

        widgets = {
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "vigencia_desde": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "vigencia_hasta": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "modalidad": forms.Select(attrs={"class": "form-select"}),
            "quien_paga": forms.Select(attrs={"class": "form-select"}),
            "limite_consultas_mensual": forms.NumberInput(
                attrs={"class": "form-control", "min": 1}
            ),
            "monto_mensual": forms.NumberInput(
                attrs={"class": "form-control", "min": 0, "step": "0.01"}
            ),
            "pase_requiere_identificador": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "consultas_por_pase": forms.NumberInput(
                attrs={"class": "form-control", "min": 1}
            ),
            "observaciones": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
        }

    def clean(self):
        datos = super().clean()
        modalidad = datos.get("modalidad")

        if modalidad == ConvenioEmpresa.MODALIDAD_PAQUETE_MENSUAL:
            datos["pase_requiere_identificador"] = False
            datos["consultas_por_pase"] = None

        elif modalidad == ConvenioEmpresa.MODALIDAD_PASE:
            datos["limite_consultas_mensual"] = None
            datos["monto_mensual"] = None

        elif modalidad in {
            ConvenioEmpresa.MODALIDAD_TARIFA_ESPECIAL,
            ConvenioEmpresa.MODALIDAD_DESCUENTO_PORCENTAJE,
        }:
            datos["limite_consultas_mensual"] = None
            datos["monto_mensual"] = None
            datos["pase_requiere_identificador"] = False
            datos["consultas_por_pase"] = None

        return datos


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
        min_value=0,
        max_value=10,
        label="Porcentaje de comisión",
        help_text=(
            "0 % aprueba la captación sin comisión; "
            "1–10 % aprueba una comisión."
        ),
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "min": 0,
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
