from celery import shared_task
from .scraper_scripts.waterdalecollection import load_xml_sitemap
import requests
import time
from bs4 import BeautifulSoup
from .models import *
import random
import traceback
from django.utils import timezone
from django.db import transaction
from celery.exceptions import SoftTimeLimitExceeded

# Headers for requests
HEADERS = {'User-Agent': 'Mozilla/5.0'}


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


@shared_task(bind=True, soft_time_limit=7200, time_limit=7260)  # 2 hour soft limit, 2h1m hard limit
def scrape_waterdale_collection(self, session_id, resume_from_index=0):
    """
    Enhanced Celery task to scrape products from Waterdale Collection with full logging and state management
    """
    try:
        # Get the scraping session
        session = ScrapingSession.objects.get(id=session_id)
        website = session.website
        
        # Update session status and celery task id
        session.status = 'running'
        session.celery_task_id = self.request.id
        session.save()
        
        # Update website state
        state, created = ScrapingState.objects.get_or_create(website=website)
        state.is_running = True
        state.current_session = session
        state.last_run = timezone.now()
        state.save()
        
        log_message(session, 'info', f'Starting scraping session for {website.name}')
        
        # Load product links
        try:
            product_links = load_xml_sitemap()
            session.total_products_found = len(product_links)
            session.save()
            log_message(session, 'info', f'Found {len(product_links)} product URLs to scrape')
        except Exception as e:
            log_message(session, 'error', f'Failed to load sitemap: {str(e)}', exception_details=traceback.format_exc())
            session.status = 'failed'
            session.completed_at = timezone.now()
            session.save()
            state.is_running = False
            state.save()
            return {'status': 'failed', 'message': 'Failed to load sitemap'}
        
        # Resume from specified index if provided
        start_index = max(resume_from_index, session.last_processed_index)
        if start_index > 0:
            log_message(session, 'info', f'Resuming from index {start_index}')
        
        # Process products
        for idx, link in enumerate(product_links[start_index:], start=start_index + 1):
            try:
                # Check for task revocation
                if self.request.called_directly is False:
                    # Update progress
                    self.update_state(
                        state='PROGRESS',
                        meta={
                            'current': idx,
                            'total': len(product_links),
                            'status': f'Processing product {idx}/{len(product_links)}'
                        }
                    )
                
                log_message(session, 'info', f'[{idx}/{len(product_links)}] Starting to scrape product', product_url=link)
                
                # Make request
                page = requests.get(link, headers=HEADERS, timeout=30)
                page.raise_for_status()
                soup = BeautifulSoup(page.content, 'html.parser')
                
                # Extract product data
                price = soup.select_one('.price__current .money')
                price_text = price.text.strip() if price else None

                sku = soup.select_one('.product-sku__value')
                sku_text = sku.text.strip() if sku else None

                title = soup.select_one('h1.product-title')
                title_text = title.text.strip() if title else None

                description_div = soup.select_one('div.disclosure__content.rte.cf')
                description_text = description_div.get_text(separator=' ', strip=True) if description_div else None

                # Save or update product using get_or_create pattern
                try:
                    # First try to get or create by SKU if available
                    if sku_text:
                        product, created = Product.objects.get_or_create(
                            website=website.name,
                            sku=sku_text,
                            defaults={
                                'name': title_text,
                                'price': price_text,
                                'description': description_text,
                                'link': link
                            }
                        )
                    else:
                        # If no SKU, try by link
                        product, created = Product.objects.get_or_create(
                            website=website.name,
                            link=link,
                            defaults={
                                'name': title_text,
                                'sku': sku_text,
                                'price': price_text,
                                'description': description_text
                            }
                        )
                    
                    if created:
                        session.products_created += 1
                        log_message(session, 'success', f'Created new product: {title_text}', product_url=link, product_sku=sku_text)
                    else:
                        # Update existing product
                        product.name = title_text
                        product.price = price_text
                        product.description = description_text
                        if not product.link:  # Update link if it was empty
                            product.link = link
                        product.save()
                        session.products_updated += 1
                        log_message(session, 'success', f'Updated product: {title_text}', product_url=link, product_sku=sku_text)
                    
                    session.products_scraped += 1
                    
                except Exception as db_error:
                    session.products_failed += 1
                    # Log outside of any transaction to avoid transaction errors
                    try:
                        log_message(session, 'error', f'Database error for product: {str(db_error)}', 
                                  product_url=link, product_sku=sku_text, exception_details=traceback.format_exc())
                    except:
                        # If logging also fails, just continue
                        print(f"Failed to log database error for {link}: {db_error}")
                
                # Update session progress
                session.last_processed_index = idx
                session.last_processed_url = link
                session.save()
                
                # Random delay to be respectful to the server
                delay = random.randint(2, 6)
                time.sleep(delay)
                
            except SoftTimeLimitExceeded:
                # Handle soft time limit with auto-resume
                log_message(session, 'warning', f'Task soft time limit exceeded at index {idx}. Auto-resuming in 30 seconds...')
                
                # Update session for resumption
                session.last_processed_index = idx
                session.status = 'paused'
                session.save()
                
                # Schedule auto-resume task with a 30-second delay
                scrape_waterdale_collection.apply_async(
                    args=[session_id, idx],
                    countdown=30  # Wait 30 seconds before resuming
                )
                
                log_message(session, 'info', f'Auto-resume task scheduled to continue from index {idx}')
                
                return {
                    'status': 'auto_resuming', 
                    'message': f'Task auto-resuming from index {idx} in 30 seconds',
                    'resume_index': idx
                }
                
            except requests.exceptions.RequestException as req_error:
                session.products_failed += 1
                log_message(session, 'error', f'Request error for {link}: {str(req_error)}', 
                          product_url=link, exception_details=traceback.format_exc())
                continue
                
            except Exception as e:
                session.products_failed += 1
                log_message(session, 'error', f'Error scraping {link}: {str(e)}', 
                          product_url=link, exception_details=traceback.format_exc())
                continue
        
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
        
        return {
            'status': 'completed',
            'total_found': session.total_products_found,
            'scraped': session.products_scraped,
            'created': session.products_created,
            'updated': session.products_updated,
            'failed': session.products_failed
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
