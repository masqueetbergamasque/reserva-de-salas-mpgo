"""
WSGI config for reserva_mpgo project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reserva_mpgo.settings')
# For temporary diagnostics on PythonAnywhere only:
# os.environ['DJANGO_DEBUG'] = 'true'

application = get_wsgi_application()
