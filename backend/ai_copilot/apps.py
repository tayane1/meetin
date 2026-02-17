from django.apps import AppConfig


class AiCopilotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_copilot'
    
    def ready(self):
        # Import signal handlers
        try:
            from . import signals
        except ImportError:
            pass
