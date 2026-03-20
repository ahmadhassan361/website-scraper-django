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
    sheet_file_id = models.CharField(max_length=255, null=True, blank=True)  # Google Drive file ID for reusing sheet
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
    product_variant_id = models.CharField(max_length=500,null=True,blank=True,unique=True)     # website
    website = models.CharField(max_length=300,null=True,blank=True)     # website
    name = models.CharField(max_length=500,null=True,blank=True)        # Item name
    sku = models.CharField(max_length=250, null=True, blank=True)       # Item number
    price = models.CharField(max_length=50, null=True, blank=True)      # price
    vendor = models.CharField(max_length=400, null=True, blank=True)     # vendor
    category = models.CharField(max_length=400, null=True, blank=True)   # category
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


# ==================== PRODUCT SYNC MODELS ====================

class VendorConfiguration(models.Model):
    """Model to store vendor-specific configuration for product sync"""
    website = models.OneToOneField(Website, on_delete=models.CASCADE, related_name='vendor_config')
    
    # Vendor identification
    vendor_id = models.IntegerField(help_text="Vendor ID for website upload CSV")
    sku_prefix = models.CharField(max_length=50, blank=True, default='', 
                                   help_text="Prefix added to SKU (e.g., 'RLC-', 'IBSLA')")
    
    # Pricing configuration
    markup_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00,
                                           help_text="Percentage to adjust price (+/- %). Example: 15.00 for 15% markup")
    
    # Default settings for products
    default_category_id = models.CharField(max_length=100, blank=True, default='',
                                           help_text="Default category ID for website")
    default_product_type_id = models.CharField(max_length=100, blank=True, default='3',
                                               help_text="Default product type ID")
    track_inventory = models.BooleanField(default=True,
                                         help_text="Default: Track inventory for this vendor")
    sell_out_of_stock = models.BooleanField(default=True,
                                           help_text="Default: Allow selling when out of stock")
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Vendor Configuration"
        verbose_name_plural = "Vendor Configurations"
        ordering = ['website__name']
    
    def __str__(self):
        return f"{self.website.name} - Prefix: {self.sku_prefix or 'None'}"
    
    def apply_sku_transform(self, original_sku):
        """Add vendor prefix to SKU"""
        if not original_sku:
            return ''
        if self.sku_prefix:
            return f"{self.sku_prefix}{original_sku}"
        return original_sku
    
    def remove_sku_prefix(self, prefixed_sku):
        """Remove vendor prefix from SKU to get original"""
        if not prefixed_sku or not self.sku_prefix:
            return prefixed_sku
        if prefixed_sku.startswith(self.sku_prefix):
            return prefixed_sku[len(self.sku_prefix):]
        return prefixed_sku
    
    def apply_price_markup(self, original_price):
        """Apply markup percentage to price"""
        from decimal import Decimal
        try:
            # Clean the price string and convert to Decimal
            cleaned_price = str(original_price).replace('$', '').replace(',', '').strip()
            price = Decimal(cleaned_price)
            
            if self.markup_percentage != 0:
                # Convert markup_percentage to Decimal for calculation
                markup_decimal = Decimal(str(self.markup_percentage))
                markup_multiplier = Decimal('1') + (markup_decimal / Decimal('100'))
                new_price = price * markup_multiplier
                return f"${new_price:.2f}"
            return f"${price:.2f}"
        except (ValueError, AttributeError, Exception) as e:
            # If anything fails, return original price
            return original_price


class ProductSyncStatus(models.Model):
    """Model to track product synchronization status with website"""
    STATUS_CHOICES = [
        ('new', 'New - Not on Website'),
        ('synced', 'Synced - On Website'),
        ('updated', 'Updated - Needs Re-sync'),
        ('removed', 'Removed from Website'),
    ]
    
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='sync_status')
    
    # Website status
    on_website = models.BooleanField(default=False, 
                                     help_text="Is this product currently on the website?")
    website_sku = models.CharField(max_length=500, blank=True, default='',
                                   help_text="SKU format as it appears on website (with prefix)")
    website_product_id = models.CharField(max_length=100, blank=True, default='',
                                         help_text="Product ID from website export")
    
    # Sync tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    last_synced_at = models.DateTimeField(null=True, blank=True,
                                          help_text="Last time this product was synced")
    last_export_at = models.DateTimeField(null=True, blank=True,
                                         help_text="Last time included in export")
    
    # User selection
    selected_for_export = models.BooleanField(default=False,
                                             help_text="Selected by user for next export")
    is_disabled = models.BooleanField(default=False,
                                             help_text="disable for never sync")
    
    # Custom overrides (optional - override vendor defaults)
    custom_category_id = models.CharField(max_length=100, blank=True, default='',
                                         help_text="Override default category")
    custom_price = models.CharField(max_length=50, blank=True, default='',
                                    help_text="Override scraped price")
    custom_track_inventory = models.BooleanField(null=True, blank=True,
                                                 help_text="Override default inventory tracking")
    custom_sell_out_of_stock = models.BooleanField(null=True, blank=True,
                                                   help_text="Override default out of stock selling")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Product Sync Status"
        verbose_name_plural = "Product Sync Statuses"
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['on_website']),
            models.Index(fields=['status']),
            models.Index(fields=['selected_for_export']),
        ]
    
    def __str__(self):
        return f"{self.product.name} - {self.get_status_display()}"
    
    def mark_on_website(self, website_sku, website_product_id=''):
        """Mark product as synced to website"""
        from django.utils import timezone
        self.on_website = True
        self.website_sku = website_sku
        self.website_product_id = website_product_id
        self.status = 'synced'
        self.last_synced_at = timezone.now()
        self.save()
    
    def mark_as_new(self):
        """Mark product as new (not on website)"""
        self.on_website = False
        self.status = 'new'
        self.save()


class WebsiteImportLog(models.Model):
    """Model to log website product imports"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    filename = models.CharField(max_length=500)
    vendor_website = models.CharField(max_length=100, blank=True, default='', help_text="Vendor/website being compared")
    celery_task_id = models.CharField(max_length=255, null=True, blank=True)
    
    # Statistics
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_rows = models.IntegerField(default=0, help_text="Total rows in CSV")
    processed_rows = models.IntegerField(default=0)
    matched_products = models.IntegerField(default=0, help_text="Products matched in database")
    new_products_found = models.IntegerField(default=0, help_text="Products in DB but not in import")
    skipped_rows = models.IntegerField(default=0)
    progress_percentage = models.IntegerField(default=0)
    
    # Error tracking
    error_message = models.TextField(blank=True, default='')
    
    # Metadata
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Website Import Log"
        verbose_name_plural = "Website Import Logs"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Import {self.id} - {self.filename} - {self.get_status_display()}"
