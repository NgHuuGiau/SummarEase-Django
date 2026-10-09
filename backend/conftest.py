import os
import sys
import tempfile

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "*")
os.environ.setdefault("DJANGO_TEST", "1")

_TEST_MEDIA_DIR = None


def pytest_configure(config):
    global _TEST_MEDIA_DIR
    from django.conf import settings

    _TEST_MEDIA_DIR = tempfile.TemporaryDirectory(prefix="summarease-test-media-")
    settings.MEDIA_ROOT = _TEST_MEDIA_DIR.name


def pytest_unconfigure(config):
    if _TEST_MEDIA_DIR is not None:
        _TEST_MEDIA_DIR.cleanup()
