import json
from django.shortcuts import render
from django.conf import settings
import os

def portafolio(request):
    # Ruta al archivo JSON
    json_file_path = os.path.join(settings.BASE_DIR, 'servicios', 'static', 'data.json')

    # Leer el archivo JSON
    with open(json_file_path, 'r') as f:
        servicios = json.load(f)

    return render(request, 'servicios/portafolio.html', {'servicios': servicios})
