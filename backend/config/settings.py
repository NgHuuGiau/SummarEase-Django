import os
import secrets
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
SQL_DIR = BACKEND_DIR / "sql"
ENV_FILE = BACKEND_DIR / ".env"


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        os.environ.setdefault(key, value)


load_env_file(ENV_FILE)

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY") or secrets.token_urlsafe(50)
DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = [host for host in os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",") if host]
TRUSTED_PROXY_IPS = tuple(
    address.strip() for address in os.getenv("TRUSTED_PROXY_IPS", "").split(",") if address.strip()
)

if not DEBUG:
    if not os.getenv("DJANGO_SECRET_KEY"):
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production.")
    if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be restricted in production.")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "drf_spectacular",
    "summaries",
]

MIDDLEWARE = [
    "config.request_id.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "config.csp.CSPMiddleware",
    "summaries.middleware.RateLimitMiddleware",
    "summaries.metrics.PrometheusMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [FRONTEND_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"

db_engine = os.getenv("DB_ENGINE", "sqlite").lower()
if (
    not DEBUG
    and os.getenv("DJANGO_REQUIRE_EXTERNAL_DATABASE", "").lower() == "true"
    and db_engine not in {"mysql", "sqlserver"}
):
    raise ImproperlyConfigured(
        "This multi-process deployment requires DB_ENGINE=mysql or DB_ENGINE=sqlserver."
    )

if db_engine == "mysql":
    try:
        import pymysql
    except ImportError as exc:
        raise ImportError(
            "DB_ENGINE=mysql requires PyMySQL. Install dependencies with "
            "'pip install -r requirements.txt' or switch DB_ENGINE back to sqlite."
        ) from exc

    pymysql.install_as_MySQLdb()
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("DB_NAME", "summarease_django"),
            "USER": os.getenv("DB_USER", "root"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "3306"),
            "CONN_MAX_AGE": 3600,
            "OPTIONS": {
                "charset": "utf8mb4",
                "connect_timeout": 10,
            },
        }
    }
elif db_engine == "sqlserver":
    db_options = {
        "driver": os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server"),
        "extra_params": "TrustServerCertificate=yes;Encrypt=yes",
    }
    if os.getenv("DB_USE_WINDOWS_AUTH", "").lower() == "true":
        db_options["extra_params"] += ";Trusted_Connection=yes"
        db_config = {
            "ENGINE": "mssql",
            "NAME": os.getenv("DB_NAME", "SummarEase_Django"),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "1433"),
            "CONN_MAX_AGE": 3600,
            "OPTIONS": db_options,
        }
    else:
        db_config = {
            "ENGINE": "mssql",
            "NAME": os.getenv("DB_NAME", "SummarEase_Django"),
            "USER": os.getenv("DB_USER", "sa"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "1433"),
            "CONN_MAX_AGE": 3600,
            "OPTIONS": db_options,
        }
    DATABASES = {"default": db_config}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.getenv("SQLITE_DB_PATH", str(SQL_DIR / "db.sqlite3")),
            "CONN_MAX_AGE": 0,
            "OPTIONS": {
                "timeout": 30,
            },
        }
    }

LANGUAGE_CODE = "vi"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True

# ── Static files ────────────────────────────────────
STATIC_URL = "/static/"
STATICFILES_DIRS = [FRONTEND_DIR / "static"]
STATIC_ROOT = BACKEND_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# ── Media files ──────────────────────────────────────
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", str(BACKEND_DIR / "media")))

# ── Gemini ───────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# ── Encryption (dedicated key for API key storage) ──
API_ENCRYPTION_KEY = os.getenv("API_ENCRYPTION_KEY", "")
API_ENCRYPTION_KEY_EXPLICIT = bool(API_ENCRYPTION_KEY)

# Legacy key derived from SECRET_KEY (for backward compat with existing encrypted values)
_LEGACY_API_KEY = ""
if not API_ENCRYPTION_KEY:
    if DEBUG:
        # Dev: derive from SECRET_KEY for convenience
        import hashlib

        _LEGACY_API_KEY = hashlib.sha256(SECRET_KEY.encode()).hexdigest()[:32]
        API_ENCRYPTION_KEY = _LEGACY_API_KEY
    else:
        # Production: require explicit key, fail fast
        raise ImproperlyConfigured(
            "API_ENCRYPTION_KEY must be set in production (DEBUG=False). "
            "Generate with: python -c 'from cryptography.fernet import "
            "Fernet; print(Fernet.generate_key().decode())'"
        )

# ── Security (hardened when DEBUG=False) ────────────
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_SSL_REDIRECT = False if DEBUG else True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_USE_SESSIONS = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if not DEBUG else None
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# ── Auth ──────────────────────────────────────────────
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

# ── Email ─────────────────────────────────────────────
# Mặc định in ra console cho dev; production: EMAIL_BACKEND=smtp + host/port/user/pass
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@summarease.local")
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
if EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend":
    EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "1") == "1"

# ── Cache & Session ──────────────────────────────────
redis_url = os.getenv("REDIS_URL", "")
if redis_url:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": redis_url,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "summarease-cache",
        }
    }
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

# ── Search (disable for SQLite tests) ──────────────────
ENABLE_FULLTEXT_SEARCH = os.getenv("ENABLE_FULLTEXT_SEARCH", "true").lower() == "true"
if os.getenv("DJANGO_TEST") == "1":
    ENABLE_FULLTEXT_SEARCH = False

# ── Celery ─────────────────────────────────────────────
# Test mode: use eager (synchronous) execution
if os.getenv("DJANGO_TEST") == "1":
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    CELERY_BROKER_URL = "memory://"
    CELERY_RESULT_BACKEND = "cache+memory://"
elif redis_url:
    CELERY_BROKER_URL = redis_url
    CELERY_RESULT_BACKEND = redis_url
else:
    CELERY_BROKER_URL = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND = "redis://localhost:6379/0"

CELERY_TASK_TRACK_STARTED = True
CELERY_RESULT_EXPIRES = 60 * 60
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_WORKER_MAX_TASKS_PER_CHILD = 100
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_BEAT_SCHEDULE = {
    "enqueue-pending-webhook-deliveries": {
        "task": "summaries.tasks.enqueue_pending_webhook_deliveries",
        "schedule": 60.0,
    }
}

# ── Rate limiting ──────────────────────────────────
RATE_LIMIT_SECONDS = 5

# ── Upload ───────────────────────────────────────────
FILE_UPLOAD_MAX_MEMORY_SIZE = 1 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000

# ── Logging ──────────────────────────────────────────
# Bật JSON structured logs cho production: LOG_FORMAT=json, LOG_FILE=/path/to/app.log
LOG_FORMAT = os.getenv("LOG_FORMAT", "json" if not DEBUG else "text")
LOG_FILE = os.getenv("LOG_FILE", "")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        "json": {
            "()": "config.logging_fmt.JsonFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if LOG_FORMAT == "json" else "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO" if DEBUG else "WARNING",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

if LOG_FILE:
    LOGGING["handlers"]["file"] = {  # type: ignore[index]
        "class": "logging.handlers.RotatingFileHandler",
        "filename": LOG_FILE,
        "maxBytes": 5 * 1024 * 1024,
        "backupCount": 5,
        "encoding": "utf-8",
        "formatter": "json",
    }
    LOGGING["root"]["handlers"] = ["console", "file"]  # type: ignore[index]
    for _name, _cfg in LOGGING["loggers"].items():  # type: ignore[attr-defined]
        _cfg["handlers"] = ["console", "file"]  # type: ignore[index]

if DEBUG:
    SILENCED_SYSTEM_CHECKS = [
        "security.W004",  # SECURE_HSTS_SECONDS (0 trong dev)
        "security.W008",  # SECURE_SSL_REDIRECT (False trong dev)
        "security.W012",  # SESSION_COOKIE_SECURE (False trong dev)
        "security.W016",  # CSRF_COOKIE_SECURE (False trong dev)
        "security.W018",  # DEBUG=True (cố ý trong dev)
        "security.W009",  # SECRET_KEY length (auto-gen fallback)
    ]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── DRF ────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# ── DRF Spectacular (API docs) ─────────────────────────
SPECTACULAR_SETTINGS = {
    "TITLE": "SummarEase API",
    "DESCRIPTION": "API for text summarization (TextRank + Gemini)",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "displayOperationId": True,
    },
    "COMPONENT_SPLIT_REQUEST": True,
}
