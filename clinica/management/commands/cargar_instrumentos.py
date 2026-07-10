"""Carga (o actualiza) los instrumentos clínicos desde el JSON de definiciones
versionado en el repo. Es el comando que se corre en producción: no depende de
archivos Excel ni exports locales.

Uso:
    python manage.py cargar_instrumentos                 # todos los instrumentos
    python manage.py cargar_instrumentos --claves scid2,scl90
    python manage.py cargar_instrumentos --forzar        # reconstruye aunque haya respuestas

Idempotente: identifica cada instrumento por `clave` (update_or_create). Si un
instrumento ya tiene respuestas de pacientes, NO reconstruye sus preguntas
(borrarlas eliminaría en cascada las respuestas) salvo que se pase --forzar.
"""
import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from clinica.models import Instrumento, PreguntaInstrumento, RespuestaInstrumento

RUTA_DEFAULT = os.path.join(
    settings.BASE_DIR, 'clinica', 'fixtures', 'instrumentos_definiciones.json'
)


class Command(BaseCommand):
    help = 'Carga los instrumentos clínicos desde clinica/fixtures/instrumentos_definiciones.json'

    def add_arguments(self, parser):
        parser.add_argument('--ruta', default=RUTA_DEFAULT, help='Ruta al JSON de definiciones')
        parser.add_argument('--claves', default='', help='Claves a cargar separadas por coma (default: todas)')
        parser.add_argument(
            '--forzar', action='store_true',
            help='Reconstruye las preguntas aunque el instrumento ya tenga respuestas de pacientes '
                 '(las respuestas existentes se BORRAN en cascada).',
        )

    def handle(self, *args, **options):
        ruta = options['ruta']
        if not os.path.exists(ruta):
            raise CommandError(f'No existe el archivo de definiciones: {ruta}')

        with open(ruta, encoding='utf-8') as f:
            definiciones = json.load(f)

        solo_claves = {c.strip() for c in options['claves'].split(',') if c.strip()}
        if solo_claves:
            desconocidas = solo_claves - {d['clave'] for d in definiciones}
            if desconocidas:
                raise CommandError(f'Claves no encontradas en el JSON: {", ".join(sorted(desconocidas))}')
            definiciones = [d for d in definiciones if d['clave'] in solo_claves]

        for definicion in definiciones:
            clave = definicion['clave']
            ins, created = Instrumento.objects.update_or_create(
                clave=clave,
                defaults={
                    'nombre': definicion['nombre'],
                    'descripcion': definicion.get('descripcion', ''),
                    'instrucciones': definicion.get('instrucciones', ''),
                    'activo': definicion.get('activo', True),
                },
            )
            accion = 'Creado' if created else 'Actualizado'

            tiene_respuestas = RespuestaInstrumento.objects.filter(
                pregunta__instrumento=ins
            ).exists()
            if tiene_respuestas and not options['forzar']:
                self.stdout.write(self.style.WARNING(
                    f'  {clave} [{accion}]: ya tiene respuestas de pacientes; '
                    f'se conservaron sus {ins.preguntas.count()} preguntas actuales '
                    f'(use --forzar para reconstruirlas, BORRA las respuestas).'
                ))
                continue

            ins.preguntas.all().delete()
            PreguntaInstrumento.objects.bulk_create([
                PreguntaInstrumento(
                    instrumento=ins,
                    orden=p['orden'],
                    texto=p['texto'],
                    clave=p.get('clave', ''),
                    tipo_respuesta=p['tipo_respuesta'],
                    opciones=p.get('opciones'),
                    imagen=p.get('imagen', ''),
                    titulo_grupo=p.get('titulo_grupo', ''),
                    requerida=p.get('requerida', True),
                )
                for p in definicion['preguntas']
            ])
            self.stdout.write(self.style.SUCCESS(
                f'  {clave} [{accion}]: {len(definicion["preguntas"])} preguntas cargadas.'
            ))

        # Los instrumentos de vista previa (demos de junio 2026) duplican nombres
        # del catálogo real; se desactivan para que no aparezcan en la UI.
        demos = Instrumento.objects.filter(clave__startswith='vista_previa', activo=True)
        n_demos = demos.update(activo=False)
        if n_demos:
            self.stdout.write(self.style.WARNING(
                f'  {n_demos} instrumentos de vista previa desactivados.'
            ))

        self.stdout.write(self.style.SUCCESS(f'Listo: {len(definiciones)} instrumentos procesados.'))
