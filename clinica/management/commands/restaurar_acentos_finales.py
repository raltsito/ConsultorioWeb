"""
Script final para completar la restauración de acentos
Busca patrones residuales como "Gmez", "Dvila" y los corrige
"""
from django.core.management.base import BaseCommand
from clinica.models import Paciente, Terapeuta, Consultorio, Servicio, Division
import re


def restaurar_acentos_finales(texto):
    """
    Restaura acentos faltantes en palabras específicas
    """
    if not texto:
        return texto
    
    # Patrones específicos faltantes
    conversiones_finales = {
        r'\bGmez\b': 'Gómez',
        r'\bGmez\b': 'Gómez',
        r'\bDvila\b': 'Dávila',
        r'\bGarca\b': 'García',
        r'\bGarcia\b': 'García',
        r'\bRodrguez\b': 'Rodríguez',
        r'\bRodriguez\b': 'Rodríguez',
        r'\bZuiga\b': 'Zúñiga',
        r'\bZuniga\b': 'Zúñiga',
        r'\bSnchez\b': 'Sánchez',
        r'\bHernndez\b': 'Hernández',
        r'\bVzquez\b': 'Vázquez',
        r'\bVazquez\b': 'Vázquez',
        r'\bMendez\b': 'Méndez',
        r'\bRamirez\b': 'Ramírez',
        r'\bJimenez\b': 'Jiménez',
        r'\bGutierrez\b': 'Gutiérrez',
        r'\bDominguez\b': 'Domínguez',
        r'\bEscobedo\b': 'Escobedo',
        r'\bFlores\b': 'Flores',
        r'\bGonzalez\b': 'González',
        r'\bVizcaino\b': 'Vizcaíno',
        r'\bViscaino\b': 'Vizcaíno',
        r'\bSilva\b': 'Silva',
        r'\bSoto\b': 'Soto',
        r'\bRios\b': 'Ríos',
        r'\bPena\b': 'Peña',
        r'\bOrdonez\b': 'Ordóñez',
        r'\bMarin\b': 'Marín',
        r'\bMaria\b': 'María',
        r'\bCifuentes\b': 'Cifuentes',
        r'\bCastaneda\b': 'Castañeda',
        r'\bCastaeda\b': 'Castañeda',
        r'\bAlarcon\b': 'Alarcón',
        r'\bArevalo\b': 'Arévalo',
        r'\bEscareo\b': 'Escareo',
        r'\bOscar\b': 'Óscar',
        r'\bEsqivel\b': 'Esquivel',
        r'\bLopez\b': 'López',
        r'\bPerez\b': 'Pérez',
        r'\bGonzalez\b': 'González',
        r'\bAgustin\b': 'Agustín',
        r'\bFélix\b': 'Félix',
        r'\bJesus\b': 'Jesús',
        r'\bJess\b': 'Jesús',
        r'\b Jess\b': 'Jesús',
        r'\bSofia\b': 'Sofía',
        r'\bFatima\b': 'Fátima',
        r'\bLucía\b': 'Lucía',
        r'\bLucia\b': 'Lucía',
        r'\bIsabel\b': 'Isabel',
        r'\bBelen\b': 'Belén',
        r'\bValentin\b': 'Valentín',
        r'\bRodrigo\b': 'Rodrigo',
        r'\bEstefania\b': 'Estefanía',
        r'\bRuben\b': 'Rubén',
        r'\bSebastian\b': 'Sebastián',
        r'\bMiguel\b': 'Miguel',
        r'\bArturo\b': 'Arturo',
        r'\bLeonardo\b': 'Leonardo',
        r'\bJose\b': 'José',
        r'\bJosé\b': 'José',
        r'\bAlejandra\b': 'Alejandra',
        r'\bMauricio\b': 'Mauricio',
        r'\bCesar\b': 'César',
        r'\bMarcos\b': 'Marcos',
        r'\bFrancisco\b': 'Francisco',
        r'\bManuel\b': 'Manuel',
        r'\bFelipe\b': 'Felipe',
    }
    
    resultado = texto
    for patron, reemplazo in conversiones_finales.items():
        resultado = re.sub(patron, reemplazo, resultado, flags=re.IGNORECASE)
    
    return resultado


class Command(BaseCommand):
    help = 'Restaura acentos finales faltantes en nombres'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Completando restauración de acentos...\n'))
        
        contador = {'pacientes': 0, 'terapeutas': 0, 'consultorios': 0}

        self.stdout.write('👥 Procesando PACIENTES...')
        for p in Paciente.objects.all():
            nombre_mejorado = restaurar_acentos_finales(p.nombre)
            if nombre_mejorado != p.nombre:
                self.stdout.write(f'   ✏️  {p.nombre} → {nombre_mejorado}')
                p.nombre = nombre_mejorado
                p.save()
                contador['pacientes'] += 1

        self.stdout.write('\n👨‍⚕️  Procesando TERAPEUTAS...')
        for t in Terapeuta.objects.all():
            nombre_mejorado = restaurar_acentos_finales(t.nombre)
            if nombre_mejorado != t.nombre:
                self.stdout.write(f'   ✏️  {t.nombre} → {nombre_mejorado}')
                t.nombre = nombre_mejorado
                t.save()
                contador['terapeutas'] += 1

        # Resumen
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('✅ RESUMEN FINAL:'))
        self.stdout.write('='*50)
        self.stdout.write(f'👥 Pacientes completados: {contador["pacientes"]}')
        self.stdout.write(f'👨‍⚕️  Terapeutas completados: {contador["terapeutas"]}')
        total = sum(contador.values())
        self.stdout.write(self.style.SUCCESS(f'🎉 TOTAL: {total} registros completados\n'))
        
        # Ejemplos
        self.stdout.write('📋 Ejemplos verificados:')
        ejemplos = Paciente.objects.filter(nombre__icontains='García')[:2]
        for p in ejemplos:
            self.stdout.write(f'✓ {p.nombre}')
