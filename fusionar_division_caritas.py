"""
Script: fusionar_division_caritas.py
Fusiona 'Critas de Saltillo' en 'Cáritas de Saltillo'.
Reasigna todos los registros relacionados y elimina el duplicado.
"""
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from clinica.models import Division, Empresa, Cita, SolicitudCita, AperturaExpediente

CONSERVAR = 'Cáritas de Saltillo'
ELIMINAR  = 'Critas de Saltillo'

# Obtener o crear la división correcta
destino, created = Division.objects.get_or_create(nombre=CONSERVAR)
if created:
    print(f"[CREADA] División '{CONSERVAR}'")
else:
    print(f"[OK] División destino: '{CONSERVAR}' (id={destino.id})")

try:
    origen = Division.objects.get(nombre=ELIMINAR)
except Division.DoesNotExist:
    print(f"[INFO] '{ELIMINAR}' no existe en la BD. Nada que fusionar.")
    exit()

print(f"[OK] División origen:  '{ELIMINAR}' (id={origen.id})")
print()

# Reasignar Citas
n = Cita.objects.filter(division=origen).update(division=destino)
print(f"[Cita]               {n} registro(s) reasignado(s)")

# Reasignar SolicitudCita
n = SolicitudCita.objects.filter(division=origen).update(division=destino)
print(f"[SolicitudCita]      {n} registro(s) reasignado(s)")

# Reasignar AperturaExpediente
n = AperturaExpediente.objects.filter(division=origen).update(division=destino)
print(f"[AperturaExpediente] {n} registro(s) reasignado(s)")

# Reasignar Empresa
n = Empresa.objects.filter(division=origen).update(division=destino)
print(f"[Empresa]            {n} registro(s) reasignado(s)")

# Eliminar el duplicado
origen.delete()
print()
print(f"[ELIMINADA] División '{ELIMINAR}'")
print(f"[LISTO] Todo apunta ahora a '{CONSERVAR}' (id={destino.id})")
