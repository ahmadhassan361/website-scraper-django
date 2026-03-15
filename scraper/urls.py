from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import sync_views
from . import api_views

app_name = 'scraper'

# API Router for REST endpoints
api_router = DefaultRouter()
api_router.register(r'products', api_views.ProductExportViewSet, basename='product-api')
api_router.register(r'bulk-export', api_views.ProductBulkExportViewSet, basename='bulk-export')

urlpatterns = [
    # API URLs
    path('api/', include(api_router.urls)),
    
    # Google OAuth2 URLs
    path('google/authorize/', views.google_oauth2_authorize, name='google_oauth2_authorize'),
    path('google/callback/', views.google_oauth2_callback, name='google_oauth2_callback'),
    path('google/status/', views.google_oauth2_status, name='google_oauth2_status'),
    path('google/revoke/', views.google_oauth2_revoke, name='google_oauth2_revoke'),
    path('google/setup/', views.google_oauth2_setup_instructions, name='google_oauth2_setup'),
    
    # Product Sync URLs
    path('vendors/', sync_views.vendor_management, name='vendor_management'),
    path('vendors/<int:website_id>/edit/', sync_views.vendor_config_edit, name='vendor_config_edit'),
    path('sync/', sync_views.product_sync_dashboard, name='product_sync_dashboard'),
    path('sync/toggle-selection/', sync_views.toggle_product_selection, name='toggle_product_selection'),
    path('sync/bulk-select/', sync_views.bulk_select_products, name='bulk_select_products'),
    path('sync/import/', sync_views.import_website_products, name='import_website_products'),
    path('sync/import/<int:import_log_id>/status/', sync_views.import_status, name='import_status'),
    path('sync/export/', sync_views.export_selected_products, name='export_selected_products'),
    path('sync/export/<str:task_id>/status/', sync_views.export_status, name='export_status'),
    path('sync/download/<str:filename>/', sync_views.download_export, name='download_export'),
    path('sync/import-history/', sync_views.import_history, name='import_history'),
]
