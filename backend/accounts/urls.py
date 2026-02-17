from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('profile/', views.user_profile, name='profile'),
    path('organizations/', views.OrganizationListCreateView.as_view(), name='organization-list'),
    path('organizations/<uuid:pk>/', views.OrganizationDetailView.as_view(), name='organization-detail'),
    path('organizations/<uuid:org_id>/members/', views.OrganizationMemberListView.as_view(), name='organization-members'),
]