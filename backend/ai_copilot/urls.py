from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'ai_copilot'

router = DefaultRouter()
router.register(r'suggestions', views.CopilotSuggestionViewSet, basename='copilot-suggestions')
router.register(r'runs', views.CopilotRunViewSet, basename='copilot-runs')
router.register(r'speaker-mappings', views.SpeakerUserMapViewSet, basename='speaker-mappings')

urlpatterns = [
    path('meetings/<uuid:meeting_id>/', include(router.urls)),
    path('meetings/<uuid:meeting_id>/run/', views.run_copilot_analysis_view, name='run-copilot-analysis'),
    path('meetings/<uuid:meeting_id>/status/', views.copilot_status, name='copilot-status'),
    path('meetings/<uuid:meeting_id>/speakers/<uuid:speaker_id>/map/', views.map_speaker_to_user, name='map-speaker-to-user'),
    path('meetings/<uuid:meeting_id>/speakers/<uuid:speaker_id>/unmap/', views.unmap_speaker, name='unmap-speaker'),
]