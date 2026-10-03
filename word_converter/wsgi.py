"""
WSGI config for word_converter project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'word_converter.settings')

application = get_wsgi_application()
