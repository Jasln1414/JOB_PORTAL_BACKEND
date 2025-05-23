import os
from django.core.asgi import get_asgi_application

# Set the Django settings module before importing anything else
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Import these AFTER setting the environment variable
import django
django.setup()
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from chat.route import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    )
})