from django.contrib import admin
from .models import Website, Product, ScrapingSession, ScrapingLog, ScrapingState

@admin.register(Website)
class WebsiteAdmin(admin.ModelAdmin):
    list_display = ['name', 'url', 'is_active', 'scraper_function', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'url']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'website', 'sku', 'price', 'created_at', 'updated_at']
    list_filter = ['website', 'created_at', 'updated_at']
    search_fields = ['name', 'sku', 'website']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(ScrapingSession)
class ScrapingSessionAdmin(admin.ModelAdmin):
    list_display = ['website', 'status', 'started_by', 'started_at', 'completed_at', 'products_scraped', 'products_created', 'products_updated', 'products_failed']
    list_filter = ['status', 'website', 'started_at', 'completed_at']
    search_fields = ['website__name', 'started_by__username', 'celery_task_id']
    readonly_fields = ['started_at', 'completed_at', 'celery_task_id']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('website', 'status', 'started_by', 'celery_task_id')
        }),
        ('Statistics', {
            'fields': ('total_products_found', 'products_scraped', 'products_created', 'products_updated', 'products_failed')
        }),
        ('Timestamps', {
            'fields': ('started_at', 'completed_at')
        }),
        ('Resume Data', {
            'fields': ('last_processed_index', 'last_processed_url', 'resume_data'),
            'classes': ['collapse']
        })
    )

@admin.register(ScrapingLog)
class ScrapingLogAdmin(admin.ModelAdmin):
    list_display = ['session', 'level', 'message_short', 'product_sku', 'timestamp']
    list_filter = ['level', 'session__website', 'timestamp']
    search_fields = ['message', 'product_sku', 'product_url']
    readonly_fields = ['timestamp']
    
    def message_short(self, obj):
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
    message_short.short_description = 'Message'

@admin.register(ScrapingState)
class ScrapingStateAdmin(admin.ModelAdmin):
    list_display = ['website', 'is_running', 'current_session', 'last_run']
    list_filter = ['is_running', 'last_run']
    readonly_fields = ['last_run']
