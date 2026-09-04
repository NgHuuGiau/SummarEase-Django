# SummarEase production image (gunicorn + whitenoise)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
# Copy source with frontend (templates/static) alongside backend and manage.py at root.
COPY backend ./backend
COPY manage.py .
COPY frontend ./frontend

RUN pip install --upgrade pip && pip install -r requirements.txt \
    && python manage.py collectstatic --noinput --clear

EXPOSE 8000

# Runtime settings come from the environment (DB_ENGINE, DJANGO_SECRET_KEY, ...).
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
