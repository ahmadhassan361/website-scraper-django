from django.urls import path
from . import views

app_name = 'scraper'

urlpatterns = [
    # Google OAuth2 URLs
    path('google/authorize/', views.google_oauth2_authorize, name='google_oauth2_authorize'),
    path('google/callback/', views.google_oauth2_callback, name='google_oauth2_callback'),
    path('google/status/', views.google_oauth2_status, name='google_oauth2_status'),
    path('google/revoke/', views.google_oauth2_revoke, name='google_oauth2_revoke'),
    path('google/setup/', views.google_oauth2_setup_instructions, name='google_oauth2_setup'),
]
