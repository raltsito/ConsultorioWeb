from django.core.management.base import BaseCommand
from clinica.models import Terapeuta, Consultorio, Division, Servicio

class Command(BaseCommand):
    help = 'Carga los catálogos iniciales desde el Excel del consultorio'

    def handle(self, *args, **kwargs):
        self.stdout.write("Iniciando carga de datos...")

        # --- 1. TERAPEUTAS ---
        terapeutas = [
            'Alejandra Durán', 'Ana Juarez', 'Benjamin Villagomez', 'Carolina Gonzalez', 
            'Daniel Salazar', 'Daniela Sarmiento', 'David Bermejo', 'Enrique Arteaga', 
            'Enrique Luna', 'Esmeralda Colunga', 'Fabiola Fragoso', 'Gloria Sarmiento', 
            'Javier Martínez', 'Jennifer Torres', 'José Arcadio', 'Lucía Sánchez', 
            'Magda Charles', 'María Amancio - Ind', 'María Amancio - Par', 'Maria de la Luz', 
            'Maricela Sena', 'Perla Realme', 'Rosy Macías', 'Rafael Gonzalez', 
            'Dante Zertuche', 'Mariana Siller', 'Yessica Leija', 'Carlos Mendiola', 
            'Alondra Escalon', 'Blanca Araceli Zamora', 'Dante Zertuche Ev'
        ]
        
        for nombre in terapeutas:
            # get_or_create evita duplicados si corres el script 2 veces
            obj, created = Terapeuta.objects.get_or_create(nombre=nombre)
            if created:
                self.stdout.write(f" + Terapeuta creado: {nombre}")

        # --- 2. CONSULTORIOS ---
        consultorios = [
            'Morelos', 'Guanajuato', 'Praderas', 'Colinas', 'Zoom', 'Externo', 'Trabajo Social'
        ]
        for nombre in consultorios:
            obj, created = Consultorio.objects.get_or_create(nombre=nombre)
            if created:
                self.stdout.write(f" + Consultorio creado: {nombre}")

        # --- 3. SERVICIOS ---
        servicios = [
            'Terapia individual', 'Terapia infantil', 'Terapia de parejas', 'Terapia Familiar',
            'Evaluación neuropsicológica', 'Médica psiquiátrica', 'Medica en salud mental',
            'Consulta nutricional', 'Hipnosis', 'Psicotanatología', 'Medica'
        ]
        for nombre in servicios:
            obj, created = Servicio.objects.get_or_create(nombre=nombre)
            if created:
                self.stdout.write(f" + Servicio creado: {nombre}")

        # --- 4. DIVISIONES ---
        divisiones = [
            'Particular', 'NEAPCO', 'GIASA', 'INSUNTE', 'DOROTHEA', 'UNIVAS', 
            'iFOOD', 'UTS', 'Cáritas de Saltillo', 'Escuela', 'Otro'
        ]
        for nombre in divisiones:
            obj, created = Division.objects.get_or_create(nombre=nombre)
            if created:
                self.stdout.write(f" + División creada: {nombre}")

        self.stdout.write(self.style.SUCCESS('¡ÉXITO! Base de datos poblada correctamente.'))