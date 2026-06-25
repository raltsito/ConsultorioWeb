import openpyxl
from django.core.management.base import BaseCommand
from clinica.models import Instrumento, PreguntaInstrumento

RUTA_DEFAULT = r"C:\Users\RocioMc\PROYECTOINTRA\TCI.xlsx"
class Command(BaseCommand):
    help = 'Carga el instrumento TCI desde su archivo Excel'

    def add_arguments(self, parser):
        parser.add_argument('--ruta', default=RUTA_DEFAULT, help='Ruta al .xlsx del TCI')

    def _texto(self, header):
        if not header: return None
        return str(header).split('|')[0].strip() or None

    def handle(self, *args, **options):
        ruta = options['ruta']
        self.stdout.write(f'Abriendo: {ruta}')
        wb = openpyxl.load_workbook(ruta, data_only=True)
        ws = wb['DTCI'] # Nombre de la hoja de calculo como esta guardado en Excel.
        headers = [cell.value for cell in ws[1]]
              

        # Rango de preguntas en Excel
        preguntas_raw = headers[8:108] 

       
        ins, created = Instrumento.objects.update_or_create(
            clave='tci',
            defaults={
                'nombre': 'TCI (Temperament and Character Inventory)',
                'descripcion': 'Inventario de temperamento y carácter de Cloninger.',
                'instrucciones': (
                    "Este registro de opiniones tiene como misión poner de manifiesto sus ideas "
                    "auto-limitadoras particulares que contribuyen, de forma encubierta, a su estrés "
                    "e infelicidad. No es necesario que pienses mucho tiempo en cada pregunta. "
                    "Escribe rápidamente la respuesta y pasa a la siguiente. Asegúrate de que "
                    "contestes lo que realmente piensas, no lo que crees que deberías pensar."
                ),
                'activo': True,
            },
        )
        
        accion = 'Creado' if created else 'Actualizado'
        ins.preguntas.all().delete()

        # Definimos las opciones de respuesta según el formato S/N
        opciones = [
            {'valor': '1', 'etiqueta': 'Estoy de acuerdo (S)'},
            {'valor': '0', 'etiqueta': 'No estoy de acuerdo (N)'},
        ]

        nuevas = [
            PreguntaInstrumento(
                instrumento=ins, orden=i,
                texto=self._texto(h),
                tipo_respuesta=PreguntaInstrumento.TIPO_SI_NO, 
                opciones=opciones,
                requerida=True,
            )
            for i, h in enumerate(preguntas_raw, 1)
            if self._texto(h)
        ]
        
        PreguntaInstrumento.objects.bulk_create(nuevas)
        self.stdout.write(self.style.SUCCESS(f' TCI [{accion}]: {len(nuevas)} preguntas cargadas.'))