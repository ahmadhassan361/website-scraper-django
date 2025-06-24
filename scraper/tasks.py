from celery import shared_task
import requests
import time
from .models import *
import random
import traceback
from django.utils import timezone
from celery.exceptions import SoftTimeLimitExceeded
import json

# Headers for requests
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15'}

def log_message(session, level, message, product_url=None, product_sku=None, exception_details=None):
    """Helper function to create log entries"""
    ScrapingLog.objects.create(
        session=session,
        level=level,
        message=message,
        product_url=product_url,
        product_sku=product_sku,
        exception_details=exception_details
    )

def extract_shopify_product_variants(product_data, website_name):
    """
    Extract all variants from a Shopify product as separate product records
    
    Args:
        product_data: Single product object from Shopify JSON
        website_name: Name of the website
        
    Returns:
        list: List of product dictionaries (one for each variant)
    """
    try:
        # Extract basic product info that's common to all variants
        title = product_data.get('title', '')
        vendor = product_data.get('vendor', '')
        product_type = product_data.get('product_type', '')
        body_html = product_data.get('body_html', '')
        handle = product_data.get('handle', '')
        product_id = product_data.get('handle', 'id')
        
        # Clean description (remove HTML tags)
        import re
        description = re.sub(r'<[^>]+>', ' ', body_html).strip() if body_html else ''
        
        # Extract all image URLs
        images = product_data.get('images', [])
        image_links = []
        for image in images:
            src = image.get('src', '')
            if src:
                image_links.append(src)
        
        # Create product URL from handle
        product_url = f"https://{website_name}.com/products/{handle}"
        
        # Extract all variants as separate products
        variants = product_data.get('variants', [])
        product_variants = []
        
        if not variants:
            # If no variants, create a single product with basic info
            product_variants.append({
                'name': title,
                'product_variant_id':product_id,
                'sku': '',
                'price': '',
                'vendor': vendor,
                'category': product_type,
                'description': description,
                'in_stock': False,
                'link': product_url,
                'image_link': ', '.join(image_links),
                'website': website_name
            })
        else:
            # Create a separate product for each variant
            for variant in variants:
                variant_sku = variant.get('sku', '')
                variant_price = variant.get('price', '')
                variant_id = variant.get('id', None)
                variant_available = variant.get('available', False)
                
                # Build variant name
                variant_title = title
                
                # Add variant options to the name if they exist
                variant_options = []
                if variant.get('option1') and variant.get('option1') != 'Default Title':
                    variant_options.append(variant.get('option1'))
                if variant.get('option2'):
                    variant_options.append(variant.get('option2'))
                if variant.get('option3'):
                    variant_options.append(variant.get('option3'))
                
                if variant_options:
                    variant_title = f"{title} - {' / '.join(variant_options)}"
                
                product_variants.append({
                    'product_variant_id':variant_id,
                    'name': variant_title,
                    'sku': variant_sku,
                    'price': variant_price,
                    'vendor': vendor,
                    'category': product_type,
                    'description': description,
                    'in_stock': variant_available,
                    'link': product_url,
                    'image_link': ', '.join(image_links),
                    'website': website_name
                })
        
        return product_variants
        
    except Exception as e:
        print(f"Error extracting product variants: {e}")
        return []

def scrape_shopify_products_common(session, website_base_url, custom_domain=None):
    """
    Common function to scrape products from Shopify JSON API
    
    Args:
        session: ScrapingSession object
        website_base_url: Base URL for the website
        custom_domain: Custom domain if different from base URL
        
    Returns:
        dict: Scraping results
    """
    page = 1
    limit = 250
    total_scraped = 0
    
    # Determine the correct domain for API calls
    api_domain = custom_domain if custom_domain else website_base_url
    
    log_message(session, 'info', f'Starting Shopify JSON API scraping for {session.website.name}')
    
    while True:
        try:
            # Construct Shopify products JSON URL
            url = f"https://{api_domain}/products.json?limit={limit}&page={page}"
            
            log_message(session, 'info', f'Fetching page {page}: {url}')
            
            # Make request with delay
            delay = random.randint(10, 20)  # 10-20 seconds as requested
            if page > 1:  # Don't delay on first request
                log_message(session, 'info', f'Waiting {delay} seconds before next request...')
                time.sleep(delay)
            
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            products = data.get('products', [])
            
            if not products:
                log_message(session, 'info', f'No more products found on page {page}. Scraping complete.')
                break
            
            log_message(session, 'info', f'Found {len(products)} products on page {page}')
            
            # Update total products found
            session.total_products_found += len(products)
            session.save()
            
            # Process each product
            for idx, product_data in enumerate(products):
                try:
                    # Extract product information
                    product_info = extract_shopify_product_variants(product_data, session.website.name)
                    
                    if not product_info:
                        session.products_failed += 1
                        continue
                    
                    # Save or update product with robust error handling
                    for prod_variant in product_info:
                        try:
                            if prod_variant['sku']:
                                # Try to get by SKU first
                                try:
                                    product = Product.objects.get(
                                        # website=session.website.name,
                                        product_variant_id=prod_variant['product_variant_id']
                                    )
                                    # Update existing product
                                    for key, value in prod_variant.items():
                                        if key not in ['website']:
                                            setattr(product, key, value)
                                    product.save()
                                    session.products_updated += 1
                                    log_message(session, 'success', f'Updated product: {prod_variant["name"]}', 
                                            product_url=prod_variant['link'], product_sku=prod_variant['sku'])
                                except Product.DoesNotExist:
                                    # Create new product
                                    try:
                                        product = Product.objects.create(**prod_variant)
                                        session.products_created += 1
                                        log_message(session, 'success', f'Created new product: {prod_variant["name"]} {prod_variant["id"]}', 
                                                product_url=prod_variant['link'], product_sku=prod_variant['sku'])
                                    except Exception as create_error:
                                        # Handle race condition - try to get again
                                        try:
                                            product = Product.objects.get(
                                                product_variant_id=prod_variant['product_variant_id']

                                                # website=session.website.name,
                                                # sku=prod_variant['sku']
                                            )
                                            # Update existing product
                                            for key, value in prod_variant.items():
                                                if key not in ['website']:
                                                    setattr(product, key, value)
                                            product.save()
                                            session.products_updated += 1
                                            log_message(session, 'success', f'Updated product (race condition): {prod_variant["name"]}', 
                                                    product_url=prod_variant['link'], product_sku=prod_variant['sku'])
                                        except:
                                            raise create_error
                            else:
                                # No SKU, try by link
                                try:
                                    product = Product.objects.get(
                                        # website=session.website.name,
                                        # link=prod_variant['link']
                                        product_variant_id=prod_variant['product_variant_id']
                                    )
                                    # Update existing product
                                    for key, value in prod_variant.items():
                                        if key not in ['website']:
                                            setattr(product, key, value)
                                    product.save()
                                    session.products_updated += 1
                                    log_message(session, 'success', f'Updated product: {prod_variant["name"]}', 
                                            product_url=prod_variant['link'], product_sku=prod_variant['sku'])
                                except Product.DoesNotExist:
                                    # Create new product
                                    try:
                                        product = Product.objects.create(**prod_variant)
                                        session.products_created += 1
                                        log_message(session, 'success', f'Created new product: {prod_variant["name"]}', 
                                                product_url=prod_variant['link'], product_sku=prod_variant['sku'])
                                    except Exception as create_error:
                                        # Handle race condition - try to get again
                                        try:
                                            product = Product.objects.get(
                                                product_variant_id=prod_variant['product_variant_id']

                                                # website=session.website.name,
                                                # link=prod_variant['link']
                                            )
                                            # Update existing product
                                            for key, value in prod_variant.items():
                                                if key not in ['website']:
                                                    setattr(product, key, value)
                                            product.save()
                                            session.products_updated += 1
                                            log_message(session, 'success', f'Updated product (race condition): {prod_variant["name"]}', 
                                                    product_url=prod_variant['link'], product_sku=prod_variant['sku'])
                                        except:
                                            raise create_error
                            
                            session.products_scraped += 1
                            total_scraped += 1
                            
                            # Update session progress
                            session.last_processed_index = total_scraped
                            session.last_processed_url = url
                            session.save()
                            
                        except Exception as db_error:
                            session.products_failed += 1
                            log_message(session, 'error', f'Database error for product: {str(db_error)}', 
                                    product_url=prod_variant['link'], product_sku=prod_variant['sku'], 
                                    exception_details=traceback.format_exc())
                            continue
                    
                except Exception as product_error:
                    session.products_failed += 1
                    log_message(session, 'error', f'Error processing product: {str(product_error)}', 
                              exception_details=traceback.format_exc())
                    continue
            
            page += 1
            
        except requests.exceptions.RequestException as req_error:
            log_message(session, 'error', f'Request error for page {page}: {str(req_error)}', 
                      product_url=url, exception_details=traceback.format_exc())
            break
            
        except Exception as e:
            log_message(session, 'error', f'Error on page {page}: {str(e)}', 
                      product_url=url, exception_details=traceback.format_exc())
            break
    
    return {
        'status': 'completed',
        'total_found': session.total_products_found,
        'scraped': session.products_scraped,
        'created': session.products_created,
        'updated': session.products_updated,
        'failed': session.products_failed
    }

def scrape_shopify_website_common(session_id, website_config, task_instance, resume_from_page=1):
    """
    Common Shopify scraper function (not a task itself)
    
    Args:
        session_id: ID of the scraping session
        website_config: Dictionary containing website-specific configuration
        task_instance: The calling task instance (self)
        resume_from_page: Page number to resume from (for future use)
    """
    try:
        # Get the scraping session
        session = ScrapingSession.objects.get(id=session_id)
        website = session.website
        
        # Update session status and celery task id
        session.status = 'running'
        session.celery_task_id = task_instance.request.id
        session.save()
        
        # Update website state
        state, created = ScrapingState.objects.get_or_create(website=website)
        state.is_running = True
        state.current_session = session
        state.last_run = timezone.now()
        state.save()
        
        log_message(session, 'info', f'Starting Shopify JSON API scraping session for {website.name}')
        
        try:
            # Use the common scraping function
            result = scrape_shopify_products_common(
                session=session,
                website_base_url=website_config['base_url'],
                custom_domain=website_config.get('custom_domain')
            )
            
            # Mark session as completed
            session.status = 'completed'
            session.completed_at = timezone.now()
            session.save()
            
            # Update website state
            state.is_running = False
            state.save()
            
            log_message(session, 'info', 
                       f'Scraping completed! Total: {session.total_products_found}, '
                       f'Scraped: {session.products_scraped}, '
                       f'Created: {session.products_created}, '
                       f'Updated: {session.products_updated}, '
                       f'Failed: {session.products_failed}')
            
            return result
            
        except SoftTimeLimitExceeded:
            # Handle soft time limit with auto-resume
            log_message(session, 'warning', f'Task soft time limit exceeded. Auto-resuming in 30 seconds...')
            
            # Update session for resumption
            session.status = 'paused'
            session.save()
            
            # Schedule auto-resume task with a 30-second delay
            scrape_shopify_website_common.apply_async(
                args=[session_id, website_config, 1],  # Resume from page 1 for now
                countdown=30  # Wait 30 seconds before resuming
            )
            
            log_message(session, 'info', f'Auto-resume task scheduled')
            
            return {
                'status': 'auto_resuming', 
                'message': f'Task auto-resuming in 30 seconds',
            }
        
    except Exception as e:
        # Handle any unexpected errors
        try:
            session.status = 'failed'
            session.completed_at = timezone.now()
            session.save()
            
            state.is_running = False
            state.save()
            
            log_message(session, 'error', f'Task failed with unexpected error: {str(e)}', 
                       exception_details=traceback.format_exc())
        except:
            # If we can't even log the error, just pass
            pass
        
        return {'status': 'failed', 'message': str(e)}

# Website-specific scraper functions
# Queue management for limiting concurrent scrapers to maximum 2
def check_concurrent_scrapers():
    """Check how many scrapers are currently running"""
    running_count = ScrapingState.objects.filter(is_running=True).count()
    return running_count

def can_start_scraper():
    """Check if we can start a new scraper (max 2 concurrent)"""
    return check_concurrent_scrapers() < 2

@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_waterdale_collection(self, session_id, resume_from_page=1):
    """Scraper for Waterdale Collection with queue management"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_waterdale_collection.apply_async(
            args=[session_id, resume_from_page],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'base_url': 'waterdalecollection.com',
        'custom_domain': None
    }
    return scrape_shopify_website_common(session_id, website_config, self, resume_from_page)

@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_menuchapublishers(self, session_id, resume_from_page=1):
    """Scraper for Menucha Publishers with queue management"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_menuchapublishers.apply_async(
            args=[session_id, resume_from_page],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'base_url': 'menuchapublishers.com',
        'custom_domain': None
    }
    return scrape_shopify_website_common(session_id, website_config, self, resume_from_page)

@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_btshalom(self, session_id, resume_from_page=1):
    """Scraper for BT Shalom with queue management"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_btshalom.apply_async(
            args=[session_id, resume_from_page],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'base_url': 'btshalom.com',
        'custom_domain': None
    }
    return scrape_shopify_website_common(session_id, website_config, self, resume_from_page)

@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_malchutjudaica(self, session_id, resume_from_page=1):
    """Scraper for Malchut Judaica with queue management"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_malchutjudaica.apply_async(
            args=[session_id, resume_from_page],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'base_url': 'malchutjudaica.com',
        'custom_domain': None
    }
    return scrape_shopify_website_common(session_id, website_config, self, resume_from_page)

@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_feldart(self, session_id, resume_from_page=1):
    """Scraper for Feldart with queue management"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_feldart.apply_async(
            args=[session_id, resume_from_page],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'base_url': 'feldart.com',
        'custom_domain': None
    }
    return scrape_shopify_website_common(session_id, website_config, self, resume_from_page)

@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_israelbookshoppublications(self, session_id, resume_from_page=1):
    """Scraper for israelbookshoppublications with queue management"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_feldart.apply_async(
            args=[session_id, resume_from_page],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'base_url': 'israelbookshoppublications.com',
        'custom_domain': None
    }
    return scrape_shopify_website_common(session_id, website_config, self, resume_from_page)


@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_judaicapress(self, session_id, resume_from_page=1):
    """Scraper for judaicapress with queue management"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_feldart.apply_async(
            args=[session_id, resume_from_page],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'base_url': 'judaicapress.com',
        'custom_domain': None
    }
    return scrape_shopify_website_common(session_id, website_config, self, resume_from_page)

@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_hausdecornj(self, session_id, resume_from_page=1):
    """Scraper for hausdecornj with queue management"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_feldart.apply_async(
            args=[session_id, resume_from_page],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'base_url': 'hausdecornj.com',
        'custom_domain': None
    }
    return scrape_shopify_website_common(session_id, website_config, self, resume_from_page)


@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_majesticgiftware(self, session_id, resume_from_page=1):
    """Scraper for majesticgiftware with queue management"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_feldart.apply_async(
            args=[session_id, resume_from_page],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'base_url': 'majesticgiftware.com',
        'custom_domain': None
    }
    return scrape_shopify_website_common(session_id, website_config, self, resume_from_page)

@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_sephardicwarehouse(self, session_id, resume_from_page=1):
    """Scraper for sephardicwarehouse with queue management"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_feldart.apply_async(
            args=[session_id, resume_from_page],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'base_url': 'sephardicwarehouse.com',
        'custom_domain': None
    }
    return scrape_shopify_website_common(session_id, website_config, self, resume_from_page)
@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_torahjudaica(self, session_id, resume_from_page=1):
    """Scraper for torahjudaica with queue management"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_feldart.apply_async(
            args=[session_id, resume_from_page],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'base_url': 'torahjudaica.com',
        'custom_domain': None
    }
    return scrape_shopify_website_common(session_id, website_config, self, resume_from_page)

@shared_task(bind=True, soft_time_limit=3600, time_limit=3660)
def export_products_to_google_sheet(self, export_id, website_filter='all'):
    """
    Export products to Google Sheet in background with progress tracking
    
    Args:
        export_id: ID of the GoogleSheetLinks record
        website_filter: 'all' or specific website name
    """
    import os
    import xlsxwriter
    from io import BytesIO
    from django.conf import settings
    from django.utils import timezone
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    
    try:
        # Get the export record
        export_record = GoogleSheetLinks.objects.get(id=export_id)
        
        # Update status to processing
        export_record.status = 'processing'
        export_record.celery_task_id = self.request.id
        export_record.save()
        
        # Get products based on filter
        if website_filter == 'all':
            products = Product.objects.all().order_by('website', 'created_at')
            filename = f"all_products_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        else:
            products = Product.objects.filter(website=website_filter).order_by('created_at')
            filename = f"{website_filter}_products_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Update total products count
        total_products = products.count()
        export_record.total_products = total_products
        export_record.filename = filename
        export_record.save()
        
        if total_products == 0:
            export_record.status = 'failed'
            export_record.error_message = 'No products found to export'
            export_record.save()
            return {'status': 'failed', 'message': 'No products found to export'}
        
        # Create Excel file in memory
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Products')
        
        # Add headers
        headers = ['Website', 'Name', 'SKU', 'Price', 'Category', 'Vendor', 'InStock', 'Description', 'Image Link', 'Link', 'Created At', 'Updated At']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header)
        
        # Process products in batches
        batch_size = 100
        processed_count = 0
        
        for i in range(0, total_products, batch_size):
            batch_products = products[i:i + batch_size]
            
            for row_offset, product in enumerate(batch_products):
                row = i + row_offset + 1  # +1 for header row
                
                worksheet.write(row, 0, product.website or '')
                worksheet.write(row, 1, product.name or '')
                worksheet.write(row, 2, product.sku or '')
                worksheet.write(row, 3, product.price or '')
                worksheet.write(row, 4, product.category or '')
                worksheet.write(row, 5, product.vendor or '')
                worksheet.write(row, 6, "Yes" if product.in_stock else "No")
                worksheet.write(row, 7, product.description or '')
                worksheet.write_string(row, 8, ", ".join(product.image_link.split(",")[:2]) if product.image_link else '')
                worksheet.write(row, 9, product.link or '')
                worksheet.write(row, 10, product.created_at.strftime('%Y-%m-%d %H:%M:%S') if product.created_at else '')
                worksheet.write(row, 11, product.updated_at.strftime('%Y-%m-%d %H:%M:%S') if product.updated_at else '')
                
                processed_count += 1
                
                # Update progress every 10 products
                if processed_count % 10 == 0:
                    progress = int((processed_count / total_products) * 80)  # 80% for processing data
                    export_record.processed_products = processed_count
                    export_record.progress_percentage = progress
                    export_record.save()
        
        workbook.close()
        output.seek(0)
        
        # Update progress to 80% (data processing complete)
        export_record.progress_percentage = 80
        export_record.save()
        
        # Upload to Google Drive
        SERVICE_ACCOUNT_FILE = os.path.join(settings.BASE_DIR, 'credentials', 'web-scraper-463601-05f99a6d168b.json')
        
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            export_record.status = 'failed'
            export_record.error_message = 'Google Service Account credentials not found'
            export_record.save()
            return {'status': 'failed', 'message': 'Google Service Account credentials not found'}
        
        SCOPES = ['https://www.googleapis.com/auth/drive']
        creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        
        # Update progress to 85% (uploading)
        export_record.progress_percentage = 85
        export_record.save()
        
        # Upload to Google Drive and convert to Google Sheet
        drive_service = build('drive', 'v3', credentials=creds)
        media = MediaIoBaseUpload(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        
        file_metadata = {
            'name': filename,
            'mimeType': 'application/vnd.google-apps.spreadsheet'  # Convert to Google Sheet
        }
        
        uploaded_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        file_id = uploaded_file.get('id')
        
        # Update progress to 95% (making public)
        export_record.progress_percentage = 95
        export_record.save()
        
        # Make it public
        drive_service.permissions().create(
            fileId=file_id,
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()
        
        # Generate public link
        link = f"https://docs.google.com/spreadsheets/d/{file_id}"
        
        # Update export record with completion
        export_record.status = 'completed'
        export_record.link = link
        export_record.progress_percentage = 100
        export_record.completed_at = timezone.now()
        export_record.save()
        
        return {
            'status': 'completed',
            'link': link,
            'total_products': total_products,
            'message': f'Successfully exported {total_products} products to Google Sheet'
        }
        
    except Exception as e:
        # Handle any errors
        try:
            export_record.status = 'failed'
            export_record.error_message = str(e)
            export_record.save()
        except:
            pass
        
        return {'status': 'failed', 'message': str(e)}
