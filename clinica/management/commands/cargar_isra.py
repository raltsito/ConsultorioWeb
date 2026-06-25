import openpyxl
from django.core.management.base import BaseCommand
from clinica.models import Instrumento, PreguntaInstrumento

RUTA_DEFAULT = r"C:\Users\RocioMc\PROYECTOINTRA\ISRA.xlsx"
class Command(BaseCommand):
    help = 'Carga el instrumento ISRA desde su archivo Excel'

    def add_arguments(self, parser):
        parser.add_argument('--ruta', default=RUTA_DEFAULT, help='Ruta al .xlsx del ISRA')

    def _texto(self, header):
        if not header: return None
        return str(header).split('|')[0].strip() or None

    def handle(self, *args, **options):
        ruta = options['ruta']
        self.stdout.write(f'Abriendo: {ruta}')
        wb = openpyxl.load_workbook(ruta, data_only=True)
        ws = wb['DISRA'] # Nombre de la hoja de calculo como esta guardado en Excel.
        headers = [cell.value for cell in ws[1]]
        
    

        # Rango de preguntas en Excel
        preguntas_raw = headers[8:259] 
       

        ins, created = Instrumento.objects.update_or_create(
            clave='isra',
            defaults={
                'nombre': 'ISRA (Inventario de Situaciones y Respuestas de Ansiedad)',
                
               'instrucciones': ("En las páginas siguientes encontrará una serie de frases que presentan situaciones "
                "en que usted podría encontrarse y otras que se refieren a respuestas que usted "
                "podría dar ante esas situaciones o reacciones que le producirían.\n\n"
                "Su tarea consiste en valorar de 0 a 4 la frecuencia con que se da en usted cada "
                "respuesta o reacción que está considerando, según la siguiente escala:\n"
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
        self.stdout.write(self.style.SUCCESS(f' ISRA [{accion}]: {len(nuevas)} preguntas cargadas.'))