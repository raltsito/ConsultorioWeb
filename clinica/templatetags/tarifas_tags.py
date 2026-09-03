from django import template


register = template.Library()


@register.simple_tag
def notificaciones_tarifas_no_leidas(usuario):
    if not usuario.is_authenticated:
        return 0
    return usuario.notificaciones_tarifas.filter(leida_en__isnull=True).count()
