"""Ponto de entrada do gunicorn: gunicorn wsgi:app"""

from api import create_app

app = create_app()
