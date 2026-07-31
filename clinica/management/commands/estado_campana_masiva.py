"""Muestra a quién SÍ se le envió una campaña masiva y a quién le falta.

Sirve cuando el navegador pierde la conexión a media campaña ("NetworkError when
attempting to fetch resource"): el bucle del panel muere, pero cada envío ya
quedó registrado en la base, así que desde aquí se ve el corte exacto.

Uso:
    python manage.py estado_campana_masiva                 # lista las campañas
    python manage.py estado_campana_masiva --id 3          # resumen de la campaña 3
    python manage.py estado_campana_masiva --id 3 --detalle
    python manage.py estado_campana_masiva --id 3 --detalle --csv salida.csv

No manda mensajes ni modifica nada: es solo lectura. Para reanudar el envío de
los pendientes, usa el botón "Reanudar" del panel de Mensajes Masivos.
"""
import csv

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from clinica.models import CampanaMasiva, EnvioMasivo


class Command(BaseCommand):
    help = 'Reporta enviados / fallidos / pendientes de una campaña masiva de WhatsApp.'

    def add_arguments(self, parser):
        parser.add_argument('--id', type=int, help='ID de la campaña. Sin esto, lista las campañas.')
        parser.add_argument('--detalle', action='store_true',
                            help='Imprime nombre y teléfono de cada destinatario.')
        parser.add_argument('--csv', dest='csv_path',
                            help='Escribe el detalle completo a un archivo CSV.')

    def handle(self, *args, **opciones):
        if not opciones['id']:
            self._listar_campanas()
            return

        campana = CampanaMasiva.objects.filter(pk=opciones['id']).first()
        if not campana:
            raise CommandError(f"No existe la campaña con id {opciones['id']}.")

        envios = list(
            campana.envios.select_related('contacto').order_by('contacto__nombre')
        )
        # Un solo recorrido: son ~250 filas, ya están en memoria.
        grupos = {clave: [] for clave, _ in EnvioMasivo.ESTADO_CHOICES}
        for envio in envios:
            grupos[envio.estado].append(envio)

        # 'enviado', 'entregado' y 'leido' son el mismo hecho para esta pregunta:
        # el mensaje ya salió y NO hay que volver a mandarlo.
        recibidos = (grupos[EnvioMasivo.ESTADO_ENVIADO]
                     + grupos[EnvioMasivo.ESTADO_ENTREGADO]
                     + grupos[EnvioMasivo.ESTADO_LEIDO])
        fallidos = grupos[EnvioMasivo.ESTADO_FALLIDO]
        pendientes = grupos[EnvioMasivo.ESTADO_PENDIENTE]

        self.stdout.write(self.style.MIGRATE_HEADING(f'\n{campana.nombre}'))
        self.stdout.write(f'  Plantilla : {campana.plantilla_meta}')
        self.stdout.write(f'  Estado    : {campana.get_estado_display()}')
        self.stdout.write(f'  Total     : {len(envios)}')
        self.stdout.write(self.style.SUCCESS(f'  Ya recibieron el mensaje : {len(recibidos)}'))
        self.stdout.write(self.style.ERROR(f'  Fallidos                 : {len(fallidos)}'))
        self.stdout.write(self.style.WARNING(f'  Pendientes (les falta)   : {len(pendientes)}'))

        ultimo = max((e.enviado_en for e in envios if e.enviado_en), default=None)
        if ultimo:
            self.stdout.write(f'  Último envío: {timezone.localtime(ultimo):%d/%m/%Y %H:%M:%S}')

        if opciones['detalle']:
            self._imprimir_grupo('YA RECIBIERON (no reenviar)', recibidos)
            self._imprimir_grupo('FALLIDOS (no se entregó)', fallidos)
            self._imprimir_grupo('PENDIENTES (les falta)', pendientes)

        if opciones['csv_path']:
            self._escribir_csv(opciones['csv_path'], envios)
            self.stdout.write(self.style.SUCCESS(f'\nCSV escrito en {opciones["csv_path"]}'))

        if pendientes:
            self.stdout.write(
                '\nPara enviarles SOLO a los pendientes, entra al panel de Mensajes '
                'Masivos y usa el botón "Reanudar" de esta campaña en el historial. '
                'No crees una campaña nueva: eso le volvería a escribir a quienes ya recibieron.'
            )

    def _listar_campanas(self):
        campanas = CampanaMasiva.objects.all()[:20]
        if not campanas:
            self.stdout.write('No hay campañas registradas.')
            return
        self.stdout.write(self.style.MIGRATE_HEADING('ID   Estado      Env/Tot   Campaña'))
        for c in campanas:
            total = c.envios.count()
            hechos = c.envios.exclude(estado=EnvioMasivo.ESTADO_PENDIENTE).count()
            self.stdout.write(f'{c.pk:<4} {c.estado:<11} {hechos:>3}/{total:<5} {c.nombre}')
        self.stdout.write('\nDetalle de una: --id <ID> --detalle')

    def _imprimir_grupo(self, titulo, envios):
        self.stdout.write(self.style.MIGRATE_HEADING(f'\n--- {titulo} ({len(envios)}) ---'))
        for e in envios:
            error = f'  [{e.error_codigo}] {e.error_mensaje}' if e.error_mensaje else ''
            self.stdout.write(f'  {e.contacto.nombre:<40} {e.telefono}{error}')

    def _escribir_csv(self, ruta, envios):
        with open(ruta, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow(['nombre', 'telefono', 'estado', 'enviado_en',
                        'error_codigo', 'error_mensaje', 'wa_message_id'])
            for e in envios:
                w.writerow([
                    e.contacto.nombre, e.telefono, e.get_estado_display(),
                    timezone.localtime(e.enviado_en).strftime('%d/%m/%Y %H:%M:%S') if e.enviado_en else '',
                    e.error_codigo, e.error_mensaje, e.wa_message_id,
                ])
