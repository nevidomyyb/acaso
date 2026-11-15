# Imagem acaso-api: Flask + flask-smorest servido por gunicorn (ADR-002). Só lê a base analítica.
FROM python:3.13-slim

WORKDIR /app
COPY backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
# 2 workers síncronos: as consultas são SELECTs curtos; access log fica no log JSON da própria API
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "30", "wsgi:app"]
