import os
import django
import pandas as pd
from datetime import date # <--- IMPORTANTE: Agregamos esto para manejar fechas

# --- CONFIGURACIÓN DE DJANGO ---
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings') 
django.setup()

from clinica.models import Paciente

def cargar_datos():
    print("🚀 Iniciando carga masiva de pacientes...")
    
    archivo = 'PACIENTES_LIMPIOS.csv'
    
    try:
        df = pd.read_csv(archivo)
    except:
        try:
            df = pd.read_excel('PACIENTES_LIMPIOS.xlsx')
        except:
            print("❌ ERROR: No encuentro el archivo 'PACIENTES_LIMPIOS.csv' ni '.xlsx'")
            return

    col_nombre = 'Nombre_Paciente'
    if col_nombre not in df.columns:
        col_nombre = df.columns[0]

    count_nuevos = 0
    count_existentes = 0

    print(f"📂 Procesando {len(df)} registros...")

    for index, row in df.iterrows():
        nombre_limpio = str(row[col_nombre]).strip()
        
        if not nombre_limpio or nombre_limpio.lower() == 'nan':
            continue

        # BUSCAR O CREAR
        obj, created = Paciente.objects.get_or_create(
            nombre=nombre_limpio,
            defaults={
                'telefono': '',
                'resumen_clinico': 'Importado desde Historial Excel',
                # 👇 AQUÍ ESTÁ EL TRUCO: Le damos una fecha falsa por defecto
                'fecha_nacimiento': date(2000, 1, 1), 
                'sexo': 'Femenino' # Ponemos uno por defecto, luego se corrige
            }
        )

        if created:
            print(f"   ✨ Creado: {nombre_limpio}")
            count_nuevos += 1
        else:
            print(f"   ⚠️ Ya existía: {nombre_limpio}")
            count_existentes += 1

    print("-" * 30)
    print(f"🎉 ¡TERMINADO!")
    print(f"✅ Pacientes Nuevos insertados: {count_nuevos}")
    print(f"⏭️ Pacientes que ya existían: {count_existentes}")
    print(f"📊 Total en base de datos: {Paciente.objects.count()}")

if __name__ == "__main__":
    cargar_datos()