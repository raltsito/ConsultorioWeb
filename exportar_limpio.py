import os
import django

# Recuerda mantener aquí el nombre real de la carpeta de tus settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.core.management import call_command

print("Iniciando volcado puro en UTF-8 (sin tablas conflictivas)...")
with open('respaldo_puro.json', 'w', encoding='utf-8') as f:
    # Excluimos contenttypes y permisos para evitar choques de IDs
    call_command('dumpdata', exclude=['contenttypes', 'auth.permission'], stdout=f)
print("¡Volcado completado con éxito!")