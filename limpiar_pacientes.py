import pandas as pd
import difflib

def limpiar_lista():
    print("📂 Leyendo archivo REVISAR_PACIENTES.xlsx - Sheet1.csv...")
    
    # 1. Cargamos el archivo CSV que subiste
    # (Asegúrate de que el archivo esté en la misma carpeta)
    try:
        df = pd.read_csv('REVISAR_PACIENTES.xlsx - Sheet1.csv')
    except:
        # Si falla, intentamos leerlo como Excel normal si ya lo convertiste
        try:
            df = pd.read_excel('REVISAR_PACIENTES.xlsx')
        except:
            print("❌ No encuentro el archivo. Asegúrate que se llame 'REVISAR_PACIENTES.xlsx - Sheet1.csv' o similar.")
            return

    # Limpiamos espacios en los nombres de columnas
    df.columns = df.columns.str.strip()
    
    # Buscamos la columna correcta
    col_nombre = 'Nombre_Paciente'
    if col_nombre not in df.columns:
        print(f"⚠️ No encontré la columna '{col_nombre}'. Usando la primera columna disponible.")
        col_nombre = df.columns[0]

    # Convertimos a lista y ordenamos por longitud (los más largos primero son "más confiables")
    nombres_originales = df[col_nombre].dropna().unique().tolist()
    # Ordenamos: Primero los más largos. Así "Juan Perez Gzz" tiene prioridad sobre "Juan Perez"
    nombres_originales.sort(key=len, reverse=True)

    pacientes_limpios = {}
    nombres_finales = []

    print(f"🧹 Analizando {len(nombres_originales)} nombres únicos con Lógica Difusa...")

    for nombre in nombres_originales:
        nombre_str = str(nombre).strip()
        encontrado = False
        
        # Comparamos con los nombres que ya dimos por "buenos"
        for final in nombres_finales:
            # difflib compara qué tan parecidos son (0.0 a 1.0)
            similitud = difflib.SequenceMatcher(None, nombre_str.lower(), final.lower()).ratio()
            
            # SI SE PARECEN MÁS DEL 85% (Ajustable)
            if similitud > 0.85:
                # Es la misma persona! Lo asignamos al nombre "oficial" (el más largo que ya guardamos)
                pacientes_limpios[nombre_str] = final
                encontrado = True
                print(f"   🔗 Fusionando: '{nombre_str}'  --->  '{final}'")
                break
        
        if not encontrado:
            # Es una persona nueva
            nombres_finales.append(nombre_str)
            pacientes_limpios[nombre_str] = nombre_str

    # 2. Creamos el archivo final
    print("-" * 30)
    print(f"✅ Reducción: De {len(nombres_originales)} pasamos a {len(nombres_finales)} pacientes reales.")
    
    df_final = pd.DataFrame(nombres_finales, columns=['Nombre_Paciente'])
    df_final.sort_values(by='Nombre_Paciente', inplace=True)
    
    nombre_archivo_salida = "PACIENTES_LIMPIOS.xlsx"
    df_final.to_excel(nombre_archivo_salida, index=False)
    print(f"🎉 ¡Listo! Archivo '{nombre_archivo_salida}' creado.")

if __name__ == "__main__":
    limpiar_lista()