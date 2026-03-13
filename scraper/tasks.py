from celery import shared_task
import requests
import time
from .models import *
import random
import traceback
from django.utils import timezone
from celery.exceptions import SoftTimeLimitExceeded
import json
from .scraper_scripts.load_xml_data import (load_craftsandmore_product_urls,load_ozvehadar_product_urls,
                                            load_shaijudaica_product_urls,load_ritelite_product_urls,
                                            load_jewisheducationaltoys_sitemap_product_urls,
                                            load_meiros_sitemap_product_urls, load_legacyjudaica_sitemap_product_urls,
                                            load_simchonim_sitemap_product_urls, load_mefoarjudaica_product_urls,
                                            load_kaftorjudaica_product_urls, get_zionjudaica_urls)
from bs4 import BeautifulSoup
import re

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


# ==================== PRODUCT SYNC TASKS ====================

@shared_task(bind=True, soft_time_limit=1800, time_limit=1860)
def import_website_products_task(self, import_log_id, file_path, vendor_website=None):
    """
    Import products from website export CSV and update sync status (vendor-specific)
    
    Args:
        import_log_id: WebsiteImportLog ID
        file_path: Path to the CSV file
        vendor_website: Filter by specific vendor/website name
    """
    from django.utils import timezone
    from .models import WebsiteImportLog, Product, VendorConfiguration, ProductSyncStatus
    from .sync_utils import CSVParser, SKUMatcher
    
    try:
        # Get import log
        import_log = WebsiteImportLog.objects.get(id=import_log_id)
        import_log.status = 'processing'
        import_log.celery_task_id = self.request.id
        import_log.save()
        
        # Parse CSV file
        try:
            website_products = CSVParser.parse_website_export(file_path)
        except Exception as parse_error:
            import_log.status = 'failed'
            import_log.error_message = f"CSV parsing error: {str(parse_error)}"
            import_log.save()
            return {'status': 'failed', 'message': str(parse_error)}
        
        # Update total rows
        import_log.total_rows = len(website_products)
        import_log.save()
        
        if not website_products:
            import_log.status = 'failed'
            import_log.error_message = "No products found in CSV"
            import_log.save()
            return {'status': 'failed', 'message': 'No products found in CSV'}
        
        matched_count = 0
        processed_count = 0
        skipped_count = 0
        website_skus = set()
        
        # Process each row from CSV
        for idx, csv_row in enumerate(website_products):
            try:
                website_sku = csv_row['sku']
                website_product_id = csv_row['id']
                
                if not website_sku:
                    skipped_count += 1
                    processed_count += 1
                    continue
                
                # Track website SKUs
                website_skus.add(website_sku)
                
                # Match product in database (vendor-specific)
                product = SKUMatcher.match_product_by_sku(website_sku, website_product_id, vendor_website)
                
                if product:
                    # Create or update sync status
                    sync_status, created = ProductSyncStatus.objects.get_or_create(
                        product=product,
                        defaults={
                            'on_website': True,
                            'website_sku': website_sku,
                            'website_product_id': website_product_id,
                            'status': 'synced'
                        }
                    )
                    
                    if not created:
                        # Update existing sync status
                        sync_status.mark_on_website(website_sku, website_product_id)
                    
                    matched_count += 1
                else:
                    skipped_count += 1
                
                processed_count += 1
                
                # Update progress every 10 rows
                if processed_count % 10 == 0:
                    progress = int((processed_count / len(website_products)) * 100)
                    import_log.processed_rows = processed_count
                    import_log.matched_products = matched_count
                    import_log.skipped_rows = skipped_count
                    import_log.progress_percentage = progress
                    import_log.save()
                
            except Exception as row_error:
                skipped_count += 1
                processed_count += 1
                continue
        
        # Now find products that are NOT on website (new products)
        # Filter by specific vendor if provided
        if vendor_website:
            vendor_configs = VendorConfiguration.objects.filter(
                website__name__iexact=vendor_website,
                is_active=True
            )
        else:
            vendor_configs = VendorConfiguration.objects.filter(is_active=True)
        
        new_products_count = 0
        
        for vendor_config in vendor_configs:
            website = vendor_config.website
            
            # Get all products for this website
            website_products_qs = Product.objects.filter(website__iexact=website.name)
            
            for product in website_products_qs:
                # Transform SKU to website format
                website_format_sku = vendor_config.apply_sku_transform(product.sku or '')
                
                # Check if this SKU is NOT in the website export
                if website_format_sku not in website_skus:
                    # This product is in our DB but NOT on the website
                    sync_status, created = ProductSyncStatus.objects.get_or_create(
                        product=product,
                        defaults={
                            'on_website': False,
                            'status': 'new',
                            'website_sku': website_format_sku
                        }
                    )
                    
                    if not created and sync_status.on_website:
                        # Product was previously on website but now removed
                        sync_status.on_website = False
                        sync_status.status = 'removed'
                        sync_status.save()
                    
                    if not sync_status.on_website:
                        new_products_count += 1
        
        # Complete import
        import_log.status = 'completed'
        import_log.processed_rows = processed_count
        import_log.matched_products = matched_count
        import_log.new_products_found = new_products_count
        import_log.skipped_rows = skipped_count
        import_log.progress_percentage = 100
        import_log.completed_at = timezone.now()
        import_log.save()
        
        return {
            'status': 'completed',
            'total_rows': len(website_products),
            'matched': matched_count,
            'new_products': new_products_count,
            'skipped': skipped_count
        }
        
    except Exception as e:
        try:
            import_log.status = 'failed'
            import_log.error_message = str(e)
            import_log.completed_at = timezone.now()
            import_log.save()
        except:
            pass
        
        return {'status': 'failed', 'message': str(e)}


@shared_task(bind=True, soft_time_limit=1800, time_limit=1860)
def export_products_to_website_task(self, product_ids, output_filename):
    """
    Export selected products to website upload CSV format
    
    Args:
        product_ids: List of Product IDs to export
        output_filename: Output CSV filename
        
    Returns:
        Dict with status and file path
    """
    from django.conf import settings
    from .models import Product, ProductSyncStatus
    from .sync_utils import CSVParser
    from django.utils import timezone
    import os
    
    try:
        # Get products
        products = Product.objects.filter(id__in=product_ids)
        
        if not products.exists():
            return {'status': 'failed', 'message': 'No products found'}
        
        # Generate output file path
        output_path = os.path.join(settings.BASE_DIR, output_filename)
        
        # Generate CSV
        count = CSVParser.generate_upload_csv(list(products), output_path)
        
        if count == 0:
            return {'status': 'failed', 'message': 'No products could be exported (check vendor configurations)'}
        
        # Update sync status for exported products
        for product in products:
            sync_status, created = ProductSyncStatus.objects.get_or_create(
                product=product,
                defaults={'status': 'new'}
            )
            sync_status.last_export_at = timezone.now()
            sync_status.selected_for_export = False  # Unselect after export
            sync_status.save()
        
        return {
            'status': 'completed',
            'file_path': output_path,
            'products_exported': count,
            'message': f'Successfully exported {count} products to {output_filename}'
        }
        
    except Exception as e:
        return {'status': 'failed', 'message': str(e)}

def scrape_custom_website_common(session_id, website_config, task_instance, resume_from_index=0):
    """
    Common custom scraper function for non-Shopify websites
    
    Args:
        session_id: ID of the scraping session
        website_config: Dictionary containing website-specific configuration
        task_instance: The calling task instance (self)
        resume_from_index: Index to resume from (for resumption)
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
        
        log_message(session, 'info', f'Starting custom HTML scraping session for {website.name}')
        
        try:
            # Use the appropriate scraping function based on website
            if website_config['scraper_type'] == 'meiros':
                result = scrape_meiros_products_common(session, resume_from_index)
            elif website_config['scraper_type'] == 'legacyjudaica':
                result = scrape_legacyjudaica_products_common(session, resume_from_index)
            elif website_config['scraper_type'] == 'simchonim':
                result = scrape_simchonim_products_common(session, resume_from_index)
            elif website_config['scraper_type'] == 'jewisheducationaltoys':
                result = scrape_jewisheducationaltoys_products_common(session, resume_from_index)
            elif website_config['scraper_type'] == 'ritelite':
                result = scrape_ritelite_products_common(session, resume_from_index)
            elif website_config['scraper_type'] == 'shaijudaica':
                result = scrape_shaijudaica_products_common(session, resume_from_index)
            elif website_config['scraper_type'] == 'ozvehadar':
                result = scrape_ozvehadar_products_common(session, resume_from_index)
            elif website_config['scraper_type'] == 'mefoarjudaica':
                result = scrape_mefoarjudaica_products_common(session, resume_from_index)
            elif website_config['scraper_type'] == 'kaftorjudaica':
                result = scrape_kaftorjudaica_products_common(session, resume_from_index)
            elif website_config['scraper_type'] == 'craftsandmore':
                result = scrape_craftsandmore_products_common(session, resume_from_index)
            elif website_config['scraper_type'] == 'zionjudaica':
                result = scrape_zionjudaica_products_common(session, resume_from_index)
            else:
                result = {'status': 'failed', 'message': f'Unknown scraper type: {website_config["scraper_type"]}'}
            
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
            # Use the last processed index for resumption
            if website_config['scraper_type'] == 'meiros':
                scrape_meiros.apply_async(
                    args=[session_id, session.last_processed_index + 1],
                    countdown=30
                )
            elif website_config['scraper_type'] == 'legacyjudaica':
                scrape_legacyjudaica.apply_async(
                    args=[session_id, session.last_processed_index + 1],
                    countdown=30
                )
            
            log_message(session, 'info', f'Auto-resume task scheduled')
            
            return {
                'status': 'auto_resuming', 
                'message': f'Task auto-resuming in 30 seconds from index {session.last_processed_index + 1}',
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

# Custom websites
def extract_jewisheducationaltoys_product_info(soup, product_url, website_name):
    """
    Extract product information from meiros.com product page HTML using BeautifulSoup
    
    Args:
        soup: BeautifulSoup object of the product page
        product_url: URL of the product page
        website_name: Name of the website
        
    Returns:
        dict: Product information dictionary
    """
    try:
        # Extract title
        title_elem = soup.find('font', class_='productnamecolorLARGE colors_productname')
        title = title_elem.get_text(strip=True) if title_elem else ''

        b_tags = soup.find_all('b')
        upc = ''

        for b in b_tags:
            if 'UPC:' in b.get_text():
                # UPC value is likely in the next sibling text
                next_sibling = b.next_sibling
                if next_sibling:
                    upc = str(next_sibling).strip()
                break
        sku = upc
        
        # Extract description
        description = ''
        desc_elem = soup.find('span', id='product_description')
        if desc_elem:
                description = desc_elem.get_text(strip=True)

        availability = soup.find('meta', itemprop='availability')
        in_stock = availability and 'InStock' in availability.get('content', '')

        category = ''
        b_tag = soup.find('td', class_='vCSS_breadcrumb_td').find('b')

        # Find all <a> tags inside <b>
        links = b_tag.find_all('a')

        # Get the last breadcrumb text
        category = links[-1].get_text(strip=True)

        # Extract image link
        image_link = ''
        img_tag = soup.find('img', id='product_photo')
        image_link = img_tag['src']

        # Optional: Add protocol if missing
        if image_link.startswith("//"):
            image_link = "https:" + image_link
        
        # Generate unique product variant ID (using URL + SKU)
        product_variant_id = f"{website_name}_{sku}" if sku else f"{website_name}_{hash(product_url)}"
        
        # Check if product is in stock (assume in stock if price exists)
        # in_stock = bool(price)
        
        product_info = {
            'product_variant_id': product_variant_id,
            'name': title,
            'sku': sku,
            'price': 'Login Required',
            'vendor': '',  # meiros.com doesn't seem to have vendor info
            'category': category,  # We could extract this from URL or breadcrumbs if needed
            'description': description,
            'in_stock': in_stock,
            'link': product_url,
            'image_link': image_link,
            'website': website_name
        }
        
        return product_info
        
    except Exception as e:
        print(f"Error extracting meiros product info: {e}")
        return None

def scrape_jewisheducationaltoys_products_common(session, resume_from_index=0):
    """
    Custom scraping function for jewisheducationaltoys.com using BeautifulSoup
    
    Args:
        session: ScrapingSession object
        resume_from_index: Index to resume from (for resumption)
        
    Returns:
        dict: Scraping results
    """
    log_message(session, 'info', f'Starting custom HTML scraping for {session.website.name}')
    
    try:
        # Get product URLs from sitemap
        product_urls = load_jewisheducationaltoys_sitemap_product_urls()
        
        if not product_urls:
            log_message(session, 'error', 'No product URLs found in sitemap')
            return {
                'status': 'failed',
                'message': 'No product URLs found in sitemap'
            }
        
        log_message(session, 'info', f'Found {len(product_urls)} product URLs from sitemap')
        
        # Update total products found
        session.total_products_found = len(product_urls)
        session.save()
        
        # Process products starting from resume index
        for idx, product_url in enumerate(product_urls[resume_from_index:], start=resume_from_index):
            try:
                # Random delay between requests (5-15 seconds)
                if idx > resume_from_index:  # Don't delay on first/resumed request
                    delay = random.randint(5, 15)
                    log_message(session, 'info', f'Waiting {delay} seconds before next request...')
                    time.sleep(delay)
                
                log_message(session, 'info', f'Processing product {idx + 1}/{len(product_urls)}: {product_url}')
                
                # Make request to product page
                response = requests.get(product_url, headers=HEADERS, timeout=30)
                response.raise_for_status()
                
                # Parse HTML with BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract product information
                product_info = extract_jewisheducationaltoys_product_info(soup, product_url, session.website.name)
                
                if not product_info:
                    session.products_failed += 1
                    log_message(session, 'warning', f'Failed to extract product info for: {product_url}')
                    continue
                
                # Save or update product in database
                try:
                    # Try to get existing product by variant ID
                    try:
                        product = Product.objects.get(product_variant_id=product_info['product_variant_id'])
                        # Update existing product
                        for key, value in product_info.items():
                            if key not in ['website']:
                                setattr(product, key, value)
                        product.save()
                        session.products_updated += 1
                        log_message(session, 'success', f'Updated product: {product_info["name"]}', 
                                product_url=product_url, product_sku=product_info['sku'])
                    except Product.DoesNotExist:
                        # Create new product
                        try:
                            product = Product.objects.create(**product_info)
                            session.products_created += 1
                            log_message(session, 'success', f'Created new product: {product_info["name"]}', 
                                    product_url=product_url, product_sku=product_info['sku'])
                        except Exception as create_error:
                            # Handle race condition - try to get again
                            try:
                                product = Product.objects.get(product_variant_id=product_info['product_variant_id'])
                                # Update existing product
                                for key, value in product_info.items():
                                    if key not in ['website']:
                                        setattr(product, key, value)
                                product.save()
                                session.products_updated += 1
                                log_message(session, 'success', f'Updated product (race condition): {product_info["name"]}', 
                                        product_url=product_url, product_sku=product_info['sku'])
                            except:
                                raise create_error
                    
                    session.products_scraped += 1
                    
                    # Update session progress
                    session.last_processed_index = idx
                    session.last_processed_url = product_url
                    session.save()
                    
                except Exception as db_error:
                    session.products_failed += 1
                    log_message(session, 'error', f'Database error for product: {str(db_error)}', 
                            product_url=product_url, product_sku=product_info['sku'], 
                            exception_details=traceback.format_exc())
                    continue
                
            except requests.exceptions.RequestException as req_error:
                session.products_failed += 1
                log_message(session, 'error', f'Request error for product {product_url}: {str(req_error)}', 
                          product_url=product_url, exception_details=traceback.format_exc())
                continue
                
            except Exception as product_error:
                session.products_failed += 1
                log_message(session, 'error', f'Error processing product {product_url}: {str(product_error)}', 
                          product_url=product_url, exception_details=traceback.format_exc())
                continue
        
        return {
            'status': 'completed',
            'total_found': session.total_products_found,
            'scraped': session.products_scraped,
            'created': session.products_created,
            'updated': session.products_updated,
            'failed': session.products_failed
        }
        
    except Exception as e:
        log_message(session, 'error', f'Critical error in meiros scraping: {str(e)}', 
                  exception_details=traceback.format_exc())
        return {
            'status': 'failed',
            'message': str(e)
        }
    
def extract_ritelite_product_info(soup, product_url, website_name):
    """
    Extract product information from ritelite.com product page HTML using BeautifulSoup
    
    Args:
        soup: BeautifulSoup object of the product page
        product_url: URL of the product page
        website_name: Name of the website
        
    Returns:
        dict: Product information dictionary
    """
    try:
        # Extract title
        title_elem = soup.find("h3", class_="mainhead myriad-pro-normal")
        title = title_elem.get_text(strip=True) if title_elem else ''
        
        # Extract price
        price = ''
        first_price_span = soup.find("span", class_="myriad-pro-bold")
        if first_price_span:
            price_text = first_price_span.get_text(strip=True).replace("MSRP", "").strip()
            price = re.sub(r'[^\d\.]', '', price_text)
            
            
        
        # Extract SKU
        sku_elem = soup.find("h4", class_="mainhead myriad-pro-bold uppercase text-center")
        sku = sku_elem.get_text(strip=True) if sku_elem else ''
        sku = re.sub(r'\bitem\b', '', sku, flags=re.IGNORECASE).strip()
        
        # Extract description
        description = ''
        desc_elem = soup.find("div", class_="col-xs-12 col-lg-12 col-md-12 nopadding myriad margin-top-10")
        if desc_elem:
                description = desc_elem.get_text(strip=True)
        
        # Extract image link
        image_link = ''
        img_tag = soup.find("img", class_="zoom_02")
        if img_tag:
            base_url = "https://ritelite.com"
            image_link = base_url + img_tag.get("src")

        
        # Generate unique product variant ID (using URL + SKU)
        product_variant_id = f"{website_name}_{sku}" if sku else f"{website_name}_{hash(product_url)}"
        category = product_url.split("Category/")[1].split("/")[0]
        # Check if product is in stock (assume in stock if price exists)
        in_stock = bool(price)
        
        product_info = {
            'product_variant_id': product_variant_id,
            'name': title,
            'sku': sku,
            'price': price,
            'vendor': '',  # meiros.com doesn't seem to have vendor info
            'category': category,  # We could extract this from URL or breadcrumbs if needed
            'description': description,
            'in_stock': in_stock,
            'link': product_url,
            'image_link': image_link,
            'website': website_name
        }
        
        return product_info
        
    except Exception as e:
        print(f"Error extracting meiros product info: {e}")
        return None

def scrape_ritelite_products_common(session, resume_from_index=0):
    """
    Custom scraping function for ritelite.com using BeautifulSoup
    
    Args:
        session: ScrapingSession object
        resume_from_index: Index to resume from (for resumption)
        
    Returns:
        dict: Scraping results
    """
    log_message(session, 'info', f'Starting custom HTML scraping for {session.website.name}')
    
    try:
        # Get product URLs from sitemap
        product_urls = load_ritelite_product_urls()
        
        if not product_urls:
            log_message(session, 'error', 'No product URLs found in sitemap')
            return {
                'status': 'failed',
                'message': 'No product URLs found in sitemap'
            }
        
        log_message(session, 'info', f'Found {len(product_urls)} product URLs from sitemap')
        
        # Update total products found
        session.total_products_found = len(product_urls)
        session.save()
        
        # Process products starting from resume index
        for idx, product_url in enumerate(product_urls[resume_from_index:], start=resume_from_index):
            try:
                # Random delay between requests (5-15 seconds)
                if idx > resume_from_index:  # Don't delay on first/resumed request
                    delay = random.randint(5, 15)
                    log_message(session, 'info', f'Waiting {delay} seconds before next request...')
                    time.sleep(delay)
                
                log_message(session, 'info', f'Processing product {idx + 1}/{len(product_urls)}: {product_url}')
                
                # Make request to product page
                response = requests.get(product_url, headers=HEADERS, timeout=30)
                response.raise_for_status()
                
                # Parse HTML with BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract product information
                product_info = extract_ritelite_product_info(soup, product_url, session.website.name)
                
                if not product_info:
                    session.products_failed += 1
                    log_message(session, 'warning', f'Failed to extract product info for: {product_url}')
                    continue
                
                # Save or update product in database
                try:
                    # Try to get existing product by variant ID
                    try:
                        product = Product.objects.get(product_variant_id=product_info['product_variant_id'])
                        # Update existing product
                        for key, value in product_info.items():
                            if key not in ['website']:
                                setattr(product, key, value)
                        product.save()
                        session.products_updated += 1
                        log_message(session, 'success', f'Updated product: {product_info["name"]}', 
                                product_url=product_url, product_sku=product_info['sku'])
                    except Product.DoesNotExist:
                        # Create new product
                        try:
                            product = Product.objects.create(**product_info)
                            session.products_created += 1
                            log_message(session, 'success', f'Created new product: {product_info["name"]}', 
                                    product_url=product_url, product_sku=product_info['sku'])
                        except Exception as create_error:
                            # Handle race condition - try to get again
                            try:
                                product = Product.objects.get(product_variant_id=product_info['product_variant_id'])
                                # Update existing product
                                for key, value in product_info.items():
                                    if key not in ['website']:
                                        setattr(product, key, value)
                                product.save()
                                session.products_updated += 1
                                log_message(session, 'success', f'Updated product (race condition): {product_info["name"]}', 
                                        product_url=product_url, product_sku=product_info['sku'])
                            except:
                                raise create_error
                    
                    session.products_scraped += 1
                    
                    # Update session progress
                    session.last_processed_index = idx
                    session.last_processed_url = product_url
                    session.save()
                    
                except Exception as db_error:
                    session.products_failed += 1
                    log_message(session, 'error', f'Database error for product: {str(db_error)}', 
                            product_url=product_url, product_sku=product_info['sku'], 
                            exception_details=traceback.format_exc())
                    continue
                
            except requests.exceptions.RequestException as req_error:
                session.products_failed += 1
                log_message(session, 'error', f'Request error for product {product_url}: {str(req_error)}', 
                          product_url=product_url, exception_details=traceback.format_exc())
                continue
                
            except Exception as product_error:
                session.products_failed += 1
                log_message(session, 'error', f'Error processing product {product_url}: {str(product_error)}', 
                          product_url=product_url, exception_details=traceback.format_exc())
                continue
        
        return {
            'status': 'completed',
            'total_found': session.total_products_found,
            'scraped': session.products_scraped,
            'created': session.products_created,
            'updated': session.products_updated,
            'failed': session.products_failed
        }
        
    except Exception as e:
        log_message(session, 'error', f'Critical error in meiros scraping: {str(e)}', 
                  exception_details=traceback.format_exc())
        return {
            'status': 'failed',
            'message': str(e)
        }

def extract_shaijudaica_product_info(soup, product_url, website_name):
    """
    Extract product information from shaijudaica.co.il product page HTML using BeautifulSoup
    
    Args:
        soup: BeautifulSoup object of the product page
        product_url: URL of the product page
        website_name: Name of the website
        
    Returns:
        dict: Product information dictionary
    """
    try:
        # Extract title
        title_elem = soup.select_one("#item_current_title")
        title = title_elem.get_text(strip=True) if title_elem else ''
        
        # Extract price
        price = ''
        price_elem = soup.find("span", class_="price_value")
        price = price_elem.get_text(strip=True) if price_elem else ''
            
            
        
        # Extract SKU
        sku_elem = soup.select_one(".code_item")
        sku = sku_elem.get_text(strip=True) if sku_elem else ''
        
        # Extract description
        description = ''
        desc_elem = soup.select_one("#item_current_sub_title")
        if desc_elem:
                description = desc_elem.get_text(strip=True)
        
        # Extract image link
        image_link = ''
        img_tag = soup.select_one("#item_show_carousel img")
        if img_tag:
            image_link = img_tag.get("src")

        
        # Generate unique product variant ID (using URL + SKU)
        product_variant_id = f"{website_name}_{sku}" if sku else f"{website_name}_{hash(product_url)}"
        category = ''
        li_tags = soup.select("#bread_crumbs li")

        if len(li_tags) >= 2:
            category = li_tags[-2].get_text(strip=True)
        # Check if product is in stock (assume in stock if price exists)
        in_stock = bool(price)
        
        product_info = {
            'product_variant_id': product_variant_id,
            'name': title,
            'sku': sku,
            'price': price,
            'vendor': '',  # meiros.com doesn't seem to have vendor info
            'category': category,  # We could extract this from URL or breadcrumbs if needed
            'description': description,
            'in_stock': in_stock,
            'link': product_url,
            'image_link': image_link,
            'website': website_name
        }
        
        return product_info
        
    except Exception as e:
        print(f"Error extracting meiros product info: {e}")
        return None

def scrape_shaijudaica_products_common(session, resume_from_index=0):
    """
    Custom scraping function for shaijudaica.co.il using BeautifulSoup
    
    Args:
        session: ScrapingSession object
        resume_from_index: Index to resume from (for resumption)
        
    Returns:
        dict: Scraping results
    """
    log_message(session, 'info', f'Starting custom HTML scraping for {session.website.name}')
    
    try:
        # Get product URLs from sitemap
        product_urls = load_shaijudaica_product_urls()
        
        if not product_urls:
            log_message(session, 'error', 'No product URLs found in sitemap')
            return {
                'status': 'failed',
                'message': 'No product URLs found in sitemap'
            }
        
        log_message(session, 'info', f'Found {len(product_urls)} product URLs from sitemap')
        
        # Update total products found
        session.total_products_found = len(product_urls)
        session.save()
        
        # Process products starting from resume index
        for idx, product_url in enumerate(product_urls[resume_from_index:], start=resume_from_index):
            try:
                # Random delay between requests (5-15 seconds)
                if idx > resume_from_index:  # Don't delay on first/resumed request
                    delay = random.randint(5, 15)
                    log_message(session, 'info', f'Waiting {delay} seconds before next request...')
                    time.sleep(delay)
                
                log_message(session, 'info', f'Processing product {idx + 1}/{len(product_urls)}: {product_url}')
                
                # Make request to product page
                response = requests.get(product_url, headers=HEADERS, timeout=30)
                response.raise_for_status()
                
                # Parse HTML with BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract product information
                product_info = extract_shaijudaica_product_info(soup, product_url, session.website.name)
                
                if not product_info:
                    session.products_failed += 1
                    log_message(session, 'warning', f'Failed to extract product info for: {product_url}')
                    continue
                
                # Save or update product in database
                try:
                    # Try to get existing product by variant ID
                    try:
                        product = Product.objects.get(product_variant_id=product_info['product_variant_id'])
                        # Update existing product
                        for key, value in product_info.items():
                            if key not in ['website']:
                                setattr(product, key, value)
                        product.save()
                        session.products_updated += 1
                        log_message(session, 'success', f'Updated product: {product_info["name"]}', 
                                product_url=product_url, product_sku=product_info['sku'])
                    except Product.DoesNotExist:
                        # Create new product
                        try:
                            product = Product.objects.create(**product_info)
                            session.products_created += 1
                            log_message(session, 'success', f'Created new product: {product_info["name"]}', 
                                    product_url=product_url, product_sku=product_info['sku'])
                        except Exception as create_error:
                            # Handle race condition - try to get again
                            try:
                                product = Product.objects.get(product_variant_id=product_info['product_variant_id'])
                                # Update existing product
                                for key, value in product_info.items():
                                    if key not in ['website']:
                                        setattr(product, key, value)
                                product.save()
                                session.products_updated += 1
                                log_message(session, 'success', f'Updated product (race condition): {product_info["name"]}', 
                                        product_url=product_url, product_sku=product_info['sku'])
                            except:
                                raise create_error
                    
                    session.products_scraped += 1
                    
                    # Update session progress
                    session.last_processed_index = idx
                    session.last_processed_url = product_url
                    session.save()
                    
                except Exception as db_error:
                    session.products_failed += 1
                    log_message(session, 'error', f'Database error for product: {str(db_error)}', 
                            product_url=product_url, product_sku=product_info['sku'], 
                            exception_details=traceback.format_exc())
                    continue
                
            except requests.exceptions.RequestException as req_error:
                session.products_failed += 1
                log_message(session, 'error', f'Request error for product {product_url}: {str(req_error)}', 
                          product_url=product_url, exception_details=traceback.format_exc())
                continue
                
            except Exception as product_error:
                session.products_failed += 1
                log_message(session, 'error', f'Error processing product {product_url}: {str(product_error)}', 
                          product_url=product_url, exception_details=traceback.format_exc())
                continue
        
        return {
            'status': 'completed',
            'total_found': session.total_products_found,
            'scraped': session.products_scraped,
            'created': session.products_created,
            'updated': session.products_updated,
            'failed': session.products_failed
        }
        
    except Exception as e:
        log_message(session, 'error', f'Critical error in meiros scraping: {str(e)}', 
                  exception_details=traceback.format_exc())
        return {
            'status': 'failed',
            'message': str(e)
        }

def extract_meiros_product_info(soup, product_url, website_name):
    """
    Extract product information from meiros.com product page HTML using BeautifulSoup
    
    Args:
        soup: BeautifulSoup object of the product page
        product_url: URL of the product page
        website_name: Name of the website
        
    Returns:
        dict: Product information dictionary
    """
    try:
        # Extract title
        title_elem = soup.find('h2', class_='pd-top__main-right__title')
        title = title_elem.get_text(strip=True) if title_elem else ''
        
        # Extract price
        price_elem = soup.find('span', class_='pd-top__main-right__price')
        price = ''
        if price_elem:
            # Remove currency symbol and clean price
            price_text = price_elem.get_text(strip=True)
            price = re.sub(r'[^\d\.]', '', price_text)
        
        # Extract SKU
        sku_elem = soup.find('span', class_='pd-top__main-right__bpinner-label sku')
        sku = sku_elem.get_text(strip=True) if sku_elem else ''
        
        # Extract description
        description = ''
        desc_elem = soup.find('div', class_='description-inner__text')
        if desc_elem:
            desc_text_elem = desc_elem.find('p', class_='description-inner__text-text')
            if desc_text_elem:
                description = desc_text_elem.get_text(strip=True)
        
        # Extract image link
        image_link = ''
        img_elem = soup.find('div', class_='slick-track')
        if img_elem:
            # Find the image link from the anchor tag
            link_elem = img_elem.find('a', class_='pd-top__main-slider-img')
            if link_elem and link_elem.get('href'):
                image_link = link_elem.get('href')
            elif img_elem.find('img'):
                # Fallback to img src if no href found
                img_tag = img_elem.find('img')
                if img_tag and img_tag.get('src'):
                    image_link = img_tag.get('src')
        
        # Generate unique product variant ID (using URL + SKU)
        product_variant_id = f"{website_name}_{sku}" if sku else f"{website_name}_{hash(product_url)}"
        
        # Check if product is in stock (assume in stock if price exists)
        in_stock = bool(price)
        
        product_info = {
            'product_variant_id': product_variant_id,
            'name': title,
            'sku': sku,
            'price': price,
            'vendor': '',  # meiros.com doesn't seem to have vendor info
            'category': '',  # We could extract this from URL or breadcrumbs if needed
            'description': description,
            'in_stock': in_stock,
            'link': product_url,
            'image_link': image_link,
            'website': website_name
        }
        
        return product_info
        
    except Exception as e:
        print(f"Error extracting meiros product info: {e}")
        return None

def scrape_meiros_products_common(session, resume_from_index=0):
    """
    Custom scraping function for meiros.com using BeautifulSoup
    
    Args:
        session: ScrapingSession object
        resume_from_index: Index to resume from (for resumption)
        
    Returns:
        dict: Scraping results
    """
    log_message(session, 'info', f'Starting custom HTML scraping for {session.website.name}')
    
    try:
        # Get product URLs from sitemap
        product_urls = load_meiros_sitemap_product_urls()
        
        if not product_urls:
            log_message(session, 'error', 'No product URLs found in sitemap')
            return {
                'status': 'failed',
                'message': 'No product URLs found in sitemap'
            }
        
        log_message(session, 'info', f'Found {len(product_urls)} product URLs from sitemap')
        
        # Update total products found
        session.total_products_found = len(product_urls)
        session.save()
        
        # Process products starting from resume index
        for idx, product_url in enumerate(product_urls[resume_from_index:], start=resume_from_index):
            try:
                # Random delay between requests (5-15 seconds)
                if idx > resume_from_index:  # Don't delay on first/resumed request
                    delay = random.randint(5, 15)
                    log_message(session, 'info', f'Waiting {delay} seconds before next request...')
                    time.sleep(delay)
                
                log_message(session, 'info', f'Processing product {idx + 1}/{len(product_urls)}: {product_url}')
                
                # Make request to product page
                response = requests.get(product_url, headers=HEADERS, timeout=30)
                response.raise_for_status()
                
                # Parse HTML with BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract product information
                product_info = extract_meiros_product_info(soup, product_url, session.website.name)
                
                if not product_info:
                    session.products_failed += 1
                    log_message(session, 'warning', f'Failed to extract product info for: {product_url}')
                    continue
                
                # Save or update product in database
                try:
                    # Try to get existing product by variant ID
                    try:
                        product = Product.objects.get(product_variant_id=product_info['product_variant_id'])
                        # Update existing product
                        for key, value in product_info.items():
                            if key not in ['website']:
                                setattr(product, key, value)
                        product.save()
                        session.products_updated += 1
                        log_message(session, 'success', f'Updated product: {product_info["name"]}', 
                                product_url=product_url, product_sku=product_info['sku'])
                    except Product.DoesNotExist:
                        # Create new product
                        try:
                            product = Product.objects.create(**product_info)
                            session.products_created += 1
                            log_message(session, 'success', f'Created new product: {product_info["name"]}', 
                                    product_url=product_url, product_sku=product_info['sku'])
                        except Exception as create_error:
                            # Handle race condition - try to get again
                            try:
                                product = Product.objects.get(product_variant_id=product_info['product_variant_id'])
                                # Update existing product
                                for key, value in product_info.items():
                                    if key not in ['website']:
                                        setattr(product, key, value)
                                product.save()
                                session.products_updated += 1
                                log_message(session, 'success', f'Updated product (race condition): {product_info["name"]}', 
                                        product_url=product_url, product_sku=product_info['sku'])
                            except:
                                raise create_error
                    
                    session.products_scraped += 1
                    
                    # Update session progress
                    session.last_processed_index = idx
                    session.last_processed_url = product_url
                    session.save()
                    
                except Exception as db_error:
                    session.products_failed += 1
                    log_message(session, 'error', f'Database error for product: {str(db_error)}', 
                            product_url=product_url, product_sku=product_info['sku'], 
                            exception_details=traceback.format_exc())
                    continue
                
            except requests.exceptions.RequestException as req_error:
                session.products_failed += 1
                log_message(session, 'error', f'Request error for product {product_url}: {str(req_error)}', 
                          product_url=product_url, exception_details=traceback.format_exc())
                continue
                
            except Exception as product_error:
                session.products_failed += 1
                log_message(session, 'error', f'Error processing product {product_url}: {str(product_error)}', 
                          product_url=product_url, exception_details=traceback.format_exc())
                continue
        
        return {
            'status': 'completed',
            'total_found': session.total_products_found,
            'scraped': session.products_scraped,
            'created': session.products_created,
            'updated': session.products_updated,
            'failed': session.products_failed
        }
        
    except Exception as e:
        log_message(session, 'error', f'Critical error in meiros scraping: {str(e)}', 
                  exception_details=traceback.format_exc())
        return {
            'status': 'failed',
            'message': str(e)
        }

def extract_legacyjudaica_product_info(soup, product_url, website_name):
    """
    Extract product information from legacyjudaica.com product page HTML using BeautifulSoup
    
    Args:
        soup: BeautifulSoup object of the product page
        product_url: URL of the product page
        website_name: Name of the website
        
    Returns:
        dict: Product information dictionary
    """
    try:
        # Extract title
        title_elem = soup.find('div', class_='product-name')
        title = ''
        if title_elem:
            h1_elem = title_elem.find('h1')
            if h1_elem:
                title = h1_elem.get_text(strip=True)
        
        # Extract price
        price_elem = soup.find('div', class_='product-price')
        price = ''
        if price_elem:
            price_span = price_elem.find('span', class_=lambda x: x and 'price-value' in x)
            if price_span:
                price_text = price_span.get_text(strip=True)
                price = re.sub(r'[^\d\.]', '', price_text)
        
        # Extract SKU
        sku_elem = soup.find('div', class_='sku')
        sku = ''
        if sku_elem:
            value_span = sku_elem.find('span', class_='value')
            if value_span:
                sku = value_span.get_text(strip=True)
        
        # Extract vendor/manufacturer
        vendor = ''
        manufacturer_elem = soup.find('div', class_='manufacturers')
        if manufacturer_elem:
            value_span = manufacturer_elem.find('span', class_='value')
            if value_span:
                vendor_link = value_span.find('a')
                if vendor_link:
                    vendor = vendor_link.get_text(strip=True)
        
        # Extract description
        description = ''
        desc_elem = soup.find('div', class_='short-description')
        if desc_elem:
            description = desc_elem.get_text(strip=True)
        
        # Extract image link - find first product image
        image_link = ''
        # Try to find main product image
        a_tag = soup.find('a', class_='picture-link')

        # Get the data-full-image-url attribute
        image_link = a_tag.get('data-full-image-url')
        
        # Generate unique product variant ID (using URL + SKU)
        product_variant_id = f"{website_name}_{sku}" if sku else f"{website_name}_{hash(product_url)}"
        
        # Check if product is in stock (assume in stock if price exists)
        in_stock = bool(price)
        
        product_info = {
            'product_variant_id': product_variant_id,
            'name': title,
            'sku': sku,
            'price': price,
            'vendor': vendor,
            'category': vendor,  # Use vendor as category since there's no separate category
            'description': description,
            'in_stock': in_stock,
            'link': product_url,
            'image_link': image_link,
            'website': website_name
        }
        
        return product_info
        
    except Exception as e:
        print(f"Error extracting legacyjudaica product info: {e}")
        return None

def scrape_legacyjudaica_products_common(session, resume_from_index=0):
    """
    Custom scraping function for legacyjudaica.com using BeautifulSoup
    
    Args:
        session: ScrapingSession object
        resume_from_index: Index to resume from (for resumption)
        
    Returns:
        dict: Scraping results
    """
    log_message(session, 'info', f'Starting custom HTML scraping for {session.website.name}')
    
    try:
        # Get product URLs from sitemap
        product_urls = load_legacyjudaica_sitemap_product_urls()
        
        if not product_urls:
            log_message(session, 'error', 'No product URLs found in sitemap')
            return {
                'status': 'failed',
                'message': 'No product URLs found in sitemap'
            }
        
        log_message(session, 'info', f'Found {len(product_urls)} product URLs from sitemap')
        
        # Update total products found
        session.total_products_found = len(product_urls)
        session.save()
        
        # Process products starting from resume index
        for idx, product_url in enumerate(product_urls[resume_from_index:], start=resume_from_index):
            try:
                # Random delay between requests (5-15 seconds)
                if idx > resume_from_index:  # Don't delay on first/resumed request
                    delay = random.randint(5, 15)
                    log_message(session, 'info', f'Waiting {delay} seconds before next request...')
                    time.sleep(delay)
                
                log_message(session, 'info', f'Processing product {idx + 1}/{len(product_urls)}: {product_url}')
                
                # Make request to product page
                response = requests.get(product_url, headers=HEADERS, timeout=30)
                response.raise_for_status()
                
                # Parse HTML with BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract product information
                product_info = extract_legacyjudaica_product_info(soup, product_url, session.website.name)
                
                if not product_info:
                    session.products_failed += 1
                    log_message(session, 'warning', f'Failed to extract product info for: {product_url}')
                    continue
                
                # Save or update product in database
                try:
                    # Try to get existing product by variant ID
                    try:
                        product = Product.objects.get(product_variant_id=product_info['product_variant_id'])
                        # Update existing product
                        for key, value in product_info.items():
                            if key not in ['website']:
                                setattr(product, key, value)
                        product.save()
                        session.products_updated += 1
                        log_message(session, 'success', f'Updated product: {product_info["name"]}', 
                                product_url=product_url, product_sku=product_info['sku'])
                    except Product.DoesNotExist:
                        # Create new product
                        try:
                            product = Product.objects.create(**product_info)
                            session.products_created += 1
                            log_message(session, 'success', f'Created new product: {product_info["name"]}', 
                                    product_url=product_url, product_sku=product_info['sku'])
                        except Exception as create_error:
                            # Handle race condition - try to get again
                            try:
                                product = Product.objects.get(product_variant_id=product_info['product_variant_id'])
                                # Update existing product
                                for key, value in product_info.items():
                                    if key not in ['website']:
                                        setattr(product, key, value)
                                product.save()
                                session.products_updated += 1
                                log_message(session, 'success', f'Updated product (race condition): {product_info["name"]}', 
                                        product_url=product_url, product_sku=product_info['sku'])
                            except:
                                raise create_error
                    
                    session.products_scraped += 1
                    
                    # Update session progress
                    session.last_processed_index = idx
                    session.last_processed_url = product_url
                    session.save()
                    
                except Exception as db_error:
                    session.products_failed += 1
                    log_message(session, 'error', f'Database error for product: {str(db_error)}', 
                            product_url=product_url, product_sku=product_info['sku'], 
                            exception_details=traceback.format_exc())
                    continue
                
            except requests.exceptions.RequestException as req_error:
                session.products_failed += 1
                log_message(session, 'error', f'Request error for product {product_url}: {str(req_error)}', 
                          product_url=product_url, exception_details=traceback.format_exc())
                continue
                
            except Exception as product_error:
                session.products_failed += 1
                log_message(session, 'error', f'Error processing product {product_url}: {str(product_error)}', 
                          product_url=product_url, exception_details=traceback.format_exc())
                continue
        
        return {
            'status': 'completed',
            'total_found': session.total_products_found,
            'scraped': session.products_scraped,
            'created': session.products_created,
            'updated': session.products_updated,
            'failed': session.products_failed
        }
        
    except Exception as e:
        log_message(session, 'error', f'Critical error in legacyjudaica scraping: {str(e)}', 
                  exception_details=traceback.format_exc())
        return {
            'status': 'failed',
            'message': str(e)
        }

def extract_simchonim_product_info(soup, product_url, website_name):
    """
    Extract product information from simchonim.com product page HTML using BeautifulSoup
    
    Args:
        soup: BeautifulSoup object of the product page
        product_url: URL of the product page
        website_name: Name of the website
        
    Returns:
        dict: Product information dictionary
    """
    try:
        title_tag = soup.find('h1', class_='product_title entry-title')
        title = title_tag.get_text(strip=True) if title_tag else None

        # Description
        desc_div = soup.find('div', class_='woocommerce-product-details__short-description')
        description = desc_div.get_text(separator=' ', strip=True) if desc_div else None

        # Price
        price_span = soup.find('span', class_='woocommerce-Price-amount')
        price = price_span.get_text(strip=True) if price_span else None

        # SKU
        sku_span = soup.find('span', class_='sku')
        sku = sku_span.get_text(strip=True) if sku_span else None

        # Image URL
        image_div = soup.find('div', class_='woocommerce-product-gallery__image')
        image_url = None
        if image_div:
            img_tag = image_div.find('img')
            if img_tag and img_tag.get('src'):
                image_url = img_tag['src']

        
        vendor = ''
        
        
        # Generate unique product variant ID (using URL + SKU)
        product_variant_id = f"{website_name}_{hash(product_url)}"
        
        # Check if product is in stock (assume in stock if price exists)
        in_stock = bool(price)
        
        product_info = {
            'product_variant_id': product_variant_id,
            'name': title,
            'sku': sku,
            'price': price,
            'vendor': vendor,
            'category': vendor,  # Use vendor as category since there's no separate category
            'description': description,
            'in_stock': in_stock,
            'link': product_url,
            'image_link': image_url,
            'website': website_name
        }
        
        return product_info
        
    except Exception as e:
        print(f"Error extracting legacyjudaica product info: {e}")
        return None

def scrape_simchonim_products_common(session, resume_from_index=0):
    """
    Custom scraping function for simchonim.com using BeautifulSoup
    
    Args:
        session: ScrapingSession object
        resume_from_index: Index to resume from (for resumption)
        
    Returns:
        dict: Scraping results
    """
    log_message(session, 'info', f'Starting custom HTML scraping for {session.website.name}')
    
    try:
        # Get product URLs from sitemap
        product_urls = load_simchonim_sitemap_product_urls()
        
        if not product_urls:
            log_message(session, 'error', 'No product URLs found in sitemap')
            return {
                'status': 'failed',
                'message': 'No product URLs found in sitemap'
            }
        
        log_message(session, 'info', f'Found {len(product_urls)} product URLs from sitemap')
        
        # Update total products found
        session.total_products_found = len(product_urls)
        session.save()
        
        # Process products starting from resume index
        for idx, product_url in enumerate(product_urls[resume_from_index:], start=resume_from_index):
            try:
                # Random delay between requests (5-15 seconds)
                if idx > resume_from_index:  # Don't delay on first/resumed request
                    delay = random.randint(5, 15)
                    log_message(session, 'info', f'Waiting {delay} seconds before next request...')
                    time.sleep(delay)
                
                log_message(session, 'info', f'Processing product {idx + 1}/{len(product_urls)}: {product_url}')
                
                # Make request to product page
                response = requests.get(product_url, headers=HEADERS, timeout=30)
                response.raise_for_status()
                
                # Parse HTML with BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract product information
                product_info = extract_simchonim_product_info(soup, product_url, session.website.name)
                
                if not product_info:
                    session.products_failed += 1
                    log_message(session, 'warning', f'Failed to extract product info for: {product_url}')
                    continue
                
                # Save or update product in database
                try:
                    # Try to get existing product by variant ID
                    try:
                        product = Product.objects.get(product_variant_id=product_info['product_variant_id'])
                        # Update existing product
                        for key, value in product_info.items():
                            if key not in ['website']:
                                setattr(product, key, value)
                        product.save()
                        session.products_updated += 1
                        log_message(session, 'success', f'Updated product: {product_info["name"]}', 
                                product_url=product_url, product_sku=product_info['sku'])
                    except Product.DoesNotExist:
                        # Create new product
                        try:
                            product = Product.objects.create(**product_info)
                            session.products_created += 1
                            log_message(session, 'success', f'Created new product: {product_info["name"]}', 
                                    product_url=product_url, product_sku=product_info['sku'])
                        except Exception as create_error:
                            # Handle race condition - try to get again
                            try:
                                product = Product.objects.get(product_variant_id=product_info['product_variant_id'])
                                # Update existing product
                                for key, value in product_info.items():
                                    if key not in ['website']:
                                        setattr(product, key, value)
                                product.save()
                                session.products_updated += 1
                                log_message(session, 'success', f'Updated product (race condition): {product_info["name"]}', 
                                        product_url=product_url, product_sku=product_info['sku'])
                            except:
                                raise create_error
                    
                    session.products_scraped += 1
                    
                    # Update session progress
                    session.last_processed_index = idx
                    session.last_processed_url = product_url
                    session.save()
                    
                except Exception as db_error:
                    session.products_failed += 1
                    log_message(session, 'error', f'Database error for product: {str(db_error)}', 
                            product_url=product_url, product_sku=product_info['sku'], 
                            exception_details=traceback.format_exc())
                    continue
                
            except requests.exceptions.RequestException as req_error:
                session.products_failed += 1
                log_message(session, 'error', f'Request error for product {product_url}: {str(req_error)}', 
                          product_url=product_url, exception_details=traceback.format_exc())
                continue
                
            except Exception as product_error:
                session.products_failed += 1
                log_message(session, 'error', f'Error processing product {product_url}: {str(product_error)}', 
                          product_url=product_url, exception_details=traceback.format_exc())
                continue
        
        return {
            'status': 'completed',
            'total_found': session.total_products_found,
            'scraped': session.products_scraped,
            'created': session.products_created,
            'updated': session.products_updated,
            'failed': session.products_failed
        }
        
    except Exception as e:
        log_message(session, 'error', f'Critical error in legacyjudaica scraping: {str(e)}', 
                  exception_details=traceback.format_exc())
        return {
            'status': 'failed',
            'message': str(e)
        }

def extract_mefoarjudaica_product_info(soup, product_url, website_name):
    """
    Extract product information from mefoarjudaica.com product page HTML using BeautifulSoup
    
    Args:
        soup: BeautifulSoup object of the product page
        product_url: URL of the product page
        website_name: Name of the website
        
    Returns:
        dict: Product information dictionary
    """
    try:
        title_tag = soup.find('h1', class_='productView-title')
        title = title_tag.get_text(strip=True) if title_tag else None

        # Description
        description = ''
        desc_div = soup.find(id="tab-description-panel")
        description = desc_div.get_text(separator=' ', strip=True) if desc_div else None

        # Price
        price_span = soup.find("span", class_="price price--withoutTax")
        price = price_span.get_text(strip=True) if price_span else None

        # SKU
        sku_span = soup.find("dd", class_="productView-info-value", attrs={"data-product-sku": True})
        sku = sku_span.get_text(strip=True) if sku_span else None


        # Image URL
        # From <img src="">
        image_links = set()
        image_urls  = []
        for a in soup.find_all("a", href=True):
            if a["href"].endswith((".png", ".jpg", ".jpeg", ".webp")):
                image_links.add(a["href"])

        # From <img src="">
        for img in soup.find_all("img", src=True):
            if img["src"].endswith((".png", ".jpg", ".jpeg", ".webp")):
                image_links.add(img["src"])

        # From <img data-lazy="">
        for img in soup.find_all("img", {"data-lazy": True}):
            if img["data-lazy"].endswith((".png", ".jpg", ".jpeg", ".webp")):
                image_links.add(img["data-lazy"])
        image_urls = list(image_links)

        
        category = ''
        lis = soup.select("breadcrumbs li")

        # Get second last li
        second_last = lis[-2] if len(lis) > 2 else None

        # Extract the text (strip spaces)
        category = ''
        if second_last:
            category = second_last.get_text(strip=True)
        
        
        # Generate unique product variant ID (using URL + SKU)
        product_variant_id = f"{website_name}_{hash(product_url)}"
        
        # Check if product is in stock (assume in stock if price exists)
        in_stock = bool(price)
        
        product_info = {
            'product_variant_id': product_variant_id,
            'name': title,
            'sku': sku,
            'price': price,
            'vendor': '',
            'category': category,  # Use vendor as category since there's no separate category
            'description': description,
            'in_stock': in_stock,
            'link': product_url,
            'image_link': ",".join(image_urls[:2]),
            'website': website_name
        }
        
        return product_info
        
    except Exception as e:
        print(f"Error extracting legacyjudaica product info: {e}")
        return None

def scrape_mefoarjudaica_products_common(session, resume_from_index=0):
    """
    Custom scraping function for mefoarjudaica.com using BeautifulSoup
    
    Args:
        session: ScrapingSession object
        resume_from_index: Index to resume from (for resumption)
        
    Returns:
        dict: Scraping results
    """
    log_message(session, 'info', f'Starting custom HTML scraping for {session.website.name}')
    
    try:
        # Get product URLs from sitemap
        product_urls = load_mefoarjudaica_product_urls()
        
        if not product_urls:
            log_message(session, 'error', 'No product URLs found in sitemap')
            return {
                'status': 'failed',
                'message': 'No product URLs found in sitemap'
            }
        
        log_message(session, 'info', f'Found {len(product_urls)} product URLs from sitemap')
        
        # Update total products found
        session.total_products_found = len(product_urls)
        session.save()
        
        # Process products starting from resume index
        for idx, product_url in enumerate(product_urls[resume_from_index:], start=resume_from_index):
            try:
                # Random delay between requests (5-15 seconds)
                if idx > resume_from_index:  # Don't delay on first/resumed request
                    delay = random.randint(5, 15)
                    log_message(session, 'info', f'Waiting {delay} seconds before next request...')
                    time.sleep(delay)
                
                log_message(session, 'info', f'Processing product {idx + 1}/{len(product_urls)}: {product_url}')
                
                # Make request to product page
                response = requests.get(product_url, headers=HEADERS, timeout=30)
                response.raise_for_status()
                
                # Parse HTML with BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract product information
                product_info = extract_ozvehadar_product_info(soup, product_url, session.website.name)
                
                if not product_info:
                    session.products_failed += 1
                    log_message(session, 'warning', f'Failed to extract product info for: {product_url}')
                    continue
                
                # Save or update product in database
                try:
                    # Try to get existing product by variant ID
                    try:
                        product = Product.objects.get(product_variant_id=product_info['product_variant_id'])
                        # Update existing product
                        for key, value in product_info.items():
                            if key not in ['website']:
                                setattr(product, key, value)
                        product.save()
                        session.products_updated += 1
                        log_message(session, 'success', f'Updated product: {product_info["name"]}', 
                                product_url=product_url, product_sku=product_info['sku'])
                    except Product.DoesNotExist:
                        # Create new product
                        try:
                            product = Product.objects.create(**product_info)
                            session.products_created += 1
                            log_message(session, 'success', f'Created new product: {product_info["name"]}', 
                                    product_url=product_url, product_sku=product_info['sku'])
                        except Exception as create_error:
                            # Handle race condition - try to get again
                            try:
                                product = Product.objects.get(product_variant_id=product_info['product_variant_id'])
                                # Update existing product
                                for key, value in product_info.items():
                                    if key not in ['website']:
                                        setattr(product, key, value)
                                product.save()
                                session.products_updated += 1
                                log_message(session, 'success', f'Updated product (race condition): {product_info["name"]}', 
                                        product_url=product_url, product_sku=product_info['sku'])
                            except:
                                raise create_error
                    
                    session.products_scraped += 1
                    
                    # Update session progress
                    session.last_processed_index = idx
                    session.last_processed_url = product_url
                    session.save()
                    
                except Exception as db_error:
                    session.products_failed += 1
                    log_message(session, 'error', f'Database error for product: {str(db_error)}', 
                            product_url=product_url, product_sku=product_info['sku'], 
                            exception_details=traceback.format_exc())
                    continue
                
            except requests.exceptions.RequestException as req_error:
                session.products_failed += 1
                log_message(session, 'error', f'Request error for product {product_url}: {str(req_error)}', 
                          product_url=product_url, exception_details=traceback.format_exc())
                continue
                
            except Exception as product_error:
                session.products_failed += 1
                log_message(session, 'error', f'Error processing product {product_url}: {str(product_error)}', 
                          product_url=product_url, exception_details=traceback.format_exc())
                continue
        
        return {
            'status': 'completed',
            'total_found': session.total_products_found,
            'scraped': session.products_scraped,
            'created': session.products_created,
            'updated': session.products_updated,
            'failed': session.products_failed
        }
        
    except Exception as e:
        log_message(session, 'error', f'Critical error in legacyjudaica scraping: {str(e)}', 
                  exception_details=traceback.format_exc())
        return {
            'status': 'failed',
            'message': str(e)
        }

def extract_kaftorjudaica_product_info(product_url, website_name):
    """
    Extract product information from kaftorjudaica.com product page HTML using BeautifulSoup
    
    Args:
        soup: BeautifulSoup object of the product page
        product_url: URL of the product page
        website_name: Name of the website
        
    Returns:
        dict: Product information dictionary
    """
    try:
        title = product_url['title']

        # Description
        description = ''
        
        # Price
        price = product_url['price']

        # SKU
        sku = product_url['sku']
        # Image URL
        # From <img src="">
        image_urls  = []
        
        image_urls.append(product_url['image'])

        
        category = ''

        
        
        # Generate unique product variant ID (using URL + SKU)
        product_variant_id = f"{website_name}_{hash(product_url['link'])}"
        
        # Check if product is in stock (assume in stock if price exists)
        in_stock = bool(price)
        
        product_info = {
            'product_variant_id': product_variant_id,
            'name': title,
            'sku': sku,
            'price': price,
            'vendor': '',
            'category': category,  # Use vendor as category since there's no separate category
            'description': description,
            'in_stock': in_stock,
            'link': product_url['link'],
            'image_link': ",".join(image_urls[:2]),
            'website': website_name
        }
        
        return product_info
        
    except Exception as e:
        print(f"Error extracting legacyjudaica product info: {e}")
        return None

def scrape_kaftorjudaica_products_common(session, resume_from_index=0):
    """
    Custom scraping function for kaftorjudaica.com using BeautifulSoup
    
    Args:
        session: ScrapingSession object
        resume_from_index: Index to resume from (for resumption)
        
    Returns:
        dict: Scraping results
    """
    log_message(session, 'info', f'Starting custom HTML scraping for {session.website.name}')
    
    try:
        # Get product URLs from sitemap
        product_urls = load_kaftorjudaica_product_urls()
        
        if not product_urls:
            log_message(session, 'error', 'No product URLs found in sitemap')
            return {
                'status': 'failed',
                'message': 'No product URLs found in sitemap'
            }
        
        log_message(session, 'info', f'Found {len(product_urls)} product URLs from sitemap')
        
        # Update total products found
        session.total_products_found = len(product_urls)
        session.save()
        
        # Process products starting from resume index
        for idx, product_url in enumerate(product_urls[resume_from_index:], start=resume_from_index):
            try:
                # Random delay between requests (5-15 seconds)
                # if idx > resume_from_index:  # Don't delay on first/resumed request
                    # delay = random.randint(5, 15)
                    # log_message(session, 'info', f'No delay')
                    # time.sleep(delay)
                
                log_message(session, 'info', f'Processing product {idx + 1}/{len(product_urls)}: {product_url}')
                
                # Make request to product page
                # response = requests.get(product_url, headers=HEADERS, timeout=30)
                # response.raise_for_status()
                
                # # Parse HTML with BeautifulSoup
                # soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract product information
                product_info = extract_kaftorjudaica_product_info(product_url, session.website.name)
                
                if not product_info:
                    session.products_failed += 1
                    log_message(session, 'warning', f'Failed to extract product info for: {product_url}')
                    continue
                
                # Save or update product in database
                try:
                    # Try to get existing product by variant ID
                    try:
                        product = Product.objects.get(product_variant_id=product_info['product_variant_id'])
                        # Update existing product
                        for key, value in product_info.items():
                            if key not in ['website']:
                                setattr(product, key, value)
                        product.save()
                        session.products_updated += 1
                        log_message(session, 'success', f'Updated product: {product_info["name"]}', 
                                product_url=product_url, product_sku=product_info['sku'])
                    except Product.DoesNotExist:
                        # Create new product
                        try:
                            product = Product.objects.create(**product_info)
                            session.products_created += 1
                            log_message(session, 'success', f'Created new product: {product_info["name"]}', 
                                    product_url=product_url, product_sku=product_info['sku'])
                        except Exception as create_error:
                            # Handle race condition - try to get again
                            try:
                                product = Product.objects.get(product_variant_id=product_info['product_variant_id'])
                                # Update existing product
                                for key, value in product_info.items():
                                    if key not in ['website']:
                                        setattr(product, key, value)
                                product.save()
                                session.products_updated += 1
                                log_message(session, 'success', f'Updated product (race condition): {product_info["name"]}', 
                                        product_url=product_url, product_sku=product_info['sku'])
                            except:
                                raise create_error
                    
                    session.products_scraped += 1
                    
                    # Update session progress
                    session.last_processed_index = idx
                    session.last_processed_url = product_url
                    session.save()
                    
                except Exception as db_error:
                    session.products_failed += 1
                    log_message(session, 'error', f'Database error for product: {str(db_error)}', 
                            product_url=product_url, product_sku=product_info['sku'], 
                            exception_details=traceback.format_exc())
                    continue
                
            except requests.exceptions.RequestException as req_error:
                session.products_failed += 1
                log_message(session, 'error', f'Request error for product {product_url}: {str(req_error)}', 
                          product_url=product_url, exception_details=traceback.format_exc())
                continue
                
            except Exception as product_error:
                session.products_failed += 1
                log_message(session, 'error', f'Error processing product {product_url}: {str(product_error)}', 
                          product_url=product_url, exception_details=traceback.format_exc())
                continue
        
        return {
            'status': 'completed',
            'total_found': session.total_products_found,
            'scraped': session.products_scraped,
            'created': session.products_created,
            'updated': session.products_updated,
            'failed': session.products_failed
        }
        
    except Exception as e:
        log_message(session, 'error', f'Critical error in legacyjudaica scraping: {str(e)}', 
                  exception_details=traceback.format_exc())
        return {
            'status': 'failed',
            'message': str(e)
        }

def extract_ozvehadar_product_info(soup, product_url, website_name):
    """
    Extract product information from ozvehadar.us product page HTML using BeautifulSoup
    
    Args:
        soup: BeautifulSoup object of the product page
        product_url: URL of the product page
        website_name: Name of the website
        
    Returns:
        dict: Product information dictionary
    """
    try:
        title_tag = soup.find('h1', class_='productView-title')
        title = title_tag.get_text(strip=True) if title_tag else None

        # Description
        decription = ''
        desc_div = soup.find(id="tab-description")
        description = desc_div.get_text(separator=' ', strip=True) if desc_div else None

        # Price
        price_span = soup.find("span", class_="price price--withoutTax")
        price = price_span.get_text(strip=True) if price_span else None

        # SKU
        sku_span = soup.find("dd", {"data-product-sku": True})
        sku = sku_span.get_text(strip=True) if sku_span else None

        # Image URL
        # From <img src="">
        image_links = set()
        image_urls  = []
        for a in soup.find_all("a", href=True):
            if a["href"].endswith((".png", ".jpg", ".jpeg", ".webp")):
                image_links.add(a["href"])

        # From <img src="">
        for img in soup.find_all("img", src=True):
            if img["src"].endswith((".png", ".jpg", ".jpeg", ".webp")):
                image_links.add(img["src"])

        # From <img data-lazy="">
        for img in soup.find_all("img", {"data-lazy": True}):
            if img["data-lazy"].endswith((".png", ".jpg", ".jpeg", ".webp")):
                image_links.add(img["data-lazy"])
        image_urls = list(image_links)

        
        category = ''
        lis = soup.select("ol.breadcrumbs li")

        # Get second last li
        second_last = lis[-2] if len(lis) > 2 else None

        # Extract the text (strip spaces)
        category = ''
        if second_last:
            category = second_last.get_text(strip=True)
        
        
        # Generate unique product variant ID (using URL + SKU)
        product_variant_id = f"{website_name}_{hash(product_url)}"
        
        # Check if product is in stock (assume in stock if price exists)
        in_stock = bool(price)
        
        product_info = {
            'product_variant_id': product_variant_id,
            'name': title,
            'sku': sku,
            'price': price,
            'vendor': '',
            'category': category,  # Use vendor as category since there's no separate category
            'description': description,
            'in_stock': in_stock,
            'link': product_url,
            'image_link': ",".join(image_urls[:2]),
            'website': website_name
        }
        
        return product_info
        
    except Exception as e:
        print(f"Error extracting legacyjudaica product info: {e}")
        return None

def scrape_ozvehadar_products_common(session, resume_from_index=0):
    """
    Custom scraping function for ozvehadar.us using BeautifulSoup
    
    Args:
        session: ScrapingSession object
        resume_from_index: Index to resume from (for resumption)
        
    Returns:
        dict: Scraping results
    """
    log_message(session, 'info', f'Starting custom HTML scraping for {session.website.name}')
    
    try:
        # Get product URLs from sitemap
        product_urls = load_ozvehadar_product_urls()
        
        if not product_urls:
            log_message(session, 'error', 'No product URLs found in sitemap')
            return {
                'status': 'failed',
                'message': 'No product URLs found in sitemap'
            }
        
        log_message(session, 'info', f'Found {len(product_urls)} product URLs from sitemap')
        
        # Update total products found
        session.total_products_found = len(product_urls)
        session.save()
        
        # Process products starting from resume index
        for idx, product_url in enumerate(product_urls[resume_from_index:], start=resume_from_index):
            try:
                # Random delay between requests (5-15 seconds)
                if idx > resume_from_index:  # Don't delay on first/resumed request
                    delay = random.randint(5, 15)
                    log_message(session, 'info', f'Waiting {delay} seconds before next request...')
                    time.sleep(delay)
                
                log_message(session, 'info', f'Processing product {idx + 1}/{len(product_urls)}: {product_url}')
                
                # Make request to product page
                response = requests.get(product_url, headers=HEADERS, timeout=30)
                response.raise_for_status()
                
                # Parse HTML with BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract product information
                product_info = extract_ozvehadar_product_info(soup, product_url, session.website.name)
                
                if not product_info:
                    session.products_failed += 1
                    log_message(session, 'warning', f'Failed to extract product info for: {product_url}')
                    continue
                
                # Save or update product in database
                try:
                    # Try to get existing product by variant ID
                    try:
                        product = Product.objects.get(product_variant_id=product_info['product_variant_id'])
                        # Update existing product
                        for key, value in product_info.items():
                            if key not in ['website']:
                                setattr(product, key, value)
                        product.save()
                        session.products_updated += 1
                        log_message(session, 'success', f'Updated product: {product_info["name"]}', 
                                product_url=product_url, product_sku=product_info['sku'])
                    except Product.DoesNotExist:
                        # Create new product
                        try:
                            product = Product.objects.create(**product_info)
                            session.products_created += 1
                            log_message(session, 'success', f'Created new product: {product_info["name"]}', 
                                    product_url=product_url, product_sku=product_info['sku'])
                        except Exception as create_error:
                            # Handle race condition - try to get again
                            try:
                                product = Product.objects.get(product_variant_id=product_info['product_variant_id'])
                                # Update existing product
                                for key, value in product_info.items():
                                    if key not in ['website']:
                                        setattr(product, key, value)
                                product.save()
                                session.products_updated += 1
                                log_message(session, 'success', f'Updated product (race condition): {product_info["name"]}', 
                                        product_url=product_url, product_sku=product_info['sku'])
                            except:
                                raise create_error
                    
                    session.products_scraped += 1
                    
                    # Update session progress
                    session.last_processed_index = idx
                    session.last_processed_url = product_url
                    session.save()
                    
                except Exception as db_error:
                    session.products_failed += 1
                    log_message(session, 'error', f'Database error for product: {str(db_error)}', 
                            product_url=product_url, product_sku=product_info['sku'], 
                            exception_details=traceback.format_exc())
                    continue
                
            except requests.exceptions.RequestException as req_error:
                session.products_failed += 1
                log_message(session, 'error', f'Request error for product {product_url}: {str(req_error)}', 
                          product_url=product_url, exception_details=traceback.format_exc())
                continue
                
            except Exception as product_error:
                session.products_failed += 1
                log_message(session, 'error', f'Error processing product {product_url}: {str(product_error)}', 
                          product_url=product_url, exception_details=traceback.format_exc())
                continue
        
        return {
            'status': 'completed',
            'total_found': session.total_products_found,
            'scraped': session.products_scraped,
            'created': session.products_created,
            'updated': session.products_updated,
            'failed': session.products_failed
        }
        
    except Exception as e:
        log_message(session, 'error', f'Critical error in legacyjudaica scraping: {str(e)}', 
                  exception_details=traceback.format_exc())
        return {
            'status': 'failed',
            'message': str(e)
        }

def extract_craftsandmore_product_info(soup, product_url, website_name):
    """
    Extract product information from craftsandmore.com product page HTML using BeautifulSoup
    
    Args:
        soup: BeautifulSoup object of the product page
        product_url: URL of the product page
        website_name: Name of the website
        
    Returns:
        dict: Product information dictionary
    """
    try:
        title_tag = soup.select_one("h1.product_title.entry-title.wd-entities-title")
        title = title_tag.get_text(strip=True) if title_tag else None

        # Description
        description = ''
        desc_div = soup.find("div", class_=["markdown", "prose", "dark:prose-invert", "w-full", "break-words", "light"])
        description = desc_div.get_text(separator=' ', strip=True) if desc_div else None

        # Price
        price_span = soup.find("p", class_="price")
        price = price_span.get_text(strip=True) if price_span else None

        # SKU
        sku_span = soup.find("span", class_="sku_wrapper")
        sku = sku_span.get_text(strip=True) if sku_span else None
        sku = sku.replace('Item# ', '').strip()

        

        # Image URL
        fig = soup.select_one('figure.woocommerce-product-gallery__image')
        image_link = ''

        if fig:
            a_tag = fig.find('a')
            if a_tag and a_tag.get('href'):
                image_link = a_tag['href']

        

        category = ''
        # find all <a> tags inside the breadcrumb nav
        links = soup.select("nav.woocommerce-breadcrumb a")

        # get second last link text
        if len(links) >= 2:
            category = links[-1].get_text(strip=True)
            
        # Generate unique product variant ID (using URL + SKU)
        product_variant_id = f"{website_name}_{hash(product_url)}"
        
        # Check if product is in stock (assume in stock if price exists)
        in_stock = bool(price)
        
        product_info = {
            'product_variant_id': product_variant_id,
            'name': title,
            'sku': sku,
            'price': price,
            'vendor': '',
            'category': category,  # Use vendor as category since there's no separate category
            'description': description,
            'in_stock': in_stock,
            'link': product_url,
            'image_link': image_link,
            'website': website_name
        }
        
        return product_info
        
    except Exception as e:
        print(f"Error extracting legacyjudaica product info: {e}")
        return None

def scrape_craftsandmore_products_common(session, resume_from_index=0):
    """
    Custom scraping function for craftsandmore.com using BeautifulSoup
    
    Args:
        session: ScrapingSession object
        resume_from_index: Index to resume from (for resumption)
        
    Returns:
        dict: Scraping results
    """
    log_message(session, 'info', f'Starting custom HTML scraping for {session.website.name}')
    
    try:
        # Get product URLs from sitemap
        product_urls = load_craftsandmore_product_urls()
        
        if not product_urls:
            log_message(session, 'error', 'No product URLs found in sitemap')
            return {
                'status': 'failed',
                'message': 'No product URLs found in sitemap'
            }
        
        log_message(session, 'info', f'Found {len(product_urls)} product URLs from sitemap')
        
        # Update total products found
        session.total_products_found = len(product_urls)
        session.save()
        
        # Process products starting from resume index
        for idx, product_url in enumerate(product_urls[resume_from_index:], start=resume_from_index):
            try:
                # Random delay between requests (5-15 seconds)
                if idx > resume_from_index:  # Don't delay on first/resumed request
                    delay = random.randint(5, 15)
                    log_message(session, 'info', f'Waiting {delay} seconds before next request...')
                    time.sleep(delay)
                
                log_message(session, 'info', f'Processing product {idx + 1}/{len(product_urls)}: {product_url}')
                
                # Make request to product page
                response = requests.get(product_url, headers=HEADERS, timeout=30)
                response.raise_for_status()
                
                # Parse HTML with BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract product information
                product_info = extract_craftsandmore_product_info(soup, product_url, session.website.name)
                
                if not product_info:
                    session.products_failed += 1
                    log_message(session, 'warning', f'Failed to extract product info for: {product_url}')
                    continue
                
                # Save or update product in database
                try:
                    # Try to get existing product by variant ID
                    try:
                        product = Product.objects.get(product_variant_id=product_info['product_variant_id'])
                        # Update existing product
                        for key, value in product_info.items():
                            if key not in ['website']:
                                setattr(product, key, value)
                        product.save()
                        session.products_updated += 1
                        log_message(session, 'success', f'Updated product: {product_info["name"]}', 
                                product_url=product_url, product_sku=product_info['sku'])
                    except Product.DoesNotExist:
                        # Create new product
                        try:
                            product = Product.objects.create(**product_info)
                            session.products_created += 1
                            log_message(session, 'success', f'Created new product: {product_info["name"]}', 
                                    product_url=product_url, product_sku=product_info['sku'])
                        except Exception as create_error:
                            # Handle race condition - try to get again
                            try:
                                product = Product.objects.get(product_variant_id=product_info['product_variant_id'])
                                # Update existing product
                                for key, value in product_info.items():
                                    if key not in ['website']:
                                        setattr(product, key, value)
                                product.save()
                                session.products_updated += 1
                                log_message(session, 'success', f'Updated product (race condition): {product_info["name"]}', 
                                        product_url=product_url, product_sku=product_info['sku'])
                            except:
                                raise create_error
                    
                    session.products_scraped += 1
                    
                    # Update session progress
                    session.last_processed_index = idx
                    session.last_processed_url = product_url
                    session.save()
                    
                except Exception as db_error:
                    session.products_failed += 1
                    log_message(session, 'error', f'Database error for product: {str(db_error)}', 
                            product_url=product_url, product_sku=product_info['sku'], 
                            exception_details=traceback.format_exc())
                    continue
                
            except requests.exceptions.RequestException as req_error:
                session.products_failed += 1
                log_message(session, 'error', f'Request error for product {product_url}: {str(req_error)}', 
                          product_url=product_url, exception_details=traceback.format_exc())
                continue
                
            except Exception as product_error:
                session.products_failed += 1
                log_message(session, 'error', f'Error processing product {product_url}: {str(product_error)}', 
                          product_url=product_url, exception_details=traceback.format_exc())
                continue
        
        return {
            'status': 'completed',
            'total_found': session.total_products_found,
            'scraped': session.products_scraped,
            'created': session.products_created,
            'updated': session.products_updated,
            'failed': session.products_failed
        }
        
    except Exception as e:
        log_message(session, 'error', f'Critical error in legacyjudaica scraping: {str(e)}', 
                  exception_details=traceback.format_exc())
        return {
            'status': 'failed',
            'message': str(e)
        }

def extract_zionjudaica_product_info(soup, product_url, website_name):
    """
    Extract product information from zionjudaica.com product page HTML using BeautifulSoup
    
    Args:
        soup: BeautifulSoup object of the product page
        product_url: URL of the product page
        website_name: Name of the website
        
    Returns:
        dict: Product information dictionary
    """
    try:



        title_tag = soup.select_one("h1.fusion-title-heading")
        title = title_tag.get_text(strip=True) if title_tag else None

        # Description
        description = ''
        desc_div = soup.select_one("#productContent p")
        description = desc_div.get_text(strip=True) if desc_div else None

        # Price
        
        
        price = (soup.select_one("p.price ins bdi") or soup.select_one("p.price bdi")).get_text(strip=True)

        # SKU
        sku_span = soup.select_one(".sku")
        sku = sku_span.get_text(strip=True) if sku_span else None

        

        # Image URL
        image_link = ''

        image = soup.select_one(".woocommerce-product-gallery__image a[href]")
        image_link = image["href"] if image else ''

        

        category = soup.select("ol.awb-breadcrumb-list li a span")[-1].get_text(strip=True)
        # Generate unique product variant ID (using URL + SKU)
        product_variant_id = f"{website_name}_{hash(product_url)}"
        
        # Check if product is in stock (assume in stock if price exists)
        in_stock = bool(price)
        
        product_info = {
            'product_variant_id': product_variant_id,
            'name': title,
            'sku': sku,
            'price': price,
            'vendor': '',
            'category': category,  # Use vendor as category since there's no separate category
            'description': description,
            'in_stock': in_stock,
            'link': product_url,
            'image_link': image_link,
            'website': website_name
        }
        
        return product_info
        
    except Exception as e:
        print(f"Error extracting legacyjudaica product info: {e}")
        return None

def scrape_zionjudaica_products_common(session, resume_from_index=0):
    """
    Custom scraping function for zionjudaica.com using BeautifulSoup
    
    Args:
        session: ScrapingSession object
        resume_from_index: Index to resume from (for resumption)
        
    Returns:
        dict: Scraping results
    """
    log_message(session, 'info', f'Starting custom HTML scraping for {session.website.name}')
    
    try:
        # Get product URLs from sitemap
        product_urls = get_zionjudaica_urls()
        
        if not product_urls:
            log_message(session, 'error', 'No product URLs found in sitemap')
            return {
                'status': 'failed',
                'message': 'No product URLs found in sitemap'
            }
        
        log_message(session, 'info', f'Found {len(product_urls)} product URLs from sitemap')
        
        # Update total products found
        session.total_products_found = len(product_urls)
        session.save()
        
        # Process products starting from resume index
        for idx, product_url in enumerate(product_urls[resume_from_index:], start=resume_from_index):
            try:
                # Random delay between requests (5-15 seconds)
                if idx > resume_from_index:  # Don't delay on first/resumed request
                    delay = random.randint(5, 15)
                    log_message(session, 'info', f'Waiting {delay} seconds before next request...')
                    time.sleep(delay)
                
                log_message(session, 'info', f'Processing product {idx + 1}/{len(product_urls)}: {product_url}')
                
                # Make request to product page
                response = requests.get(product_url, headers=HEADERS, timeout=30)
                response.raise_for_status()
                
                # Parse HTML with BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract product information
                product_info = extract_zionjudaica_product_info(soup, product_url, session.website.name)
                
                if not product_info:
                    session.products_failed += 1
                    log_message(session, 'warning', f'Failed to extract product info for: {product_url}')
                    continue
                
                # Save or update product in database
                try:
                    # Try to get existing product by variant ID
                    try:
                        product = Product.objects.get(product_variant_id=product_info['product_variant_id'])
                        # Update existing product
                        for key, value in product_info.items():
                            if key not in ['website']:
                                setattr(product, key, value)
                        product.save()
                        session.products_updated += 1
                        log_message(session, 'success', f'Updated product: {product_info["name"]}', 
                                product_url=product_url, product_sku=product_info['sku'])
                    except Product.DoesNotExist:
                        # Create new product
                        try:
                            product = Product.objects.create(**product_info)
                            session.products_created += 1
                            log_message(session, 'success', f'Created new product: {product_info["name"]}', 
                                    product_url=product_url, product_sku=product_info['sku'])
                        except Exception as create_error:
                            # Handle race condition - try to get again
                            try:
                                product = Product.objects.get(product_variant_id=product_info['product_variant_id'])
                                # Update existing product
                                for key, value in product_info.items():
                                    if key not in ['website']:
                                        setattr(product, key, value)
                                product.save()
                                session.products_updated += 1
                                log_message(session, 'success', f'Updated product (race condition): {product_info["name"]}', 
                                        product_url=product_url, product_sku=product_info['sku'])
                            except:
                                raise create_error
                    
                    session.products_scraped += 1
                    
                    # Update session progress
                    session.last_processed_index = idx
                    session.last_processed_url = product_url
                    session.save()
                    
                except Exception as db_error:
                    session.products_failed += 1
                    log_message(session, 'error', f'Database error for product: {str(db_error)}', 
                            product_url=product_url, product_sku=product_info['sku'], 
                            exception_details=traceback.format_exc())
                    continue
                
            except requests.exceptions.RequestException as req_error:
                session.products_failed += 1
                log_message(session, 'error', f'Request error for product {product_url}: {str(req_error)}', 
                          product_url=product_url, exception_details=traceback.format_exc())
                continue
                
            except Exception as product_error:
                session.products_failed += 1
                log_message(session, 'error', f'Error processing product {product_url}: {str(product_error)}', 
                          product_url=product_url, exception_details=traceback.format_exc())
                continue
        
        return {
            'status': 'completed',
            'total_found': session.total_products_found,
            'scraped': session.products_scraped,
            'created': session.products_created,
            'updated': session.products_updated,
            'failed': session.products_failed
        }
        
    except Exception as e:
        log_message(session, 'error', f'Critical error in zionjudaica scraping: {str(e)}', 
                  exception_details=traceback.format_exc())
        return {
            'status': 'failed',
            'message': str(e)
        }


# shopify websites
@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_ezpekalach(self, session_id, resume_from_page=1):
    """Scraper for ezpekalach.com with queue management"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_ezpekalach.apply_async(
            args=[session_id, resume_from_page],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'base_url': 'ezpekalach.com',
        'custom_domain': None
    }
    return scrape_shopify_website_common(session_id, website_config, self, resume_from_page)
@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_alef_to_tav_collection(self, session_id, resume_from_page=1):
    """Scraper for alef-to-tav Collection with queue management"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_alef_to_tav_collection.apply_async(
            args=[session_id, resume_from_page],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'base_url': 'alef-to-tav.com',
        'custom_domain': None
    }
    return scrape_shopify_website_common(session_id, website_config, self, resume_from_page)

@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_chazakkinder_collection(self, session_id, resume_from_page=1):
    """Scraper for chazakkinder Collection with queue management"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_chazakkinder_collection.apply_async(
            args=[session_id, resume_from_page],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'base_url': 'www.chazakkinder.com',
        'custom_domain': None
    }
    return scrape_shopify_website_common(session_id, website_config, self, resume_from_page)

@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_thekoshercook_collection(self, session_id, resume_from_page=1):
    """Scraper for thekoshercook Collection with queue management"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_thekoshercook_collection.apply_async(
            args=[session_id, resume_from_page],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'base_url': 'www.thekoshercook.com',
        'custom_domain': None
    }
    return scrape_shopify_website_common(session_id, website_config, self, resume_from_page)

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
def scrape_nermitzvah(self, session_id, resume_from_page=1):
    """Scraper for Waterdale Collection with queue management"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_nermitzvah.apply_async(
            args=[session_id, resume_from_page],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'base_url': 'www.nermitzvah.com',
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
def scrape_colourscrafts(self, session_id, resume_from_page=1):
    """Scraper for Feldart with queue management"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_colourscrafts.apply_async(
            args=[session_id, resume_from_page],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'base_url': 'colourscrafts.com',
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

@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_gramcoschoolsupplies(self, session_id, resume_from_page=1):
    """Scraper for gramcoschoolsupplies with queue management"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_gramcoschoolsupplies.apply_async(
            args=[session_id, resume_from_page],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'base_url': 'www.gramcoschoolsupplies.com',
        'custom_domain': None
    }
    return scrape_shopify_website_common(session_id, website_config, self, resume_from_page)

@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_davidjudaica(self, session_id, resume_from_page=1):
    """Scraper for davidjudaica.shop with queue management"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_davidjudaica.apply_async(
            args=[session_id, resume_from_page],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'base_url': 'www.davidjudaica.shop',
        'custom_domain': None
    }
    return scrape_shopify_website_common(session_id, website_config, self, resume_from_page)

@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_classictouchdecor(self, session_id, resume_from_page=1):
    """Scraper for classictouchdecor.com with queue management"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_classictouchdecor.apply_async(
            args=[session_id, resume_from_page],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'base_url': 'www.classictouchdecor.com',
        'custom_domain': None
    }
    return scrape_shopify_website_common(session_id, website_config, self, resume_from_page)

# custom websites
@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_meiros(self, session_id, resume_from_index=0):
    """Custom scraper for meiros.com with queue management and BeautifulSoup"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_meiros.apply_async(
            args=[session_id, resume_from_index],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'scraper_type': 'meiros',
        'base_url': 'meiros.com',
        'custom_domain': None
    }
    return scrape_custom_website_common(session_id, website_config, self, resume_from_index)

@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_ritelite(self, session_id, resume_from_index=0):
    """Custom scraper for ritelite.com with queue management and BeautifulSoup"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_ritelite.apply_async(
            args=[session_id, resume_from_index],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'scraper_type': 'ritelite',
        'base_url': 'ritelite.com',
        'custom_domain': None
    }
    return scrape_custom_website_common(session_id, website_config, self, resume_from_index)

@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_shaijudaica(self, session_id, resume_from_index=0):
    """Custom scraper for shaijudaica.co.il with queue management and BeautifulSoup"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_shaijudaica.apply_async(
            args=[session_id, resume_from_index],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'scraper_type': 'shaijudaica',
        'base_url': 'shaijudaica.co.il',
        'custom_domain': None
    }
    return scrape_custom_website_common(session_id, website_config, self, resume_from_index)

@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_jewisheducationaltoys(self, session_id, resume_from_index=0):
    """Custom scraper for jewisheducationaltoys.com with queue management and BeautifulSoup"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_jewisheducationaltoys.apply_async(
            args=[session_id, resume_from_index],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'scraper_type': 'jewisheducationaltoys',
        'base_url': 'jewisheducationaltoys.com',
        'custom_domain': None
    }
    return scrape_custom_website_common(session_id, website_config, self, resume_from_index)

@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_legacyjudaica(self, session_id, resume_from_index=0):
    """Custom scraper for legacyjudaica.com with queue management and BeautifulSoup"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_legacyjudaica.apply_async(
            args=[session_id, resume_from_index],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'scraper_type': 'legacyjudaica',
        'base_url': 'legacyjudaica.com',
        'custom_domain': None
    }
    return scrape_custom_website_common(session_id, website_config, self, resume_from_index)

@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_simchonim(self, session_id, resume_from_index=0):
    """Custom scraper for simchonim.com with queue management and BeautifulSoup"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_simchonim.apply_async(
            args=[session_id, resume_from_index],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'scraper_type': 'simchonim',
        'base_url': 'simchonim.com',
        'custom_domain': None
    }
    return scrape_custom_website_common(session_id, website_config, self, resume_from_index)

@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_kaftorjudaica(self, session_id, resume_from_index=0):
    """Custom scraper for kaftorjudaica.com with queue management and BeautifulSoup"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_kaftorjudaica.apply_async(
            args=[session_id, resume_from_index],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'scraper_type': 'kaftorjudaica',
        'base_url': 'www.kaftorjudaica.com',
        'custom_domain': None
    }
    return scrape_custom_website_common(session_id, website_config, self, resume_from_index)
@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_mefoarjudaica(self, session_id, resume_from_index=0):
    """Custom scraper for mefoarjudaica.com with queue management and BeautifulSoup"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_mefoarjudaica.apply_async(
            args=[session_id, resume_from_index],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'scraper_type': 'mefoarjudaica',
        'base_url': 'mefoarjudaica.com',
        'custom_domain': None
    }
    return scrape_custom_website_common(session_id, website_config, self, resume_from_index)

@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_ozvehadar(self, session_id, resume_from_index=0):
    """Custom scraper for ozvehadar.us with queue management and BeautifulSoup"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_ozvehadar.apply_async(
            args=[session_id, resume_from_index],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'scraper_type': 'ozvehadar',
        'base_url': 'ozvehadar.us',
        'custom_domain': None
    }
    return scrape_custom_website_common(session_id, website_config, self, resume_from_index)

@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_craftsandmore(self, session_id, resume_from_index=0):
    """Custom scraper for craftsandmore.com with queue management and BeautifulSoup"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_craftsandmore.apply_async(
            args=[session_id, resume_from_index],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'scraper_type': 'craftsandmore',
        'base_url': 'craftsandmore.com',
        'custom_domain': None
    }
    return scrape_custom_website_common(session_id, website_config, self, resume_from_index)

@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)
def scrape_zionjudaica(self, session_id, resume_from_index=0):
    """Custom scraper for zionjudaica.com with queue management and BeautifulSoup"""
    # Check if we can start (max 2 concurrent scrapers)
    if not can_start_scraper():
        session = ScrapingSession.objects.get(id=session_id)
        log_message(session, 'info', 'Scraper queued - waiting for available slot (max 2 concurrent scrapers)')
        
        # Retry after 30 seconds
        scrape_zionjudaica.apply_async(
            args=[session_id, resume_from_index],
            countdown=30
        )
        return {'status': 'queued', 'message': 'Waiting for available scraper slot'}
    
    website_config = {
        'scraper_type': 'zionjudaica',
        'base_url': 'zionjudaica.com',
        'custom_domain': None
    }
    return scrape_custom_website_common(session_id, website_config, self, resume_from_index)

import logging
logger = logging.getLogger(__name__)

@shared_task(bind=True, soft_time_limit=3600, time_limit=3660)
def export_products_to_google_sheet(self, export_id, website_filter='all'):
    """
    Export products to Google Sheet in background with progress tracking using OAuth2
    Updates existing sheet if available, otherwise creates new one
    
    Args:
        export_id: ID of the GoogleSheetLinks record
        website_filter: 'all' or specific website name
    """
    import xlsxwriter
    from io import BytesIO
    from django.utils import timezone
    from googleapiclient.http import MediaIoBaseUpload
    from .google_auth import google_auth_manager
    
    try:
        # Get the export record
        export_record = GoogleSheetLinks.objects.get(id=export_id)
        
        # Update status to processing
        export_record.status = 'processing'
        export_record.celery_task_id = self.request.id
        export_record.save()
        
        # Check if OAuth2 credentials are available
        credentials = google_auth_manager.get_active_credentials()
        if not credentials:
            export_record.status = 'failed'
            export_record.error_message = 'No valid Google OAuth2 credentials found. Please authorize the application first.'
            export_record.save()
            return {'status': 'failed', 'message': 'Google authorization required. Please authorize the application first.'}
        
        # Get products based on filter
        if website_filter == 'all':
            products = Product.objects.all().order_by('website', 'created_at')
            sheet_name = "All Products"
        else:
            website = Website.objects.get(id=website_filter)
            products = Product.objects.filter(website=website.name).order_by('created_at')
            sheet_name = f"{website.name} Products"
        
        # Update total products count
        total_products = products.count()
        export_record.total_products = total_products
        export_record.filename = sheet_name
        export_record.save()
        
        if total_products == 0:
            export_record.status = 'failed'
            export_record.error_message = 'No products found to export'
            export_record.save()
            return {'status': 'failed', 'message': 'No products found to export'}
        
        # Build Drive and Sheets services using OAuth2
        drive_service = google_auth_manager.build_drive_service()
        sheets_service = google_auth_manager.build_sheets_service()
        
        # Check if we have an existing sheet for this filter
        existing_file_id = None
        try:
            # Look for the most recent completed export with the same filter
            last_export = GoogleSheetLinks.objects.filter(
                website_filter=website_filter,
                status='completed',
                sheet_file_id__isnull=False
            ).exclude(id=export_id).order_by('-completed_at').first()
            
            if last_export and last_export.sheet_file_id:
                # Verify the file still exists in Google Drive
                try:
                    drive_service.files().get(fileId=last_export.sheet_file_id).execute()
                    existing_file_id = last_export.sheet_file_id
                    logger.info(f"Found existing sheet to update: {existing_file_id}")
                except:
                    logger.info("Previous sheet no longer exists, will create new one")
                    existing_file_id = None
        except Exception as e:
            logger.warning(f"Error checking for existing sheet: {e}")
            existing_file_id = None
        
        if existing_file_id:
            # Update existing sheet
            file_id = existing_file_id
            logger.info(f"Updating existing Google Sheet: {file_id}")
            
            # Update progress to 85%
            export_record.progress_percentage = 85
            export_record.save()
            
            # Get sheet metadata
            sheet_metadata = sheets_service.spreadsheets().get(spreadsheetId=file_id).execute()
            sheet_id = sheet_metadata['sheets'][0]['properties']['sheetId']
            
            # Clear existing data (keep header)
            logger.info("Clearing existing data...")
            sheets_service.spreadsheets().values().clear(
                spreadsheetId=file_id,
                range='A2:Z'  # Clear from row 2 onwards, keep headers
            ).execute()
            
        else:
            # Create new sheet
            logger.info("Creating new Google Sheet...")
            
            # Create Excel file in memory
            output = BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            worksheet = workbook.add_worksheet('Products')
            
            # Add headers
            headers = ['Website', 'Name', 'SKU', 'Price', 'Category', 'Vendor', 'InStock', 'Description', 'Image Link', 'Link', 'Created At', 'Updated At']
            for col, header in enumerate(headers):
                worksheet.write(0, col, header)
            
            workbook.close()
            output.seek(0)
            
            # Update progress to 85% (uploading)
            export_record.progress_percentage = 85
            export_record.save()
            
            media = MediaIoBaseUpload(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            
            # Upload to personal Google Drive
            file_metadata = {
                'name': sheet_name,
                'mimeType': 'application/vnd.google-apps.spreadsheet',
            }
            
            uploaded_file = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            file_id = uploaded_file.get('id')
            logger.info(f"New file created: {file_id}")
            
            # Get sheet metadata
            sheet_metadata = sheets_service.spreadsheets().get(spreadsheetId=file_id).execute()
            sheet_id = sheet_metadata['sheets'][0]['properties']['sheetId']
            
            # Make it public
            drive_service.permissions().create(
                fileId=file_id,
                body={'type': 'anyone', 'role': 'writer'}
            ).execute()
        
        # Prepare data for batch update
        logger.info("Preparing product data...")
        values = []
        processed_count = 0
        batch_size = 100
        
        for i in range(0, total_products, batch_size):
            batch_products = products[i:i + batch_size]
            
            for product in batch_products:
                row = [
                    product.website or '',
                    product.name or '',
                    product.sku or '',
                    product.price or '',
                    product.category or '',
                    product.vendor or '',
                    "Yes" if product.in_stock else "No",
                    product.description or '',
                    ", ".join(product.image_link.split(",")[:2]) if product.image_link else '',
                    product.link or '',
                    product.created_at.strftime('%Y-%m-%d %H:%M:%S') if product.created_at else '',
                    product.updated_at.strftime('%Y-%m-%d %H:%M:%S') if product.updated_at else ''
                ]
                values.append(row)
                processed_count += 1
                
                # Update progress every 50 products
                if processed_count % 50 == 0:
                    progress = 85 + int((processed_count / total_products) * 10)  # 85-95%
                    export_record.processed_products = processed_count
                    export_record.progress_percentage = progress
                    export_record.save()
        
        # Update sheet with all data at once
        logger.info(f"Writing {len(values)} rows to sheet...")
        sheets_service.spreadsheets().values().update(
            spreadsheetId=file_id,
            range='A2',  # Start from row 2 (after headers)
            valueInputOption='RAW',
            body={'values': values}
        ).execute()
        
        # Set row height
        logger.info("Formatting sheet...")
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=file_id,
            body={
                "requests": [
                    {
                        "updateDimensionProperties": {
                            "range": {
                                "sheetId": sheet_id,
                                "dimension": "ROWS",
                                "startIndex": 1,
                                "endIndex": total_products + 2
                            },
                            "properties": {
                                "pixelSize": 25
                            },
                            "fields": "pixelSize"
                        }
                    }
                ]
            }
        ).execute()
        
        # Generate public link
        link = f"https://docs.google.com/spreadsheets/d/{file_id}"
        
        # Update export record with completion
        export_record.status = 'completed'
        export_record.link = link
        export_record.sheet_file_id = file_id  # Store for future reuse
        export_record.progress_percentage = 100
        export_record.completed_at = timezone.now()
        export_record.save()
        
        action = "updated" if existing_file_id else "created"
        logger.info(f"Export completed successfully. Sheet {action}: {link}")
        
        return {
            'status': 'completed',
            'link': link,
            'total_products': total_products,
            'message': f'Successfully {action} Google Sheet with {total_products} products'
        }
        
    except Exception as e:
        # Handle any errors
        try:
            export_record.status = 'failed'
            export_record.error_message = str(e)
            export_record.save()
            logger.error(f"Export failed: {e}")
        except:
            pass
        
        return {'status': 'failed', 'message': str(e)}
