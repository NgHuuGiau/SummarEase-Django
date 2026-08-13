from django.core.wsgi import get_wsgi_application

from ._setup import *  # noqa: F401, F403

application = get_wsgi_application()
