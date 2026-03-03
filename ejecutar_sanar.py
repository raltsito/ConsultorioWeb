#!/usr/bin/env python
"""
Script ejecutable para limpiar nombres con encoding corrompido
Ejecutar desde manage.py o directamente
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from clinica.models import Paciente, Terapeuta, Consultorio, Servicio, Division

def corregir_encoding(texto):
    """
    Corrige texto con encoding corrompido (Latin1 leído como UTF-8)
    """
    if not texto:
        return texto
    
    # Conversiones de caracteres Latin1 mal interpretados
    conversiones = {
        'Ã¡': 'á', 'Ã©': 'é', 'Ã­': 'í', 'Ã³': 'ó', 'Ãº': 'ú',
        'Ã¡': 'á', 'Ã‰': 'É', 'Ã­': 'í', 'Ó³': 'ó', 'Ã±': 'ñ',
        'Â': '', 'Ã': '', 'â€™': "'",
        '┴': 'á', 'Á': 'á', '┬': 'á',
        'SofÝa': 'Sofía',
        'Sß': 'Sá',
        'Ý': 'í', 'ý': 'y',
    }
    
    resultado = texto
    for corrupto, correcto in conversiones.items():
        resultado = resultado.replace(corrupto, correcto)
    
    try:
        resultado = resultado.encode('latin1', errors='ignore').decode('utf-8', errors='ignore')
    except:
        pass
    
    return resultado.strip()

def main():
    print("🚀 Iniciando limpieza de caracteres corrompidos...\n")
    
    contador = {
        'pacientes': 0,
        'terapeutas': 0,
        'consultorios': 0,
        'servicios': 0,
        'divisiones': 0
    }

    # Pacientes
    print("👥 Procesando PACIENTES...")
    for p in Paciente.objects.all():
        nombre_limpio = corregir_encoding(p.nombre)
        
        if nombre_limpio != p.nombre and nombre_limpio:
            print(f"   ✏️  {p.nombre} → {nombre_limpio}")
            p.nombre = nombre_limpio
            p.save()
            contador['pacientes'] += 1

    # Terapeutas
    print("\n👨‍⚕️  Procesando TERAPEUTAS...")
    for t in Terapeuta.objects.all():
        nombre_limpio = corregir_encoding(t.nombre)
        
        if nombre_limpio != t.nombre and nombre_limpio:
            print(f"   ✏️  {t.nombre} → {nombre_limpio}")
            t.nombre = nombre_limpio
            t.save()
            contador['terapeutas'] += 1

    # Consultorios
    print("\n🏥 Procesando CONSULTORIOS...")
    for c in Consultorio.objects.all():
        nombre_limpio = corregir_encoding(c.nombre)
        
        if nombre_limpio != c.nombre and nombre_limpio:
            print(f"   ✏️  {c.nombre} → {nombre_limpio}")
            c.nombre = nombre_limpio
            c.save()
            contador['consultorios'] += 1

    # Servicios
    print("\n🔧 Procesando SERVICIOS...")
    for s in Servicio.objects.all():
        nombre_limpio = corregir_encoding(s.nombre)
        
        if nombre_limpio != s.nombre and nombre_limpio:
            print(f"   ✏️  {s.nombre} → {nombre_limpio}")
            s.nombre = nombre_limpio
            s.save()
            contador['servicios'] += 1

    # Divisiones
    print("\n📂 Procesando DIVISIONES...")
    for d in Division.objects.all():
        nombre_limpio = corregir_encoding(d.nombre)
        
        if nombre_limpio != d.nombre and nombre_limpio:
            print(f"   ✏️  {d.nombre} → {nombre_limpio}")
            d.nombre = nombre_limpio
            d.save()
            contador['divisiones'] += 1

    # Resumen
    print("\n" + "="*50)
    print("✅ RESUMEN DE CORRECCIONES:")
    print("="*50)
    print(f"👥 Pacientes arreglados:    {contador['pacientes']}")
    print(f"👨‍⚕️  Terapeutas arreglados:   {contador['terapeutas']}")
    print(f"🏥 Consultorios arreglados: {contador['consultorios']}")
    print(f"🔧 Servicios arreglados:    {contador['servicios']}")
    print(f"📂 Divisiones arregladas:   {contador['divisiones']}")
    print("="*50)
    total = sum(contador.values())
    print(f"🎉 TOTAL: {total} registros corregidos\n")

if __name__ == "__main__":
    main()
