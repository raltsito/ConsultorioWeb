from ventas.models import Captador


def captador_es_terapeuta(captador):
    """Indica si un captador interno tiene un perfil clínico real."""
    if captador.tipo != Captador.TIPO_INTERNO or not captador.usuario_id:
        return False
    return hasattr(captador.usuario, "perfil_terapeuta")


def captador_es_elegible_para_liquidacion(captador):
    """Clasifica los captadores incluidos en Fase 7, sin consultar grupos."""
    if captador.tipo in (Captador.TIPO_EXTERNO, Captador.TIPO_EMPRESA):
        return True
    if captador.tipo == Captador.TIPO_INTERNO:
        return not captador_es_terapeuta(captador)
    return False


def clasificacion_captador_liquidacion(captador):
    if captador.tipo == Captador.TIPO_INTERNO:
        return "Usuario interno no clínico"
    if captador.tipo == Captador.TIPO_EMPRESA:
        return "Empresa"
    if captador.tipo == Captador.TIPO_EXTERNO:
        return captador.get_tipo_organizacion_display()
    return "Sin clasificación"
