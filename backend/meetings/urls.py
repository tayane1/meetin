from django.urls import path
from . import views

app_name = 'meetings'

urlpatterns = [
    path('', views.MeetingListCreateView.as_view(), name='meeting-list'),
    path('<uuid:pk>/', views.MeetingDetailView.as_view(), name='meeting-detail'),
    path('<uuid:meeting_id>/live/start/', views.start_live_session, name='start-live-session'),
    path('<uuid:meeting_id>/live/stop/', views.stop_live_session, name='stop-live-session'),
    path('<uuid:meeting_id>/live/status/', views.live_session_status, name='live-session-status'),
    path('<uuid:meeting_id>/recordings/initiate/', views.initiate_recording, name='initiate-recording'),
    path('<uuid:meeting_id>/recordings/upload/', views.upload_recording, name='upload-recording'),
    path('<uuid:meeting_id>/recordings/<uuid:recording_id>/transcribe/', views.transcribe_recording_view, name='transcribe-recording'),
    path('recordings/<uuid:recording_id>/complete/', views.complete_recording, name='complete-recording'),
    path('<uuid:meeting_id>/speakers/<uuid:speaker_id>/', views.update_speaker, name='update-speaker'),
]