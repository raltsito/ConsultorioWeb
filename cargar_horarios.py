import os
import django
from datetime import time

# Configuración para que funcione dentro de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from clinica.models import Terapeuta, Horario

# Diccionario para traducir días a números
DIAS = {
    'Lunes': 0, 'Martes': 1, 'Miércoles': 2, 'Jueves': 3, 'Viernes': 4, 'Sábado': 5, 'Domingo': 6
}

# ==========================================
# 📅 HORARIOS LIMPIOS
# ==========================================
datos_a_cargar = [
    # --- DANIEL SALAZAR ---
    ["Daniel Salazar", "Lunes", "07:00", "09:00"],
    ["Daniel Salazar", "Lunes", "13:00", "15:00"],
    ["Daniel Salazar", "Lunes", "18:00", "21:00"],
    ["Daniel Salazar", "Martes", "18:00", "21:00"],
    ["Daniel Salazar", "Miércoles", "18:00", "21:00"],
    ["Daniel Salazar", "Jueves", "18:00", "21:00"],
    ["Daniel Salazar", "Viernes", "18:00", "21:00"],
    ["Daniel Salazar", "Sábado", "08:00", "14:00"],

    # --- ALISSON BERMEA ---
    ["Alisson Bermea", "Lunes", "09:00", "13:00"],
    ["Alisson Bermea", "Martes", "09:00", "13:00"],
    ["Alisson Bermea", "Miércoles", "09:00", "13:00"],
    ["Alisson Bermea", "Jueves", "09:00", "13:00"],
    ["Alisson Bermea", "Viernes", "09:00", "13:00"],

    # --- BENJAMIN VILLAGOMEZ ---
    ["Benjamin Villagomez", "Lunes", "18:00", "21:00"],
    ["Benjamin Villagomez", "Martes", "18:00", "21:00"],
    ["Benjamin Villagomez", "Miércoles", "18:00", "21:00"],
    ["Benjamin Villagomez", "Jueves", "18:00", "21:00"],
    ["Benjamin Villagomez", "Viernes", "18:00", "21:00"],
    ["Benjamin Villagomez", "Sábado", "11:00", "14:00"],

    # --- LUCÍA SÁNCHEZ ---
    ["Lucía Sánchez", "Lunes", "10:00", "14:00"],
    ["Lucía Sánchez", "Martes", "10:00", "14:00"],
    ["Lucía Sánchez", "Miércoles", "10:00", "14:00"],
    ["Lucía Sánchez", "Jueves", "10:00", "14:00"],
    ["Lucía Sánchez", "Viernes", "10:00", "14:00"],
    ["Lucía Sánchez", "Lunes", "15:00", "20:00"],
    ["Lucía Sánchez", "Martes", "15:00", "20:00"],
    ["Lucía Sánchez", "Miércoles", "15:00", "20:00"],
    ["Lucía Sánchez", "Jueves", "15:00", "20:00"],

    # --- MARICELA SENA ---
    ["Maricela Sena", "Lunes", "09:00", "14:00"],
    ["Maricela Sena", "Martes", "09:00", "14:00"],
    ["Maricela Sena", "Miércoles", "09:00", "14:00"],
    ["Maricela Sena", "Jueves", "09:00", "14:00"],
    ["Maricela Sena", "Viernes", "09:00", "14:00"],
    ["Maricela Sena", "Lunes", "16:00", "20:00"],
    ["Maricela Sena", "Miércoles", "16:00", "20:00"],
    
    # --- GLORIA SARMIENTO ---
    ["Gloria Sarmiento", "Lunes", "14:00", "20:00"],
    ["Gloria Sarmiento", "Martes", "14:00", "20:00"],
    ["Gloria Sarmiento", "Miércoles", "14:00", "20:00"],
    ["Gloria Sarmiento", "Jueves", "14:00", "20:00"],
    ["Gloria Sarmiento", "Viernes", "14:00", "20:00"],

    # --- FABIOLA FRAGOSO ---
    ["Fabiola Fragoso", "Lunes", "18:00", "21:00"],
    ["Fabiola Fragoso", "Miércoles", "18:00", "21:00"],
    ["Fabiola Fragoso", "Viernes", "18:00", "21:00"],
    
    # --- ENRIQUE LUNA ---
    ["Enrique Luna", "Lunes", "16:00", "21:00"],
    ["Enrique Luna", "Martes", "16:00", "21:00"],
    ["Enrique Luna", "Miércoles", "16:00", "21:00"],
    ["Enrique Luna", "Jueves", "16:00", "21:00"],
    ["Enrique Luna", "Viernes", "16:00", "21:00"],

    # --- JOSÉ ARCADIO ---
    ["José Arcadio", "Lunes", "17:30", "21:00"],
    ["José Arcadio", "Martes", "17:30", "21:00"],
    ["José Arcadio", "Miércoles", "17:30", "21:00"],
    ["José Arcadio", "Jueves", "17:30", "21:00"],
    ["José Arcadio", "Viernes", "17:30", "21:00"],
    
    # --- DANIELA SARMIENTO ---
    ["Daniela Sarmiento", "Lunes", "09:00", "12:00"],
    ["Daniela Sarmiento", "Lunes", "16:00", "19:00"],
]

def cargar():
    print("🚀 Iniciando carga masiva de horarios...")
    print("🧹 Limpiando horarios antiguos...")
    Horario.objects.all().delete()
    
    creados = 0
    errores = 0

    for item in datos_a_cargar:
        nombre_terapeuta, dia_str, hora_ini_str, hora_fin_str = item
        
        try:
            # Buscamos coincidencias parciales si el nombre no es exacto
            terapeutas = Terapeuta.objects.filter(nombre__icontains=nombre_terapeuta)
            
            if not terapeutas.exists():
                print(f"❌ ERROR: No encuentro al terapeuta '{nombre_terapeuta}'")
                errores += 1
                continue
                
            terapeuta = terapeutas.first()
            
            h_inicio = time(*map(int, hora_ini_str.split(':')))
            h_fin = time(*map(int, hora_fin_str.split(':')))
            dia_num = DIAS[dia_str]

            Horario.objects.create(
                terapeuta=terapeuta,
                dia=dia_num,
                hora_inicio=h_inicio,
                hora_fin=h_fin
            )
            print(f"✅ {terapeuta.nombre} -> {dia_str} {hora_ini_str}-{hora_fin_str}")
            creados += 1

        except Exception as e:
            print(f"⚠️ Error con {nombre_terapeuta}: {e}")
            errores += 1

    print("-" * 30)
    print(f"🏁 Carga terminada. Horarios creados: {creados} | Errores: {errores}")

if __name__ == "__main__":
    cargar()