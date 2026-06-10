"""Carga las preguntas del Raven SPM desde el export de Forminator.

Cada pregunta almacena la ruta a su imagen de matriz y la clave de respuesta
correcta dentro del JSONField `opciones` (campo `"correcta": true`).

Uso:
    python manage.py cargar_raven
    python manage.py cargar_raven --ruta "C:/ruta/al/export.txt"
"""
import json
import re

from django.core.management.base import BaseCommand

from clinica.models import Instrumento, PreguntaInstrumento

RUTA_DEFAULT = r'C:\Users\carlo\Downloads\forminator-3-raven-psi-form-export.txt'
IMG_DIR = 'instrumentos/raven'   # relativo a MEDIA_ROOT


class Command(BaseCommand):
    help = 'Carga preguntas del Raven SPM desde el export Forminator'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ruta', default=RUTA_DEFAULT,
            help='Ruta al .txt (JSON export de Forminator)',
        )

    def handle(self, *args, **options):
        ruta = options['ruta']
        self.stdout.write(f'Abriendo: {ruta}')

        with open(ruta, encoding='utf-8') as f:
            data = json.load(f)

        fields = data['data']['fields']

        ins, created = Instrumento.objects.update_or_create(
            clave='raven',
            defaults={
                'nombre': 'Raven — Matrices Progresivas (SPM)',
                'descripcion': (
                    'Test no verbal de inteligencia fluida. '
                    'Evalúa la capacidad para deducir relaciones y completar patrones '
                    'a través de 60 ítems organizados en 5 series (A–E).'
                ),
                'instrucciones': (
                    'A continuación verás una serie de figuras con una parte faltante. '
                    'Observa el patrón y selecciona la opción (1–6 u 1–8) que completa '
                    'correctamente cada figura.'
                ),
                'activo': True,
            },
        )
        accion = 'Creado' if created else 'Actualizado'
        ins.preguntas.all().delete()

        # Index radio fields (item 1 = radio-1, ..., item 60 = radio-60)
        radio_map = {
            int(f['id'].split('-')[1]): f
            for f in fields
            if f['type'] == 'radio' and re.match(r'^radio-\d+$', f['id'])
        }

        # Index html fields by group — take the one with an <img> src
        html_by_group = {}
        for f in fields:
            if f['type'] != 'html' or not f.get('parent_group'):
                continue
            m = re.search(r'src="([^"]+\.png[^"]*)"', f.get('variations', ''), re.IGNORECASE)
            if m:
                gnum = int(f['parent_group'].split('-')[1])
                html_by_group[gnum] = m.group(1)

        nuevas = []
        for item_num in range(1, 61):
            radio = radio_map.get(item_num)
            if not radio:
                self.stdout.write(self.style.WARNING(f'  radio-{item_num} no encontrado, omitido'))
                continue

            img_url = html_by_group.get(item_num, '')
            img_filename = f'{item_num}.png'
            img_path = f'{IMG_DIR}/{img_filename}'

            raw_opts = radio.get('options', [])
            opciones = []
            for opt in raw_opts:
                opciones.append({
                    'valor':    opt['value'],
                    'etiqueta': opt.get('label', opt['value']),
                    'correcta': str(opt.get('calculation', '0')) == '1',
                })

            # Label del set (A=1-12, B=13-24, C=25-36, D=37-48, E=49-60)
            set_letra = 'ABCDE'[(item_num - 1) // 12]
            set_pos   = ((item_num - 1) % 12) + 1

            nuevas.append(PreguntaInstrumento(
                instrumento=ins,
                orden=item_num,
                texto=f'Serie {set_letra}, lámina {set_pos}',
                tipo_respuesta=PreguntaInstrumento.TIPO_IMAGEN_UNICA,
                imagen=img_path,
                opciones=opciones,
                requerida=True,
            ))

        PreguntaInstrumento.objects.bulk_create(nuevas)
        self.stdout.write(
            self.style.SUCCESS(
                f'  Raven [{accion}]: {len(nuevas)} preguntas cargadas.'
            )
        )
