import os

import openpyxl
from django.conf import settings
from django.core.management.base import BaseCommand
from clinica.models import Instrumento, PreguntaInstrumento

RUTA_DEFAULT = os.path.join(settings.BASE_DIR, 'docs_xslx_instrumentos', 'TDS.xlsx')
class Command(BaseCommand):
    help = 'Carga el instrumento TDS desde su archivo Excel'

    def add_arguments(self, parser):
        parser.add_argument('--ruta', default=RUTA_DEFAULT, help='Ruta al .xlsx del TDS')

    def _texto(self, header):
        if not header: return None
        return str(header).split('|')[0].strip() or None

    def handle(self, *args, **options):
        ruta = options['ruta']
        self.stdout.write(f'Abriendo: {ruta}')
        wb = openpyxl.load_workbook(ruta, data_only=True)
        ws = wb['DATOS'] # Nombre de la hoja de calculo como esta guardado en Excel.
        headers = [cell.value for cell in ws[1]]
        
    

        # Rango de preguntas en Excel
        preguntas_raw = headers[7:37] 
       

        ins, created = Instrumento.objects.update_or_create(
            clave='tds',
            defaults={
                'nombre': 'TDS (Trastornos del Sueño)',
                
               'instrucciones': (
                "Lea cada enunciado con atención y, pensando en cómo se ha sentido durante "
                "las últimas dos semanas, marque la opción que mejor describa su situación.\n\n"
                "La escala de calificación es la siguiente:\n"
                "0: Casi nunca\n"
                "1: Pocas veces\n"
                "2: Unas veces sí y otras no\n"
                "3: Muchas veces\n"
                "4: Casi siempre"
        ),
                'activo': True,
            },
        )
        
        accion = 'Creado' if created else 'Actualizado'        
        ins.preguntas.all().delete()

        # Definimos las opciones de respuesta para la escala de frecuencia
        opciones = [
            {'valor': '0', 'etiqueta': '0: Casi nunca'},
            {'valor': '1', 'etiqueta': '1: Pocas veces'},
            {'valor': '2', 'etiqueta': '2: Unas veces sí y otras no'},
            {'valor': '3', 'etiqueta': '3: Muchas veces'},
            {'valor': '4', 'etiqueta': '4: Casi siempre'},
        ]

        nuevas = [
            PreguntaInstrumento(
                instrumento=ins, 
                orden=i,
                texto=self._texto(h),
                tipo_respuesta=PreguntaInstrumento.TIPO_ESCALA, 
                opciones=opciones,
                requerida=True,
            )
            for i, h in enumerate(preguntas_raw, 1)
            if self._texto(h)
        ]
        
        PreguntaInstrumento.objects.bulk_create(nuevas)
        self.stdout.write(self.style.SUCCESS(f' TDS [{accion}]: {len(nuevas)} preguntas cargadas.'))