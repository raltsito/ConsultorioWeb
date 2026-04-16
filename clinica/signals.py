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
