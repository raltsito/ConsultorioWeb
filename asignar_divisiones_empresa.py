"""
Script: asignar_divisiones_empresa.py
Asigna la Division correspondiente a cada Empresa.
"""
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from clinica.models import Division, Empresa

# nombre Empresa -> nombre Division
MAPEO = {
    'GIASA':          'GIASA',
    'NEAPCO':         'NEAPCO',
    'CARITAS':        'Critas de Saltillo',
    'DOROTHEA':       'DOROTHEA',
    'INTEC DON BOSCO': 'INTEC Don Bosco',
}

for emp_nombre, div_nombre in MAPEO.items():
    try:
        emp = Empresa.objects.get(nombre=emp_nombre)
        div = Division.objects.get(nombre=div_nombre)
        emp.division = div
        emp.save(update_fields=['division'])
        print(f"[OK] {emp_nombre} -> {div_nombre}")
    except Empresa.DoesNotExist:
        print(f"[SKIP] Empresa '{emp_nombre}' no encontrada")
    except Division.DoesNotExist:
        print(f"[SKIP] Division '{div_nombre}' no encontrada")
