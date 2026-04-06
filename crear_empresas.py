import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from clinica.models import Empresa

empresas = [
    {'username': 'giasa',        'password': 'Giasa2025!',       'nombre': 'GIASA'},
    {'username': 'neapco',       'password': 'Neapco2025!',      'nombre': 'NEAPCO'},
    {'username': 'caritas',      'password': 'Caritas2025!',     'nombre': 'CARITAS'},
    {'username': 'intecdonbosco','password': 'IntecBosco2025!',  'nombre': 'INTEC DON BOSCO'},
    {'username': 'dorothea',     'password': 'Dorothea2025!',    'nombre': 'DOROTHEA'},
]

for e in empresas:
    if not User.objects.filter(username=e['username']).exists():
        user = User.objects.create_user(username=e['username'], password=e['password'])
        Empresa.objects.create(usuario=user, nombre=e['nombre'], activo=True)
        print(f"[CREADO] {e['nombre']} — usuario: {e['username']} / pass: {e['password']}")
    else:
        u = User.objects.get(username=e['username'])
        u.set_password(e['password'])
        u.save()
        if not hasattr(u, 'perfil_empresa'):
            Empresa.objects.create(usuario=u, nombre=e['nombre'], activo=True)
            print(f"[ACTUALIZADO + EMPRESA] {e['nombre']} — usuario: {e['username']}")
        else:
            print(f"[YA EXISTE] {e['nombre']} — usuario: {e['username']} / pass: {e['password']}")
