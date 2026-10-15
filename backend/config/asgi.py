import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from django.urls import path
from django.conf import settings
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler

http_application = get_asgi_application()
# Serve static files when running Daphne in development.
if settings.DEBUG:
    http_application = ASGIStaticFilesHandler(http_application)
from backend.support.consumers import SupportConsumer

application = ProtocolTypeRouter({
    "http": http_application,
    "websocket": AuthMiddlewareStack(URLRouter([
        path("ws/support/<int:conversation_id>/", SupportConsumer.as_asgi()),
    ])),
})
