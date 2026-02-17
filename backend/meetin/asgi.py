import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import re_path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meetin.settings')

django_asgi_app = get_asgi_application()

from transcription.consumers import LiveTranscriptionConsumer
from transcription.middleware import JWTAuthMiddleware

websocket_urlpatterns = [
    re_path(r'ws/meetings/(?P<meeting_id>[0-9a-f-]+)/live/$', LiveTranscriptionConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        JWTAuthMiddleware(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
