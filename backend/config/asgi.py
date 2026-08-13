from django.core.asgi import get_asgi_application

from ._setup import *  # noqa: F401, F403

application = get_asgi_application()
