"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,re_path,include
from dashboard.views import *
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve

urlpatterns = [
# static and media files urls
    re_path(r'^media/(?P<path>.*)$', serve,{'document_root': settings.MEDIA_ROOT}),
    re_path(r'^static/(?P<path>.*)$', serve,{'document_root': settings.STATIC_ROOT}),
    path('admin/', admin.site.urls),
    
    # Authentication
    path('login/', user_login, name='login'),
    path('logout/', user_logout, name='logout'),
    
    # Dashboard
    path('', home, name='home'),
    
    # Scraping Management
    path('start-scraping/<int:website_id>/', start_scraping, name='start_scraping'),
    path('stop-scraping/<int:website_id>/', stop_scraping, name='stop_scraping'),
    path('resume-scraping/<int:session_id>/', resume_scraping, name='resume_scraping'),
    
    # Bulk Operations
    path('start-all-scraping/', start_all_scraping, name='start_all_scraping'),
    path('stop-all-scraping/', stop_all_scraping, name='stop_all_scraping'),
    
    # Export Functionality
    path('export-products/', export_products, name='export_products'),
    path('export-status/<int:export_id>/', export_status, name='export_status'),
    path('cancel-export/<int:export_id>/', cancel_export, name='cancel_export'),
    
    # Status and Monitoring
    path('website-status/<int:website_id>/', website_status, name='website_status'),
    path('session-details/<int:session_id>/', session_details, name='session_details'),
    path('session-logs/<int:session_id>/', session_logs, name='session_logs'),
    path('session-data/<int:session_id>/', session_data, name='session_data'),
    path('session-history/<int:website_id>/', session_history, name='session_history'),
]+ static(settings.MEDIA_URL,document_root=settings.MEDIA_ROOT)


urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
