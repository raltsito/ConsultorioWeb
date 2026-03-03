import os
import django
import unicodedata

# --- CONFIGURACION DE DJANGO ---
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings') 
django.setup()

from django.contrib.auth.models import User
from clinica.models import Terapeuta, Paciente

def generar_username(nombre_completo):
    # Quitar acentos y convertir espacios en puntos para el usuario (ej. ana.reyna)
    sin_acentos = ''.join(c for c in unicodedata.normalize('NFD', nombre_completo) if unicodedata.category(c) != 'Mn')
    return sin_acentos.lower().replace(' ', '.')

def aprovisionar_cuentas():
    print("Iniciando aprovisionamiento de cuentas del sistema...")
    password_temporal = 'Intra2026*'
    
    # 1. TERAPEUTAS
    # Nota: Si el campo en tu modelo Terapeuta se llama 'user' en lugar de 'usuario', cambialo aqui
    terapeutas_sin_cuenta = Terapeuta.objects.filter(usuario__isnull=True) 
    
    for t in terapeutas_sin_cuenta:
        base_username = generar_username(t.nombre)
        username = base_username
        contador = 1
        
        # Evitar nombres de usuario duplicados
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{contador}"
            contador += 1
            
        nuevo_user = User.objects.create_user(username=username, password=password_temporal)
        
        # Vincular la cuenta al expediente del terapeuta
        t.usuario = nuevo_user
        t.save()
        print(f"Terapeuta vinculado: {t.nombre} -> User: {username} | Pass: {password_temporal}")

    # 2. PACIENTES (Opcional - Quita los '#' si quieres crearle cuenta a los 600 pacientes)
    # pacientes_sin_cuenta = Paciente.objects.filter(usuario__isnull=True)
    # for p in pacientes_sin_cuenta:
    #     base_username = generar_username(p.nombre)
    #     username = base_username
    #     contador = 1
    #     while User.objects.filter(username=username).exists():
    #         username = f"{base_username}{contador}"
    #         contador += 1
    #         
    #     nuevo_user = User.objects.create_user(username=username, password=password_temporal)
    #     p.usuario = nuevo_user
    #     p.save()
    #     print(f"Paciente vinculado: {p.nombre} -> User: {username}")

    print("-" * 30)
    print("¡Aprovisionamiento completado!")

if __name__ == "__main__":
    aprovisionar_cuentas()