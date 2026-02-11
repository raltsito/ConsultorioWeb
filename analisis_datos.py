import pandas as pd
import os

def analizar_excel():
    print(" Leyendo archivo Excel...")
    
    try:
        # 1. Cargamos el Excel
        df = pd.read_excel('datos_originales.xlsx', sheet_name='Datos')
        
        # 2. TRUCO DE MAGIA: Quitamos espacios vacíos en los títulos de las columnas
        # (Así "Paciente " se convierte en "Paciente")
        df.columns = df.columns.str.strip()
        
        print("\n Las columnas que encontré en tu Excel son:")
        print(df.columns.tolist())
        print("-" * 30)

        # 3. Verificamos si existe la columna, o tratamos de adivinar
        columna_nombre = 'Paciente|text-1'
        
        if columna_nombre not in df.columns:
            print(f" ERROR: No encuentro la columna '{columna_nombre}'.")
            print(" Revisa la lista de arriba y cambia la variable 'columna_nombre' en este script.")
            # Intentamos buscar si hay alguna parecida
            posibles = [c for c in df.columns if 'paciente' in c.lower() or 'nombre' in c.lower()]
            if posibles:
                print(f"💡 ¿Quizás quisiste decir: '{posibles[0]}'?\n")
            return

        # 4. Si llegamos aquí, ¡la columna existe! Procedemos.
        print(f" Columna '{columna_nombre}' encontrada. Analizando...")
        
        df['Paciente_Limpio'] = df[columna_nombre].astype(str).str.strip().str.title()

        conteo = df['Paciente_Limpio'].value_counts().reset_index()
        conteo.columns = ['Nombre_Paciente', 'Total_Citas']
        conteo = conteo.sort_values(by='Nombre_Paciente')

        print(f" Se encontraron {len(conteo)} pacientes únicos.")
        
        conteo.to_excel("REVISAR_PACIENTES.xlsx", index=False)
        print(" ¡LISTO! Archivo 'REVISAR_PACIENTES.xlsx' creado.")

    except Exception as e:
        print(f" Error crítico: {e}")

if __name__ == "__main__":
    analizar_excel()