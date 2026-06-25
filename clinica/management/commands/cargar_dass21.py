import openpyxl
from django.core.management.base import BaseCommand
from clinica.models import Instrumento, PreguntaInstrumento

RUTA_DEFAULT = r"C:\Users\RocioMc\PROYECTOINTRA\DASS-21.xlsx"
class Command(BaseCommand):
    help = 'Carga el instrumento DASS-21 desde su archivo Excel'

    def add_arguments(self, parser):
        parser.add_argument('--ruta', default=RUTA_DEFAULT, help='Ruta al .xlsx del DASS-21')

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
        preguntas_raw = headers[5:26] 
       

        ins, created = Instrumento.objects.update_or_create(
            clave='dass-21',
            defaults={
                'nombre': 'DASS-21(Escala de Depresión, Ansiedad y Estrés)',
                
               'instrucciones': (          
                "Por favor, lea las siguientes afirmaciones e indique en qué grado "
                "le ha ocurrido a usted esta afirmación durante la semana pasada.\n\n"
                "La escala de calificación es la siguiente:\n"
                "0: No me ha ocurrido\n"
                "1: Me ha ocurrido un poco, o durante parte del tiempo\n"
                "2: Me ha ocurrido bastante, o durante una buena parte del tiempo\n"
                "3: Me ha ocurrido mucho, o la mayor parte del tiempo"
        ),
                'activo': True,
            },
        )
        
        accion = 'Creado' if created else 'Actualizado'        
        ins.preguntas.all().delete()

        # Definimos las opciones de respuesta para la escala de frecuencia
        opciones = [
        {'valor': '0', 'etiqueta': '0: No me ha ocurrido'},
        {'valor': '1', 'etiqueta': '1: Me ha ocurrido un poco, o durante parte del tiempo'},
        {'valor': '2', 'etiqueta': '2: Me ha ocurrido bastante, o durante una buena parte del tiempo'},
        {'valor': '3', 'etiqueta': '3: Me ha ocurrido mucho, o la mayor parte del tiempo'},
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
        self.stdout.write(self.style.SUCCESS(f' DASS-21 [{accion}]: {len(nuevas)} preguntas cargadas.'))