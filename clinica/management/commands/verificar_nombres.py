"""
Script para verificar corrección de nombres en la BD
"""
from django.core.management.base import BaseCommand
from clinica.models import Paciente, Terapeuta, Consultorio, Servicio, Division


class Command(BaseCommand):
    help = 'Verifica que los nombres en la BD estén correctamente guardados'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('📊 Verificando nombres en la base de datos...\n'))
        
        # Buscar nombres con caracteres sospechosos
        caracteres_problema = ['┴', 'ß', 'Ý', '¾', 'Ã', 'Â', 'À']
        
        problemas = {
            'pacientes': [],
            'terapeutas': [],
            'consultorios': [],
            'servicios': [],
            'divisiones': []
        }

        # Pacientes
        self.stdout.write('👥 Revisando PACIENTES...')
        for p in Paciente.objects.all():
            for car in caracteres_problema:
                if car in p.nombre:
                    problemas['pacientes'].append((p.id, p.nombre))
                    break

        # Terapeutas
        self.stdout.write('👨‍⚕️  Revisando TERAPEUTAS...')
        for t in Terapeuta.objects.all():
            for car in caracteres_problema:
                if car in t.nombre:
                    problemas['terapeutas'].append((t.id, t.nombre))
                    break

        # Consultorios
        self.stdout.write('🏥 Revisando CONSULTORIOS...')
        for c in Consultorio.objects.all():
            for car in caracteres_problema:
                if car in c.nombre:
                    problemas['consultorios'].append((c.id, c.nombre))
                    break

        # Servicios
        self.stdout.write('🔧 Revisando SERVICIOS...')
        for s in Servicio.objects.all():
            for car in caracteres_problema:
                if car in s.nombre:
                    problemas['servicios'].append((s.id, s.nombre))
                    break

        # Divisiones
        self.stdout.write('📂 Revisando DIVISIONES...')
        for d in Division.objects.all():
            for car in caracteres_problema:
                if car in d.nombre:
                    problemas['divisiones'].append((d.id, d.nombre))
                    break

        # Resumen
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('📊 RESUMEN DE VERIFICACIÓN:'))
        self.stdout.write('='*50)
        
        if sum(len(v) for v in problemas.values()) == 0:
            self.stdout.write(self.style.SUCCESS('✅ ¡EXCELENTE! No se encontraron caracteres corruptos'))
            self.stdout.write(self.style.SUCCESS('Todos los nombres están correctamente guardados en UTF-8'))
        else:
            self.stdout.write(self.style.ERROR('⚠️  Se encontraron ALGUNOS caracteres corruptos:'))
            
            for tipo, registros in problemas.items():
                if registros:
                    self.stdout.write(f'\n{tipo}:')
                    for id_reg, nombre in registros:
                        self.stdout.write(f'  ID {id_reg}: {nombre}')
        
        # Mostrar ejemplos de nombres correctos
        self.stdout.write('\n' + '='*50)
        self.stdout.write('📋 Ejemplos de nombres CORRECTOS:')
        self.stdout.write('='*50)
        
        ejemplos = Paciente.objects.filter(nombre__icontains='García')[:3]
        for p in ejemplos:
            self.stdout.write(f'✓ {p.nombre}')
        
        ejemplos = Paciente.objects.filter(nombre__icontains='Sofía')[:3]
        for p in ejemplos:
            self.stdout.write(f'✓ {p.nombre}')
            
        ejemplos = Paciente.objects.filter(nombre__icontains='Sánchez')[:3]
        for p in ejemplos:
            self.stdout.write(f'✓ {p.nombre}')
