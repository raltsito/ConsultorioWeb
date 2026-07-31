"""Pruebas de los adjuntos de WhatsApp.

Correr con: python manage.py test clinica
"""
import io
from unittest import mock

from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
from django.test import SimpleTestCase

from clinica import services_whatsapp as wa


class SubirMediaTests(SimpleTestCase):
    """
    Regresión del error que salió en producción al mandar el primer adjunto:
    "a bytes-like object is required, not '_TemporaryFileWrapper'".

    Django guarda en disco los archivos que pasan de ~2.5 MB, y requests 2.34
    decide si leerlos con un isinstance contra un Protocol; esa comprobación usa
    inspect.getattr_static, que no ve el read() que _TemporaryFileWrapper delega
    por __getattr__. El objeto llegaba crudo a urllib3 y reventaba.

    Solo se reproduce en Linux con Python 3.13 (producción); en el Windows de
    desarrollo la clase temporal es otra y el bug no aparece. Por eso la prueba
    verifica lo que de verdad importa y es igual en todas las plataformas: que a
    requests siempre le lleguen bytes completos.
    """
    CONTENIDO = b'%PDF-1.4' + b'z' * 5000

    def _subir(self, archivo, nombre, mime):
        with mock.patch.object(wa.requests, 'post') as post:
            post.return_value.json.return_value = {'id': 'MID'}
            wa.subir_media(archivo, nombre, mime)
            return post.call_args.kwargs['files']['file'][1]

    def test_archivo_en_disco_se_manda_como_bytes(self):
        grande = TemporaryUploadedFile('grande.pdf', 'application/pdf', len(self.CONTENIDO), None)
        grande.write(self.CONTENIDO)
        grande.seek(0)

        enviado = self._subir(grande, 'grande.pdf', 'application/pdf')

        self.assertIsInstance(enviado, bytes)
        self.assertEqual(enviado, self.CONTENIDO)

    def test_archivo_ya_leido_se_rebobina(self):
        """Validar el archivo antes de subirlo no debe truncar lo que se manda."""
        grande = TemporaryUploadedFile('grande.pdf', 'application/pdf', len(self.CONTENIDO), None)
        grande.write(self.CONTENIDO)
        grande.seek(0)
        grande.read(10)

        self.assertEqual(self._subir(grande, 'grande.pdf', 'application/pdf'), self.CONTENIDO)

    def test_archivo_en_memoria_se_manda_como_bytes(self):
        chico = InMemoryUploadedFile(
            io.BytesIO(self.CONTENIDO), None, 'chico.png', 'image/png', len(self.CONTENIDO), None,
        )
        self.assertEqual(self._subir(chico, 'chico.png', 'image/png'), self.CONTENIDO)

    def test_bytes_directos_siguen_funcionando(self):
        self.assertEqual(
            self._subir(self.CONTENIDO, 'x.bin', 'application/octet-stream'), self.CONTENIDO,
        )


class ClasificacionMediaTests(SimpleTestCase):
    def test_tipo_para_mime(self):
        casos = {
            'image/png': 'image', 'image/jpeg': 'image',
            'video/mp4': 'video', 'audio/ogg': 'audio',
            # Lo que no cae en ninguna categoría conocida va como documento.
            'application/pdf': 'document', 'text/csv': 'document', '': 'document',
            'image/jpeg; charset=binary': 'image',  # con parámetros extra
        }
        for mime, esperado in casos.items():
            self.assertEqual(wa.tipo_para_mime(mime), esperado, msg=mime)

    def test_validar_media_respeta_limites(self):
        mb = 1024 * 1024
        self.assertIsNone(wa.validar_media('image', 4 * mb))
        self.assertIn('5 MB', wa.validar_media('image', 6 * mb))
        self.assertIsNone(wa.validar_media('document', 20 * mb))
        self.assertIn('25 MB', wa.validar_media('document', 30 * mb))
        self.assertIn('vacío', wa.validar_media('document', 0))
