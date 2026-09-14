# Production Runbook

## 1. Required configuration

Set these values in a secret manager or deployment environment, never in Git:

```env
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<random-secret-at-least-50-characters>
API_ENCRYPTION_KEY=<fernet-key>
DJANGO_ALLOWED_HOSTS=app.example.com
DB_ENGINE=sqlserver
REDIS_URL=redis://:<password>@redis:6379/0
```

Use a managed database for public deployments. SQLite is suitable only for development or a single-process internal installation.

## 2. Backup and restore

Create a database and media backup at least daily:

```bash
python manage.py backup_db --dest /backups --include-media
```

Each backup contains `db.json`, optional media, and `manifest.json` with a SHA-256 checksum. Copy the complete timestamped folder to storage outside the host/container. Test restore at least monthly on an isolated database; a backup that has never been restored is not verified.

## 3. Health and monitoring

- Probe `/health/` for database and media readiness.
- Scrape `/metrics/` only from the monitoring network; it is protected in production.
- Alert on HTTP 5xx, latency, Celery task failures, queue age, Redis availability, database connections, disk usage and Gemini quota/errors.
- Include deployment version and correlation/request IDs in the log aggregation system.

## 4. Release gate

Before deploying:

```bash
python -m pytest backend/summaries/tests.py -q
ruff check backend manage.py
ruff format --check backend manage.py
python manage.py check --deploy --fail-level ERROR
docker compose config --quiet
```

Run a load test with the expected peak concurrency and perform an OWASP review for every public release. Record the result and rollback target.

## 5. Recovery

1. Stop receiving traffic or roll back to the last known-good image.
2. Preserve logs and metrics before restarting workers.
3. Restore the database only after verifying the backup manifest checksum.
4. Reconcile media and database records, then run health and smoke tests.
5. Rotate exposed secrets and document the incident.
