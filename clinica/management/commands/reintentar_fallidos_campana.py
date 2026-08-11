"""Devuelve a 'pendiente' los envíos fallidos de una campaña para reintentarlos.

No manda nada por sí solo: solo reabre los envíos. Una vez reabiertos, el botón
"Reanudar" del panel de Mensajes Masivos aparece en el historial de esa campaña
y dispara el reintento por el mismo camino de siempre (lotes de 20, pausa entre
envíos, registro del código de error de cada uno).

Se hace así a propósito, en vez de reenviar desde el comando: el envío por lotes
ya está probado y es idempotente, y de este modo el reintento queda registrado
igual que el envío original.

Uso:
    python manage.py reintentar_fallidos_campana --id 8              # dry-run
    python manage.py reintentar_fallidos_campana --id 8 --confirmar
    python manage.py reintentar_fallidos_campana --id 8 --codigo 131000 --confirmar

Sin --confirmar no escribe nada: solo muestra qué reabriría.
"""
from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from clinica.models import CampanaMasiva, EnvioMasivo
# Mismo glosario que usa el reporte, para no mantener dos traducciones.
from clinica.management.commands.estado_campana_masiva import GLOSARIO_ERRORES

# Códigos donde el reintento tiene una posibilidad real: el fallo fue del lado
# de Meta o del momento, no del número. El resto se puede reintentar igual
# -el comando no lo impide-, pero lo normal es que falle idéntico.
VALE_LA_PENA_REINTENTAR = {'131000', '131047', '130429', '470', '131056'}


class Command(BaseCommand):
    help = 'Reabre los envíos fallidos de una campaña masiva para poder reintentarlos.'

    def add_arguments(self, parser):
        parser.add_argument('--id', type=int, required=True, help='ID de la campaña.')
        parser.add_argument('--codigo', action='append', dest='codigos',
                            help='Reabrir solo este código de error. Repetible.')
        parser.add_argument('--confirmar', action='store_true',
                            help='Sin esto el comando es de solo lectura.')

    def handle(self, *args, **opciones):
        campana = CampanaMasiva.objects.filter(pk=opciones['id']).first()
        if not campana:
            raise CommandError(f"No existe la campaña con id {opciones['id']}.")

        envios = campana.envios.filter(estado=EnvioMasivo.ESTADO_FALLIDO)
        if opciones['codigos']:
            envios = envios.filter(error_codigo__in=opciones['codigos'])
        envios = list(envios.select_related('contacto').order_by('contacto__nombre'))

        if not envios:
            self.stdout.write(self.style.WARNING(
                'No hay envíos fallidos que coincidan. Nada que reabrir.'))
            return

        self.stdout.write(self.style.MIGRATE_HEADING(f'\n{campana.nombre}'))
        self.stdout.write(f'  Plantilla: {campana.plantilla_meta}')
        self.stdout.write(f'  Fallidos que se reabrirían: {len(envios)}\n')

        for codigo, cuantos in Counter(e.error_codigo or '(sin código)' for e in envios).most_common():
            titulo = GLOSARIO_ERRORES.get(codigo, ('Error no catalogado', ''))[0]
            if codigo in VALE_LA_PENA_REINTENTAR:
                marca = self.style.SUCCESS('reintento con posibilidad real')
            else:
                marca = self.style.WARNING('lo más probable es que falle igual')
            self.stdout.write(f'  [{codigo}] x{cuantos} — {titulo}')
            self.stdout.write(f'      {marca}')

        if not opciones['confirmar']:
            self.stdout.write(self.style.WARNING(
                '\nDRY-RUN: no se escribió nada. Repite el comando con --confirmar.'))
            return

        with transaction.atomic():
            actualizados = EnvioMasivo.objects.filter(
                pk__in=[e.pk for e in envios],
                # Se revalida el estado dentro de la transacción por si un webhook
                # tardío de Meta cambió alguno entre la lectura y la escritura.
                estado=EnvioMasivo.ESTADO_FALLIDO,
            ).update(
                estado=EnvioMasivo.ESTADO_PENDIENTE,
                error_codigo='',
                error_mensaje='',
                respuesta_api=None,
                # 'enviado_en' se conserva a propósito: acota la bandeja de
                # respuestas al inicio real de la campaña (_mm_primer_envio_por_contacto).
                # Si el reintento funciona, enviar_lote lo sobrescribe.
            )

        self.stdout.write(self.style.SUCCESS(f'\n{actualizados} envíos reabiertos como pendientes.'))
        self.stdout.write(
            'Ahora entra al panel de Mensajes Masivos: en el historial, esa campaña '
            'ya muestra el botón "Reanudar". Solo se le escribirá a estos '
            f'{actualizados}; quienes ya recibieron el mensaje no se tocan.'
        )
