from decimal import Decimal
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='clinica.Cita')
def crear_penalizacion_por_inasistencia(sender, instance, created, **kwargs):
    """
    Cuando una cita se guarda con estatus 'no_asistio', genera automáticamente
    una PenalizacionPaciente por el 50% del precio estándar del servicio.
    Solo crea la penalización si no existía ya (idempotente).
    """
    from clinica.models import PenalizacionPaciente

    if instance.estatus != 'no_asistio':
        return
    if instance.paciente_id is None:
        return

    # Evitar duplicados
    if hasattr(instance, 'penalizacion_generada'):
        return

    # Calcular monto: 50% del precio estándar del servicio.
    # Si el servicio no tiene precio configurado, no se genera penalización.
    if not instance.servicio or not instance.servicio.precio:
        return

    base = instance.servicio.precio
    monto = (base * Decimal("0.50")).quantize(Decimal("0.01"))

    PenalizacionPaciente.objects.create(
        paciente_id=instance.paciente_id,
        cita_origen=instance,
        monto=monto,
    )


@receiver(post_save, sender='clinica.Cita')
def pagar_penalizacion_al_terapeuta_si_asistio(sender, instance, created, **kwargs):
    """
    Cuando la cita de cobro de una penalización se marca como 'si_asistio',
    registra el pago al terapeuta en su nómina (50% de su tarifa de sesión).
    Es idempotente: verifica que no exista ya una LineaNomina para esa cita origen.
    """
    if instance.estatus != 'si_asistio':
        return

    from clinica.models import PenalizacionPaciente, LineaNomina
    from clinica.services import registrar_pago_penalizacion_terapeuta

    penalizaciones = PenalizacionPaciente.objects.filter(
        cita_cobro=instance,
        pagada=True,
    ).select_related('cita_origen__terapeuta', 'cita_origen__servicio', 'paciente')

    for pen in penalizaciones:
        ya_registrada = LineaNomina.objects.filter(
            tipo=LineaNomina.TIPO_PENALIZACION,
            cita=pen.cita_origen,
        ).exists()
        if not ya_registrada:
            try:
                registrar_pago_penalizacion_terapeuta(pen)
            except Exception:
                pass
