import os
import django

# Configuración de entorno Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from clinica.models import Division, Servicio, Consultorio

def cargar_datos():
    print("🚀 Iniciando carga de catálogos oficiales...")

    # ==========================================
    # 1. DIVISIONES (Clientes / Convenios)
    # ==========================================
    divisiones = [
        "Particular",
        "NEAPCO",
        "GIASA",
        "INSUNTE",
        "DOROTHEA",
        "UNIVAS",
        "iFOOD",
        "UTS",
        "Cáritas de Saltillo",
        "Escuela",
        "Otro"
    ]
    
    print(f"\n📂 Cargando {len(divisiones)} Divisiones...")
    for nombre in divisiones:
        obj, created = Division.objects.get_or_create(nombre=nombre)
        if created:
            print(f"   ✅ Creado: {nombre}")
        else:
            print(f"   ℹ️ Ya existe: {nombre}")

    # ==========================================
    # 2. SERVICIOS (Tipos de Terapia)
    # ==========================================
    servicios = [
        "Terapia individual",
        "Terapia infantil",
        "Terapia de parejas",
        "Terapia Familiar",
        "Evaluación neuropsicológica",
        "Consulta psiquiátrica",
        "Consulta en salud mental",
        "Consulta nutricional",
        "Hipnosis",
        "Psicotanatología",
        "Consulta Médica"
    ]
    
    print(f"\n🧠 Cargando {len(servicios)} Servicios...")
    for nombre in servicios:
        obj, created = Servicio.objects.get_or_create(nombre=nombre)
        if created:
            print(f"   ✅ Creado: {nombre}")
        else:
            print(f"   ℹ️ Ya existe: {nombre}")

    # ==========================================
    # 3. CONSULTORIOS (Sedes y Salas)
    # ==========================================
    # Estructura: "República" tiene 3, "Morelos" tiene 2, etc.
    consultorios = [
        # Sede República (Antes Guanajuato) - 3 Consultorios
        "República - Sala 1",
        "República - Sala 2",
        "República - Sala 3",
        
        # Sede Morelos - 2 Consultorios
        "Morelos - Sala 1",
        "Morelos - Sala 2",
        
        # Sede Colinas - 1 Consultorio
        "Colinas - Única",
        
        # Sede Trabajo Social (Poniente) - 1 Consultorio
        "Trabajo Social (Poniente)",
        
        # Virtual
        "Zoom / Online"
    ]

    print(f"\n🏢 Cargando {len(consultorios)} Consultorios...")
    for nombre in consultorios:
        obj, created = Consultorio.objects.get_or_create(nombre=nombre)
        if created:
            print(f"   ✅ Creado: {nombre}")
        else:
            print(f"   ℹ️ Ya existe: {nombre}")

    print("\n✨ ¡Carga completa! Ahora sí puedes agendar con los datos correctos.")

if __name__ == "__main__":
    cargar_datos()