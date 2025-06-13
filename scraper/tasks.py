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

def extract_shopify_product_data(product_data, website_name):
    """
    Common function to extract product data from Shopify JSON API response
    
    Args:
        product_data: Single product object from Shopify JSON
        website_name: Name of the website
        
    Returns:
        dict: Extracted product information
    """
    try:
        # Extract basic product info
        title = product_data.get('title', '')
        vendor = product_data.get('vendor', '')
        product_type = product_data.get('product_type', '')
        body_html = product_data.get('body_html', '')
        handle = product_data.get('handle', '')
        
        # Clean description (remove HTML tags)
        import re
        description = re.sub(r'<[^>]+>', ' ', body_html).strip() if body_html else ''
        
        # Extract first variant data (SKU and price)
        variants = product_data.get('variants', [])
        sku = ''
        price = ''
        if variants:
            first_variant = variants[0]
            sku = first_variant.get('sku', '')
            price = first_variant.get('price', '')
        
        # Extract all image URLs
        images = product_data.get('images', [])
        image_links = []
        for image in images:
            src = image.get('src', '')
            if src:
                image_links.append(src)
        
        # Create product URL from handle
        # This will need to be customized per website
        product_url = f"https://{website_name}.com/products/{handle}"
        
        return {
            'name': title,
            'sku': sku,
            'price': price,
            'vendor': vendor,
            'category': product_type,
            'description': description,
            'link': product_url,
            'image_link': ', '.join(image_links),
            'website': website_name
        }
    except Exception as e:
        print(f"Error extracting product data: {e}")
        return None

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
                    product_info = extract_shopify_product_data(product_data, session.website.name)
                    
                    if not product_info:
                        session.products_failed += 1
                        continue
                    
                    # Save or update product with robust error handling
                    try:
                        if product_info['sku']:
                            # Try to get by SKU first
                            try:
                                product = Product.objects.get(
                                    website=session.website.name,
                                    sku=product_info['sku']
                                )
                                # Update existing product
                                for key, value in product_info.items():
                                    if key not in ['website']:
                                        setattr(product, key, value)
                                product.save()
                                session.products_updated += 1
                                log_message(session, 'success', f'Updated product: {product_info["name"]}', 
                                          product_url=product_info['link'], product_sku=product_info['sku'])
                            except Product.DoesNotExist:
                                # Create new product
                                try:
                                    product = Product.objects.create(**product_info)
                                    session.products_created += 1
                                    log_message(session, 'success', f'Created new product: {product_info["name"]}', 
                                              product_url=product_info['link'], product_sku=product_info['sku'])
                                except Exception as create_error:
                                    # Handle race condition - try to get again
                                    try:
                                        product = Product.objects.get(
                                            website=session.website.name,
                                            sku=product_info['sku']
                                        )
                                        # Update existing product
                                        for key, value in product_info.items():
                                            if key not in ['website']:
                                                setattr(product, key, value)
                                        product.save()
                                        session.products_updated += 1
                                        log_message(session, 'success', f'Updated product (race condition): {product_info["name"]}', 
                                                  product_url=product_info['link'], product_sku=product_info['sku'])
                                    except:
                                        raise create_error
                        else:
                            # No SKU, try by link
                            try:
                                product = Product.objects.get(
                                    website=session.website.name,
                                    link=product_info['link']
                                )
                                # Update existing product
                                for key, value in product_info.items():
                                    if key not in ['website']:
                                        setattr(product, key, value)
                                product.save()
                                session.products_updated += 1
                                log_message(session, 'success', f'Updated product: {product_info["name"]}', 
                                          product_url=product_info['link'], product_sku=product_info['sku'])
                            except Product.DoesNotExist:
                                # Create new product
                                try:
                                    product = Product.objects.create(**product_info)
                                    session.products_created += 1
                                    log_message(session, 'success', f'Created new product: {product_info["name"]}', 
                                              product_url=product_info['link'], product_sku=product_info['sku'])
                                except Exception as create_error:
                                    # Handle race condition - try to get again
                                    try:
                                        product = Product.objects.get(
                                            website=session.website.name,
                                            link=product_info['link']
                                        )
                                        # Update existing product
                                        for key, value in product_info.items():
                                            if key not in ['website']:
                                                setattr(product, key, value)
                                        product.save()
                                        session.products_updated += 1
                                        log_message(session, 'success', f'Updated product (race condition): {product_info["name"]}', 
                                                  product_url=product_info['link'], product_sku=product_info['sku'])
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
                                  product_url=product_info['link'], product_sku=product_info['sku'], 
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
            scrape_shopify_website.apply_async(
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

