from django.urls import path
from . import views

app_name = 'transcription'

urlpatterns = [
    path('meetings/<uuid:meeting_id>/transcript/', views.TranscriptDetailView.as_view(), name='transcript-detail'),
    path('meetings/<uuid:meeting_id>/minutes/generate/', views.generate_minutes_view, name='generate-minutes'),
    path('meetings/<uuid:meeting_id>/minutes/', views.MinutesDetailView.as_view(), name='minutes-detail'),
    path('meetings/<uuid:meeting_id>/minutes/versions/', views.MinutesVersionListView.as_view(), name='minutes-versions'),
    path('meetings/<uuid:meeting_id>/action-items/', views.ActionItemListView.as_view(), name='action-items'),
    path('meetings/<uuid:meeting_id>/action-items/<uuid:pk>/', views.ActionItemDetailView.as_view(), name='action-item-detail'),
]