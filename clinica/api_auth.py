from django.http import JsonResponse
from django.conf import settings
from functools import wraps

API_KEY = settings.DJANGO_API_KEY

def api_key_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Permitir si el usuario ya tiene sesion en el navegador
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        # Permitir si viene con API key valida (otro sistema)
        api_key = request.headers.get('X-API-Key', '')
        if api_key and api_key == API_KEY:
            return view_func(request, *args, **kwargs)
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    return _wrapped_view
