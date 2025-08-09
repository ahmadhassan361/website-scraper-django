from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Website(models.Model):
    """Model to manage different websites for scraping"""
    name = models.CharField(max_length=100, unique=True)
    url = models.URLField()
    is_active = models.BooleanField(default=True)
    scraper_function = models.CharField(max_length=100)  # Name of the scraper function
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

class GoogleSheetLinks(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    link = models.TextField(null=True, blank=True)                # Google Sheet link
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    celery_task_id = models.CharField(max_length=255, null=True, blank=True)
    filename = models.CharField(max_length=300, null=True, blank=True)
    total_products = models.IntegerField(default=0)
    processed_products = models.IntegerField(default=0)
    progress_percentage = models.IntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)
    website_filter = models.CharField(max_length=100, null=True, blank=True)  # 'all' or website name
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Export {self.id} - {self.status} - {self.created_at}"

class Product(models.Model):
    product_variant_id = models.CharField(max_length=300,null=True,blank=True,unique=True)     # website
    website = models.CharField(max_length=300,null=True,blank=True)     # website
    name = models.CharField(max_length=300,null=True,blank=True)        # Item name
    sku = models.CharField(max_length=250, null=True, blank=True)       # Item number
    price = models.CharField(max_length=50, null=True, blank=True)      # price
    vendor = models.CharField(max_length=50, null=True, blank=True)     # vendor
    category = models.CharField(max_length=50, null=True, blank=True)   # category
    description = models.TextField(null=True, blank=True)               # Description
    in_stock = models.BooleanField(default=False)                       # In Stock
    link = models.TextField(null=True, blank=True)                      # link
    image_link = models.TextField(null=True, blank=True)                # image_link
    created_at = models.DateTimeField(auto_now_add=True)                # created_at
    updated_at = models.DateTimeField(auto_now=True)                    # updated_at
    
    # class Meta:
        # Ensure unique products per website based on SKU or link
        # unique_together = [['website', 'sku'], ['website', 'link']]
    
    def __str__(self):
        return f"{self.website} - {self.name}"

class ScrapingSession(models.Model):
    """Model to track scraping sessions"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('stopped', 'Stopped'),
        ('paused', 'Paused'),
    ]
    
    website = models.ForeignKey(Website, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    celery_task_id = models.CharField(max_length=255, null=True, blank=True)
    started_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Statistics
    total_products_found = models.IntegerField(default=0)
    products_scraped = models.IntegerField(default=0)
    products_updated = models.IntegerField(default=0)
    products_created = models.IntegerField(default=0)
    products_failed = models.IntegerField(default=0)
    
    # Timestamps
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Resume functionality
    last_processed_index = models.IntegerField(default=0)
    last_processed_url = models.TextField(null=True, blank=True)
    resume_data = models.JSONField(default=dict, blank=True)  # Store any additional resume data
    
    def __str__(self):
        return f"{self.website.name} - {self.status} - {self.started_at}"
    
    @property
    def duration(self):
        if self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        return None

class ScrapingLog(models.Model):
    """Model to store detailed logs for each scraping action"""
    LOG_LEVELS = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('success', 'Success'),
    ]
    
    session = models.ForeignKey(ScrapingSession, on_delete=models.CASCADE, related_name='logs')
    level = models.CharField(max_length=10, choices=LOG_LEVELS, default='info')
    message = models.TextField()
    product_url = models.TextField(null=True, blank=True)
    product_sku = models.CharField(max_length=250, null=True, blank=True)
    exception_details = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.session.website.name} - {self.level} - {self.timestamp}"

class ScrapingState(models.Model):
    """Model to store the current state of scraping operations"""
    website = models.OneToOneField(Website, on_delete=models.CASCADE)
    is_running = models.BooleanField(default=False)
    current_session = models.ForeignKey(ScrapingSession, on_delete=models.SET_NULL, null=True, blank=True)
    last_run = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.website.name} - {'Running' if self.is_running else 'Idle'}"

class GoogleOAuth2Token(models.Model):
    """Model to store Google OAuth2 tokens for accessing Google Drive/Sheets"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    access_token = models.TextField()
    refresh_token = models.TextField()
    token_uri = models.URLField(default='https://oauth2.googleapis.com/token')
    client_id = models.TextField()
    client_secret = models.TextField()
    scopes = models.JSONField(default=list)  # Store scopes as JSON array
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"OAuth2 Token - {self.user.username if self.user else 'System'} - {'Active' if self.is_active else 'Inactive'}"
    
    @property
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at
