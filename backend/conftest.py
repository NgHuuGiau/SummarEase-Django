import os
import sys
import tempfile

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "*")


def pytest_configure(config):
    from django.conf import settings

    settings.MEDIA_ROOT = tempfile.mkdtemp(prefix="summarease-test-media-")
