from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Captador, CodigoCaptacion


@receiver(post_save, sender=Captador)
def crear_codigo_inicial(sender, instance, created, **kwargs):
    if created and not instance.codigos.exists():
        CodigoCaptacion.objects.create(captador=instance)
