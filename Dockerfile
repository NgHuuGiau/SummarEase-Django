# SummarEase production image (gunicorn + whitenoise)
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && curl -fsSLo /tmp/packages-microsoft-prod.deb https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb \
    && dpkg -i /tmp/packages-microsoft-prod.deb \
    && rm /tmp/packages-microsoft-prod.deb \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 unixodbc-dev libgssapi-krb5-2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Copy source with frontend (templates/static) alongside backend and manage.py at root.
COPY backend ./backend
COPY manage.py .
COPY frontend ./frontend

RUN pip install --upgrade pip && pip install -r requirements.txt \
    && python -c "import pyodbc; assert 'ODBC Driver 18 for SQL Server' in pyodbc.drivers()" \
    && python manage.py collectstatic --noinput --clear \
    && useradd --create-home --user-group --uid 1000 summarizease \
    && mkdir -p /app/backend/sql /app/backend/media \
    && chown -R summarizease:summarizease /app

USER summarizease

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/', timeout=3).status==200 else 1)"

# Runtime settings come from the environment (DB_ENGINE, DJANGO_SECRET_KEY, ...).
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
