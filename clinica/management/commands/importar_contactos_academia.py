"""Importa los alumnos de Academia (diplomados) desde el Excel de inscripciones,
para poder enviarles campañas masivas de WhatsApp.

Uso:
    python manage.py importar_contactos_academia --archivo "C:\\ruta\\bddo.xlsx"
    python manage.py importar_contactos_academia --archivo bddo.xlsx --dry-run

Formato esperado (hoja "Inscripciones detalladas" del archivo bddo.xlsx):
encabezados en la fila 3, datos desde la fila 4, con las columnas
"Año fuente | Diplomado | Nombre | Teléfono | Correo | Fecha inscripción |
 Matrícula | Estatus origen | Observaciones origen | Fila en archivo original".
Las columnas se buscan por nombre de encabezado, no por posición.

Idempotente: identifica al contacto por su teléfono normalizado a 10 dígitos
(update_or_create), así que se puede correr varias veces sin duplicar. Una misma
persona inscrita en varios diplomados produce UN ContactoAcademia y varias
InscripcionAcademia — enviarle la campaña una sola vez es intencional.
"""
import os
import unicodedata
from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from clinica.models import ContactoAcademia, InscripcionAcademia

# Encabezado del Excel -> campo lógico. Se comparan normalizados (sin acentos,
# minúsculas) para que un "Telefono" sin acento también haga match.
COLUMNAS = {
    'ano fuente': 'anio_fuente',
    'diplomado': 'diplomado',
    'nombre': 'nombre',
    'telefono': 'telefono',
    'correo': 'correo',
    'fecha inscripcion': 'fecha_inscripcion',
    'matricula': 'matricula',
    'estatus origen': 'estatus',
    'observaciones origen': 'observaciones',
    'fila en archivo original': 'fila_origen',
}

ESTATUS_MAP = {
    'activo': InscripcionAcademia.ESTATUS_ACTIVO,
    'inactivo': InscripcionAcademia.ESTATUS_INACTIVO,
    'por confirmar': InscripcionAcademia.ESTATUS_POR_CONFIRMAR,
}


def _normalizar(texto) -> str:
    """minúsculas, sin acentos y sin espacios sobrantes — para comparar encabezados."""
    s = str(texto or '').strip().lower()
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')


def _telefono_10(valor) -> str:
    """
    Deja el teléfono en los 10 dígitos que usa la BD (mismo criterio que
    services_whatsapp.buscar_paciente_por_wa_id, que hace match por los últimos 10).
    Devuelve '' si no hay dígitos suficientes.
    """
    # openpyxl puede entregar el teléfono como número si la celda es numérica.
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    digitos = ''.join(c for c in str(valor or '') if c.isdigit())
    if len(digitos) < 10:
        return ''
    return digitos[-10:]


def _fecha(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return None


class Command(BaseCommand):
    help = 'Importa contactos e inscripciones de Academia desde el Excel de inscripciones detalladas'

    def add_arguments(self, parser):
        parser.add_argument('--archivo', required=True, help='Ruta al .xlsx de inscripciones')
        parser.add_argument('--hoja', default='', help='Nombre de la hoja (default: la primera)')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Analiza el archivo y reporta, sin escribir nada en la base de datos.',
        )

    def handle(self, *args, **options):
        try:
            import openpyxl
        except ImportError:
            raise CommandError('Falta openpyxl. Instálalo con: pip install openpyxl')

        self._reportar_base_de_datos()

        ruta = options['archivo']
        if not os.path.exists(ruta):
            raise CommandError(f'No existe el archivo: {ruta}')

        libro = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
        hoja = libro[options['hoja']] if options['hoja'] else libro.worksheets[0]

        filas = list(hoja.iter_rows(values_only=True))
        indices, fila_encabezado = self._localizar_encabezados(filas)

        registros, descartados = self._leer_filas(filas, fila_encabezado, indices)

        if not registros:
            raise CommandError('No se encontró ninguna fila con nombre y teléfono válidos.')

        self._reportar_lectura(registros, descartados)

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('\n--dry-run: no se escribió nada en la base de datos.'))
            return

        creados, actualizados, inscripciones_nuevas = self._guardar(registros)

        self.stdout.write(self.style.SUCCESS(
            f'\nListo. Contactos creados: {creados} | actualizados: {actualizados} | '
            f'inscripciones nuevas: {inscripciones_nuevas}'
        ))
        self.stdout.write(
            f'Total de contactos en la base: {ContactoAcademia.objects.count()} '
            f'({ContactoAcademia.objects.filter(suscrito=True).count()} suscritos)'
        )

    def _reportar_base_de_datos(self):
        """
        Deja clarísimo contra qué base se va a escribir.

        settings usa dj_database_url con fallback a SQLite: si DATABASE_URL no
        llega (p. ej. se corrió sin `railway run`), la importación entraría en
        la base local sin avisar y parecería que ya está en producción.
        """
        config = connection.settings_dict
        motor = config['ENGINE'].rsplit('.', 1)[-1]

        if motor == 'sqlite3':
            self.stdout.write(self.style.WARNING(
                f'BASE DE DATOS: SQLite LOCAL ({config["NAME"]})\n'
                'Si esperabas producción, el comando debe correrse con `railway run` '
                'para que DATABASE_URL apunte a Postgres.\n'
            ))
        else:
            destino = config.get('HOST') or 'desconocido'
            self.stdout.write(self.style.SUCCESS(
                f'BASE DE DATOS: {motor} en {destino} — base "{config.get("NAME")}"\n'
            ))

    def _localizar_encabezados(self, filas):
        """
        Busca la fila de encabezados en las primeras 10 filas (en bddo.xlsx está en
        la 3 porque arriba hay un título y una fila vacía) y mapea columna -> índice.
        """
        for i, fila in enumerate(filas[:10]):
            encontrados = {}
            for j, celda in enumerate(fila):
                campo = COLUMNAS.get(_normalizar(celda))
                if campo:
                    encontrados[campo] = j
            if {'nombre', 'telefono', 'diplomado'} <= set(encontrados):
                return encontrados, i
        raise CommandError(
            'No se encontró la fila de encabezados. Se esperan al menos las columnas '
            '"Nombre", "Teléfono" y "Diplomado" en las primeras 10 filas.'
        )

    def _leer_filas(self, filas, fila_encabezado, indices):
        def valor(fila, campo):
            j = indices.get(campo)
            return fila[j] if j is not None and j < len(fila) else None

        registros, descartados = [], []
        for numero, fila in enumerate(filas[fila_encabezado + 1:], start=fila_encabezado + 2):
            nombre = str(valor(fila, 'nombre') or '').strip()
            if not nombre:
                continue

            telefono = _telefono_10(valor(fila, 'telefono'))
            if not telefono:
                descartados.append((numero, nombre, 'sin teléfono válido'))
                continue

            anio = valor(fila, 'anio_fuente')
            try:
                anio = int(anio)
            except (TypeError, ValueError):
                descartados.append((numero, nombre, 'año fuente inválido'))
                continue

            fila_origen = valor(fila, 'fila_origen')
            try:
                fila_origen = int(fila_origen)
            except (TypeError, ValueError):
                fila_origen = None

            registros.append({
                'fila_excel': numero,
                'nombre': nombre,
                'telefono': telefono,
                'correo': str(valor(fila, 'correo') or '').strip(),
                'diplomado': str(valor(fila, 'diplomado') or '').strip() or 'SIN DIPLOMADO',
                'anio_fuente': anio,
                'estatus': ESTATUS_MAP.get(
                    _normalizar(valor(fila, 'estatus')), InscripcionAcademia.ESTATUS_POR_CONFIRMAR
                ),
                'matricula': str(valor(fila, 'matricula') or '').strip(),
                'fecha_inscripcion': _fecha(valor(fila, 'fecha_inscripcion')),
                'observaciones': str(valor(fila, 'observaciones') or '').strip(),
                'fila_origen': fila_origen,
            })

        return registros, descartados

    def _reportar_lectura(self, registros, descartados):
        telefonos = {r['telefono'] for r in registros}
        self.stdout.write(f'Filas válidas leídas: {len(registros)}')
        self.stdout.write(f'Contactos únicos por teléfono: {len(telefonos)}')

        por_estatus = {}
        for r in registros:
            por_estatus[r['estatus']] = por_estatus.get(r['estatus'], 0) + 1
        self.stdout.write('Inscripciones por estatus: ' + ', '.join(
            f'{k}={v}' for k, v in sorted(por_estatus.items())
        ))

        if descartados:
            self.stdout.write(self.style.WARNING(f'\nFilas descartadas: {len(descartados)}'))
            for numero, nombre, motivo in descartados[:15]:
                self.stdout.write(f'  fila {numero}: {nombre} — {motivo}')
            if len(descartados) > 15:
                self.stdout.write(f'  ... y {len(descartados) - 15} más')

    @transaction.atomic
    def _guardar(self, registros):
        creados = actualizados = inscripciones_nuevas = 0
        vistos = set()

        for r in registros:
            telefono = r['telefono']
            if telefono in vistos:
                # Ya se creó/actualizó el contacto con la primera fila de esta
                # persona; el nombre de las filas siguientes puede variar
                # (abreviado, con typo) y se ignora a propósito.
                contacto = ContactoAcademia.objects.get(telefono=telefono)
            else:
                contacto, creado = ContactoAcademia.objects.update_or_create(
                    telefono=telefono,
                    defaults={'nombre': r['nombre'], 'correo': r['correo']},
                )
                creados += 1 if creado else 0
                actualizados += 0 if creado else 1
                vistos.add(telefono)

            _, nueva = InscripcionAcademia.objects.update_or_create(
                contacto=contacto,
                diplomado=r['diplomado'],
                anio_fuente=r['anio_fuente'],
                defaults={
                    'estatus': r['estatus'],
                    'matricula': r['matricula'],
                    'fecha_inscripcion': r['fecha_inscripcion'],
                    'observaciones': r['observaciones'],
                    'fila_origen': r['fila_origen'],
                },
            )
            inscripciones_nuevas += 1 if nueva else 0

        return creados, actualizados, inscripciones_nuevas
