import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from clinica.models import Empresa

if not User.objects.filter(username='giasa').exists():
    user = User.objects.create_user(username='giasa', password='Giasa2025!')
    Empresa.objects.create(usuario=user, nombre='GIASA', activo=True)
    print('Usuario GIASA creado correctamente.')
else:
    u = User.objects.get(username='giasa')
    u.set_password('Giasa2025!')
    u.save()
    if not hasattr(u, 'perfil_empresa'):
        Empresa.objects.create(usuario=u, nombre='GIASA', activo=True)
        print('Empresa creada y contraseña actualizada.')
    else:
        print('Contraseña actualizada.')
