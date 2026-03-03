"""
Custom Django command para limpiar nombres con encoding corrompido
Uso: python manage.py sanar_nombres
"""
from django.core.management.base import BaseCommand
from clinica.models import Paciente, Terapeuta, Consultorio, Servicio, Division


def corregir_encoding(texto):
    """
    Corrige texto con encoding corrompido (Latin1 leído como UTF-8 doble)
    Mapea caracteres visuales corrompidos de forma inteligente
    """
    if not texto:
        return texto
    
    # **TABLA COMPLETA Y CORRECTA** de conversión
    # Los caracteres simples sucio son típicamente el resultado de:
    # utf8(iso-8859-1(original))
    
    conversiones_precisas = {
        # Caracteres acentuados básicos (reales caracteres corruptos)
        'Ã¡': 'á',   # á (e aguda minúscula)
        'Ã©': 'é',   # é (e aguda minúscula)
        'Ã­': 'í',   # í (i aguda minúscula)
        'Ã³': 'ó',   # ó (o aguda minúscula)
        'Ãš': 'ú',   # ú (u aguda minúscula)
        'Ã¼': 'ü',   # ü (u diéresis)
        'Ã±': 'ñ',   # ñ (n tilde)
        'Ã': 'Á',    # Á (A mayúscula aguda)
        'Ã©': 'É',   # É (E mayúscula aguda)
        'Ã­': 'Í',   # Í (I mayúscula aguda)
        'Ã³': 'Ó',   # Ó (O mayúscula aguda)
        'ÃŠ': 'Ú',   # Ú (U mayúscula aguda)
        'Ã': 'Ñ',    # Ñ (N mayúscula tilde)
        
        # Caracteres de representación visual confusa
        'Ý': 'í',    # Íor y con tilde → í
        'ý': 'y',    # y con tilde → y
        '┴': 'á',    # Glyph corrupto → á
        '┬': 'á',    # Glyph corrupto → á
        'Á': 'á',    # A aguda → á
        '·': 'i',    # Punto medio → i
        'ß': 'a',    # Eszett alemán → a (usado mal en español)
        '¾': 'ó',    # 3/4 → ó (parece por fuente)
        'º': '',     # Símbolo ordinal masculino → (quitar)
        'ª': '',     # Símbolo ordinal femenino → (quitar)
        
        # Caracteres de control y ruido
        'Â': '',     # Control → (quitar)
        'Ã': '',     # Control → (quitar)  
        'ÃÂ': '',    # Noise → (quitar)
        'Ã¢': '',    # Noise → (quitar)
        'â€™': "'",  # Comilla elegante → comilla normal
        'â€œ': '"',  # Comilla izquierda → comilla normal
        'â€\x9d': '"', # Comilla derecha → comilla normal
        
        # Letras con acentos/marcas dibujadas mal
        'CÃ³': 'Có',     # Patrón común
        'MÃ©ndez': 'Méndez',
        'DÃ­az': 'Díaz',
        'SÃ¡nchez': 'Sánchez',
        'RamÃ­rez': 'Ramírez',
        'GarcÃ­a': 'García',
        'FernÃ¡ndez': 'Fernández',
        'GÃ³mez': 'Gómez',
        'LÃ³pez': 'López',
        'PÃ©rez': 'Pérez',
    }
    
    resultado = texto
    
    # Aplicar conversiones precisas (long strings first)
    conversiones_ordenadas = sorted(conversiones_precisas.items(), 
                                    key=lambda x: len(x[0]), 
                                    reverse=True)
    
    for corrupto, correcto in conversiones_ordenadas:
        resultado = resultado.replace(corrupto, correcto)
    
    # Limpieza de espacios extras
    resultado = ' '.join(resultado.split())
    
    return resultado.strip()


class Command(BaseCommand):
    help = 'Limpia caracteres corrompidos en nombres de pacientes, terapeutas, consultorios y servicios'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Iniciando limpieza de caracteres corrompidos...\n'))
        
        contador = {
            'pacientes': 0,
            'terapeutas': 0,
            'consultorios': 0,
            'servicios': 0,
            'divisiones': 0
        }

        # Pacientes
        self.stdout.write('👥 Procesando PACIENTES...')
        for p in Paciente.objects.all():
            nombre_limpio = corregir_encoding(p.nombre)
            
            if nombre_limpio != p.nombre and nombre_limpio:
                self.stdout.write(f'   ✏️  {p.nombre} → {nombre_limpio}')
                p.nombre = nombre_limpio
                p.save()
                contador['pacientes'] += 1

        # Terapeutas
        self.stdout.write('\n👨‍⚕️  Procesando TERAPEUTAS...')
        for t in Terapeuta.objects.all():
            nombre_limpio = corregir_encoding(t.nombre)
            
            if nombre_limpio != t.nombre and nombre_limpio:
                self.stdout.write(f'   ✏️  {t.nombre} → {nombre_limpio}')
                t.nombre = nombre_limpio
                t.save()
                contador['terapeutas'] += 1

        # Consultorios
        self.stdout.write('\n🏥 Procesando CONSULTORIOS...')
        for c in Consultorio.objects.all():
            nombre_limpio = corregir_encoding(c.nombre)
            
            if nombre_limpio != c.nombre and nombre_limpio:
                self.stdout.write(f'   ✏️  {c.nombre} → {nombre_limpio}')
                c.nombre = nombre_limpio
                c.save()
                contador['consultorios'] += 1

        # Servicios
        self.stdout.write('\n🔧 Procesando SERVICIOS...')
        for s in Servicio.objects.all():
            nombre_limpio = corregir_encoding(s.nombre)
            
            if nombre_limpio != s.nombre and nombre_limpio:
                self.stdout.write(f'   ✏️  {s.nombre} → {nombre_limpio}')
                s.nombre = nombre_limpio
                s.save()
                contador['servicios'] += 1

        # Divisiones
        self.stdout.write('\n📂 Procesando DIVISIONES...')
        for d in Division.objects.all():
            nombre_limpio = corregir_encoding(d.nombre)
            
            if nombre_limpio != d.nombre and nombre_limpio:
                self.stdout.write(f'   ✏️  {d.nombre} → {nombre_limpio}')
                d.nombre = nombre_limpio
                d.save()
                contador['divisiones'] += 1

        # Resumen
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('✅ RESUMEN DE CORRECCIONES:'))
        self.stdout.write('='*50)
        self.stdout.write(f'👥 Pacientes arreglados:    {contador["pacientes"]}')
        self.stdout.write(f'👨‍⚕️  Terapeutas arreglados:   {contador["terapeutas"]}')
        self.stdout.write(f'🏥 Consultorios arreglados: {contador["consultorios"]}')
        self.stdout.write(f'🔧 Servicios arreglados:    {contador["servicios"]}')
        self.stdout.write(f'📂 Divisiones arregladas:   {contador["divisiones"]}')
        self.stdout.write('='*50)
        total = sum(contador.values())
        self.stdout.write(self.style.SUCCESS(f'🎉 TOTAL: {total} registros corregidos\n'))
