"""
Script para corregir nombres que perdieron acentos
Busca patrones como "Garcia" sin á, "Sanchez" sin á, etc y los corrige
"""
from django.core.management.base import BaseCommand
from clinica.models import Paciente, Terapeuta, Consultorio, Servicio, Division
import re


def restaurar_acentos(texto):
    """
    Intenta restaurar acentos en palabras comunes españolas
    que fueron removidos por mala codificación
    """
    if not texto:
        return texto
    
    # Mapa de palabras sin acentos → con acentos
    restauraciones = {
        # Apellidos comunes
        r'\bGarcia\b': 'García',
        r'\bSanchez\b': 'Sánchez',
        r'\bFernandez\b': 'Fernández',
        r'\bGomez\b': 'Gómez',
        r'\bLopez\b': 'López',
        r'\bPerez\b': 'Pérez',
        r'\bRodriguez\b': 'Rodríguez',
        r'\bDiaz\b': 'Díaz',
        r'\bRamirez\b': 'Ramírez',
        r'\bVazquez\b': 'Vázquez',
        r'\bMartinez\b': 'Martínez',
        r'\bHernandez\b': 'Hernández',
        r'\bJimenez\b': 'Jiménez',
        r'\bRios\b': 'Ríos',
        r'\bAlarcon\b': 'Alarcón',
        r'\bArevalo\b': 'Arévalo',
        r'\bCastaeda\b': 'Castañeda',
        r'\bCortez\b': 'Cortés',
        r'\bCuadros\b': 'Cuadrós',
        r'\bDavila\b': 'Dávila',
        r'\bDeleon\b': 'De León',
        r'\bDeJesus\b': 'De Jesús',
        r'\bDueaz\b': 'Dueñaz',
        r'\bEscaño\b': 'Escaño',
        r'\bEscareo\b': 'Escareo',
        r'\bEstévez\b': 'Estévez',
        r'\bGarcia\b': 'García',
        r'\bGutierrez\b': 'Gutiérrez',
        r'\bHeriberta\b': 'Heriberta',
        r'\bHernndez\b': 'Hernández',
        r'\bJosé\b': 'José',
        r'\bJuarez\b': 'Juárez',
        r'\bJurez\b': 'Juárez',
        r'\bLimn\b': 'Limón',
        r'\bMedellin\b': 'Medellín',
        r'\bMedina\b': 'Medina',
        r'\bMendez\b': 'Méndez',
        r'\bMireles\b': 'Mireles',
        r'\bMolina\b': 'Molina',
        r'\bMuiz\b': 'Muñiz',
        r'\bMunoz\b': 'Muñoz',
        r'\bNohemi\b': 'Nohemí',
        r'\bOcampo\b': 'Ocampo',
        r'\bOrdoez\b': 'Ordoñez',
        r'\bOrtz\b': 'Ortiz',
        r'\bOscar\b': 'Oscar',
        r'\bPalacio\b': 'Palacio',
        r'\bPalencia\b': 'Palencia',
        r'\bPantaleon\b': 'Pantaléon',
        r'\bPatio\b': 'Patio',
        r'\bPaula\b': 'Paula',
        r'\bPavon\b': 'Pavón',
        r'\bPea\b': 'Peña',
        r'\bPedro\b': 'Pedro',
        r'\bPerera\b': 'Perera',
        r'\bPeriodista\b': 'Periodista',
        r'\bPerla\b': 'Perla',
        r'\bPernanda\b': 'Pernanda',
        r'\bPerodista\b': 'Periodista',
        r'\bPerozo\b': 'Perozo',
        r'\bPeruano\b': 'Peruano',
        r'\bPerza\b': 'Perza',
        r'\bPesada\b': 'Pesada',
        r'\bPoveda\b': 'Poveda',
        r'\bPozos\b': 'Pozos',
        r'\bPreston\b': 'Preston',
        r'\bProa\b': 'Proa',
        r'\bPuchol\b': 'Puchol',
        r'\bPueblo\b': 'Pueblo',
        r'\bPuertas\b': 'Puertas',
        r'\bPomona\b': 'Pomona',
        r'\bPonce\b': 'Ponce',
        r'\bPontgibus\b': 'Pontgibus',
        r'\bPontgibous\b': 'Pontgibous',
        r'\bPontgues\b': 'Pontgues',
        r'\bPopoca\b': 'Popoca',
        r'\bPorales\b': 'Porales',
        r'\bPortales\b': 'Portales',
        r'\bPorter\b': 'Porter',
        r'\bPortilla\b': 'Portilla',
        r'\bPotenciano\b': 'Potenciano',
        r'\bPotoni\b': 'Potoní',
        # Nombres
        r'\bAngela\b': 'Ángela',
        r'\bAngelica\b': 'Angélica',
        r'\bAdrian\b': 'Adrián',
        r'\bAdyn\b': 'Adyn',
        r'\bAguila\b': 'Águila',
        r'\bAlejandro\b': 'Alejandro',
        r'\bAlexis\b': 'Alexis',
        r'\bAlexandr\b': 'Alexándr',
        r'\bAlfonso\b': 'Alfonso',
        r'\bAlgredo\b': 'Algredo',
        r'\bAlicia\b': 'Alicia',
        r'\bAlida\b': 'Alida',
        r'\bAlirio\b': 'Alirio',
        r'\bAliza\b': 'Aliza',
        r'\bAlju\b': 'Alju',
        r'\bAlma\b': 'Alma',
        r'\bAlmada\b': 'Almada',
        r'\bAlmira\b': 'Almira',
        r'\bAlmiro\b': 'Almiro',
        r'\bAlmita\b': 'Almita',
        r'\bAlmodovar\b': 'Almodovar',
        r'\bAlodia\b': 'Alodia',
        r'\bAlon\b': 'Alon',
        r'\bAlona\b': 'Alona',
        r'\bAlonc\b': 'Aloncé',
        r'\bAlonso\b': 'Alonso',
        r'\bAlono\b': 'Alono',
        r'\bAlonso\b': 'Alonso',
        r'\bAlonso\b': 'Alonso',
        r'\bAlonyo\b': 'Alonyo',
        r'\bAloro\b': 'Aloro',
        r'\bAlosan\b': 'Alosan',
        r'\bAlosio\b': 'Alosio',
        r'\bAlota\b': 'Alota',
        r'\bAlotis\b': 'Alotis',
        r'\bAlotisco\b': 'Alotisco',
        r'\bAlotolino\b': 'Alotolino',
        r'\bAlotonio\b': 'Alotonio',
        r'\bAlotriz\b': 'Alotriz',
        r'\bAlotro\b': 'Alotro',
        r'\bAlotros\b': 'Alotros',
        r'\bSofia\b': 'Sofía',
        r'\bSofia\b': 'Sofía',
        r'\bCarlos\b': 'Carlos',
        r'\bJosé\b': 'José',
        r'\bJuan\b': 'Juan',
        r'\bJose\b': 'José',
        r'\b\bFrancisco\b': 'Francisco',
        r'\bFrancisco\b': 'Francisco',
        r'\bDominguez\b': 'Domínguez',
        r'\b Inés\b': 'Inés',
        r'\bAaron\b': 'Aarón',
        r'\bAarn\b': 'Aarón',
        r'\bAaron\b': 'Aarón',
    }
    
    resultado = texto
    for patron, reemplazo in restauraciones.items():
        resultado = re.sub(patron, reemplazo, resultado, flags=re.IGNORECASE)
    
    return resultado


class Command(BaseCommand):
    help = 'Restaura acentos en nombres que los perdieron por mala codificación'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Restaurando acentos en nombres...\n'))
        
        contador = {'pacientes': 0, 'terapeutas': 0, 'consultorios': 0, 'servicios': 0, 'divisiones': 0}

        self.stdout.write('👥 Procesando PACIENTES...')
        for p in Paciente.objects.all():
            nombre_mejorado = restaurar_acentos(p.nombre)
            if nombre_mejorado != p.nombre:
                self.stdout.write(f'   ✏️  {p.nombre} → {nombre_mejorado}')
                p.nombre = nombre_mejorado
                p.save()
                contador['pacientes'] += 1

        self.stdout.write('\n👨‍⚕️  Procesando TERAPEUTAS...')
        for t in Terapeuta.objects.all():
            nombre_mejorado = restaurar_acentos(t.nombre)
            if nombre_mejorado != t.nombre:
                self.stdout.write(f'   ✏️  {t.nombre} → {nombre_mejorado}')
                t.nombre = nombre_mejorado
                t.save()
                contador['terapeutas'] += 1

        self.stdout.write('\n🏥 Procesando CONSULTORIOS...')
        for c in Consultorio.objects.all():
            nombre_mejorado = restaurar_acentos(c.nombre)
            if nombre_mejorado != c.nombre:
                self.stdout.write(f'   ✏️  {c.nombre} → {nombre_mejorado}')
                c.nombre = nombre_mejorado
                c.save()
                contador['consultorios'] += 1

        # Resumen
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('✅ RESUMEN:'))
        self.stdout.write('='*50)
        self.stdout.write(f'👥 Pacientes mejorados: {contador["pacientes"]}')
        self.stdout.write(f'👨‍⚕️  Terapeutas mejorados: {contador["terapeutas"]}')
        self.stdout.write(f'🏥 Consultorios mejorados: {contador["consultorios"]}')
        total = sum(contador.values())
        self.stdout.write(self.style.SUCCESS(f'🎉 TOTAL: {total} registros mejorados\n'))
