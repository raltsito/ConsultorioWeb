"""
Script: vincular_pacientes_empresa.py
Vincula pacientes existentes a su Empresa según la division de sus citas.
Mapeo:
  NEAPCO            -> Empresa NEAPCO
  GIASA             -> Empresa GIASA
  Cáritas de Saltillo -> Empresa CARITAS
  DOROTHEA          -> Empresa DOROTHEA
  INTEC Don Bosco   -> Empresa INTEC DON BOSCO
"""
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from clinica.models import Division, Empresa, Paciente, Cita

# Mapeo nombre division -> nombre empresa
MAPEO = {
    'NEAPCO':              'NEAPCO',
    'GIASA':               'GIASA',
    'Critas de Saltillo':  'CARITAS',
    'DOROTHEA':            'DOROTHEA',
    'INTEC Don Bosco':     'INTEC DON BOSCO',
}

# Cargar objetos
divisiones = {d.nombre: d for d in Division.objects.all()}
empresas   = {e.nombre: e for e in Empresa.objects.all()}

vinculados  = 0
sin_empresa = 0

for div_nombre, emp_nombre in MAPEO.items():
    div = divisiones.get(div_nombre)
    emp = empresas.get(emp_nombre)

    if not div:
        print(f"[ADVERTENCIA] Division '{div_nombre}' no encontrada en BD")
        continue
    if not emp:
        print(f"[ADVERTENCIA] Empresa '{emp_nombre}' no encontrada en BD")
        continue

    # Pacientes únicos con alguna cita en esta division
    pacientes_ids = (
        Cita.objects.filter(division=div)
        .values_list('paciente_id', flat=True)
        .distinct()
    )

    for pac_id in pacientes_ids:
        try:
            pac = Paciente.objects.get(id=pac_id)
        except Paciente.DoesNotExist:
            continue

        if pac.empresa is None:
            pac.empresa = emp
            pac.save(update_fields=['empresa'])
            print(f"  [VINCULADO] {pac.nombre} -> {emp.nombre}")
            vinculados += 1
        elif pac.empresa == emp:
            print(f"  [YA VINCULADO] {pac.nombre} -> {emp.nombre}")
        else:
            # Paciente ya tiene otra empresa asignada, no sobreescribir
            print(f"  [CONFLICTO] {pac.nombre} ya tiene empresa '{pac.empresa.nombre}', se deja como está")

print()
print(f"Resultado: {vinculados} paciente(s) vinculado(s).")
