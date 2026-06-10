"""Carga preguntas del Allport Study of Values desde el export de Forminator.

Uso:
    python manage.py cargar_allport
    python manage.py cargar_allport --ruta "C:/ruta/al/export.txt"
"""
import json
import re
from collections import defaultdict

from html.parser import HTMLParser

from django.core.management.base import BaseCommand

from clinica.models import Instrumento, PreguntaInstrumento

RUTA_DEFAULT = r'C:\Users\carlo\Downloads\forminator-1-allport-psi-form-export.txt'


class _StripHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, d):
        if d.strip():
            self.parts.append(d.strip())

    def get_text(self):
        return ' '.join(self.parts)


def _strip(html):
    p = _StripHTML()
    p.feed(html)
    return p.get_text()


def _extract_options(text):
    """Split 'pregunta? a) optA b) optB c) optC d) optD' into {'a':..,'b':..,'c':..,'d':..}."""
    parts = re.split(r'\s+([abcd])\)', text)
    if len(parts) < 9:
        return {}
    result = {}
    for i in range(1, len(parts) - 1, 2):
        result[parts[i].lower()] = parts[i + 1].strip()
    return result


class Command(BaseCommand):
    help = 'Carga preguntas del Allport Study of Values desde el export Forminator'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ruta', default=RUTA_DEFAULT,
            help='Ruta al archivo .txt (JSON export de Forminator)',
        )

    def handle(self, *args, **options):
        ruta = options['ruta']
        self.stdout.write(f'Abriendo: {ruta}')

        with open(ruta, encoding='utf-8') as f:
            data = json.load(f)

        fields = data['data']['fields']

        # Index fields by parent group
        by_group = defaultdict(list)
        for field in fields:
            g = field.get('parent_group')
            if g:
                by_group[g].append(field)

        ins, created = Instrumento.objects.update_or_create(
            clave='allport',
            defaults={
                'nombre': 'Allport — Estudio de Valores',
                'descripcion': (
                    'Instrumento de Allport, Vernon y Lindzey que evalúa seis valores '
                    'fundamentales: Teórico, Económico, Estético, Social, Político y Religioso.'
                ),
                'instrucciones': (
                    'Este cuestionario consta de dos secciones. '
                    'En la primera (30 reactivos) elija entre dos alternativas A y B según su preferencia. '
                    'En la segunda (16 reactivos) asigne los valores 4, 3, 2 y 1 a las cuatro opciones '
                    'según su importancia personal (4 = más importante, 1 = menos importante).'
                ),
                'activo': True,
            },
        )
        accion = 'Creado' if created else 'Actualizado'
        ins.preguntas.all().delete()

        nuevas = []
        nuevas += self._secccion1(by_group)
        nuevas += self._seccion2(by_group)

        for p in nuevas:
            p.instrumento = ins
        PreguntaInstrumento.objects.bulk_create(nuevas)
        self.stdout.write(
            self.style.SUCCESS(
                f'  Allport [{accion}]: {len(nuevas)} preguntas cargadas '
                f'(S1={sum(1 for p in nuevas if p.orden <= 30)}, '
                f'S2={sum(1 for p in nuevas if p.orden > 30)}).'
            )
        )

    # ── Sección 1 (30 reactivos, elección forzada A/B) ────────────────────────

    def _secccion1(self, by_group):
        opciones_s1 = [
            {'valor': '3', 'etiqueta': 'De acuerdo con la alternativa A, en desacuerdo con la B'},
            {'valor': '2', 'etiqueta': 'Ligera preferencia por la alternativa A sobre la B'},
            {'valor': '1', 'etiqueta': 'Ligera preferencia por la alternativa B sobre la A'},
            {'valor': '0', 'etiqueta': 'De acuerdo con la alternativa B, en desacuerdo con la A'},
        ]
        preguntas = []
        for item_num in range(1, 31):
            gname = f'group-{item_num}'
            html_fields = [f for f in by_group[gname] if f['type'] == 'html']
            if not html_fields:
                self.stdout.write(self.style.WARNING(f'  S1 grupo {gname}: sin html, omitido'))
                continue
            texto = _strip(html_fields[0].get('variations', ''))
            preguntas.append(PreguntaInstrumento(
                instrumento=None,  # asignado en bulk
                orden=item_num,
                texto=texto,
                tipo_respuesta=PreguntaInstrumento.TIPO_OPCION_UNICA,
                opciones=opciones_s1,
                requerida=True,
            ))
        return preguntas

    # ── Sección 2 (16 reactivos × 4 opciones = 64 sub-preguntas) ─────────────

    def _seccion2(self, by_group):
        opciones_s2 = [
            {'valor': '4', 'etiqueta': '4 (más importante)'},
            {'valor': '3', 'etiqueta': '3'},
            {'valor': '2', 'etiqueta': '2'},
            {'valor': '1', 'etiqueta': '1 (menos importante)'},
        ]

        # Collect S2 groups and sort by first radio number
        s2_entries = []
        for gname, gfields in by_group.items():
            parts = gname.split('-')
            if len(parts) != 2 or not parts[1].isdigit():
                continue
            if int(parts[1]) < 31:
                continue
            radio_fields = sorted(
                [f for f in gfields if f['type'] == 'radio'],
                key=lambda x: int(x['id'].split('-')[1]),
            )
            if not radio_fields:
                continue
            first_radio_num = int(radio_fields[0]['id'].split('-')[1])
            s2_entries.append((first_radio_num, gname, radio_fields, gfields))

        s2_entries.sort(key=lambda x: x[0])

        preguntas = []
        for item_idx, (_, gname, radio_fields, gfields) in enumerate(s2_entries, 1):
            html_fields = [f for f in gfields if f['type'] == 'html']
            question_html = [
                f for f in html_fields
                if 'En cada pregunta asigne' not in _strip(f.get('variations', ''))
            ]
            item_full_text = _strip(question_html[0].get('variations', '')) if question_html else ''

            # Separate the item question from the embedded option texts
            # item_full_text = "1.- ¿Pregunta? a) opA b) opB c) opC d) opD"
            # Extract just the question (before the first option letter)
            m = re.search(r'^(.+?)\s+[abcd]\)', item_full_text)
            item_titulo = m.group(1).strip() if m else item_full_text
            opts = _extract_options(item_full_text)

            grupo_clave = f'allport_s2_{item_idx}'

            for radio in radio_fields:
                letter = radio.get('field_label', '?').rstrip(')')  # 'a)' → 'a'
                radio_num = int(radio['id'].split('-')[1])
                opt_text = opts.get(letter, f'Opción {letter}')
                preguntas.append(PreguntaInstrumento(
                    instrumento=None,
                    orden=radio_num,
                    texto=f'{letter}) {opt_text}',
                    clave=grupo_clave,
                    titulo_grupo=item_titulo,
                    tipo_respuesta=PreguntaInstrumento.TIPO_OPCION_UNICA,
                    opciones=opciones_s2,
                    requerida=True,
                ))
        return preguntas
