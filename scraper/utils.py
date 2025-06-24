from .tasks import (scrape_waterdale_collection, scrape_btshalom,
                    scrape_malchutjudaica, scrape_feldart, scrape_menuchapublishers,
                    scrape_israelbookshoppublications, scrape_judaicapress,
                    scrape_hausdecornj,scrape_majesticgiftware, scrape_sephardicwarehouse,
                    scrape_torahjudaica)
from .models import Website, ScrapingSession, ScrapingState, ScrapingLog
from django.contrib.auth.models import User
from django.utils import timezone
from celery import current_app
import importlib

# Website scraper function mapping
SCRAPER_FUNCTIONS = {
    'waterdalecollection': scrape_waterdale_collection,
    'btshalom': scrape_btshalom,
    'malchutjudaica': scrape_malchutjudaica,
    'feldart': scrape_feldart,
    'menuchapublishers': scrape_menuchapublishers,
    'israelbookshoppublications':scrape_israelbookshoppublications,
    'judaicapress':scrape_judaicapress,
    'hausdecornj':scrape_hausdecornj,
    'majesticgiftware':scrape_majesticgiftware,
    'sephardicwarehouse':scrape_sephardicwarehouse,
    'torahjudaica':scrape_torahjudaica
}

def get_scraper_function(function_name):
    """Get scraper function by name"""
    return SCRAPER_FUNCTIONS.get(function_name)

def start_scraping_session(website_id, user=None, resume_from_index=0):
    """
    Start a new scraping session for a website
    """
    try:
        website = Website.objects.get(id=website_id)
        
        # Check if website is already running
        state, created = ScrapingState.objects.get_or_create(website=website)
        if state.is_running:
            return {
                'success': False, 
                'message': f'Scraping is already running for {website.name}',
                'session_id': state.current_session.id if state.current_session else None
            }
        
        # Create new scraping session
        session = ScrapingSession.objects.create(
            website=website,
            status='pending',
            started_by=user,
            last_processed_index=resume_from_index
        )
        
        # Get the scraper function
        scraper_function = get_scraper_function(website.scraper_function)
        if not scraper_function:
            session.status = 'failed'
            session.save()
            return {
                'success': False, 
                'message': f'No scraper function found for {website.scraper_function}'
            }
        
        # Start the Celery task
        task = scraper_function.delay(session.id, resume_from_index)
        session.celery_task_id = task.id
        session.save()
        
        return {
            'success': True, 
            'message': f'Scraping started for {website.name}',
            'session_id': session.id,
            'task_id': task.id
        }
        
    except Website.DoesNotExist:
        return {'success': False, 'message': 'Website not found'}
    except Exception as e:
        return {'success': False, 'message': f'Error starting scraping: {str(e)}'}

def stop_scraping_session(website_id):
    """
    Stop the current scraping session for a website
    """
    try:
        website = Website.objects.get(id=website_id)
        state = ScrapingState.objects.get(website=website)
        
        if not state.is_running or not state.current_session:
            return {'success': False, 'message': 'No active scraping session found'}
        
        session = state.current_session
        
        # Revoke the Celery task
        if session.celery_task_id:
            current_app.control.revoke(session.celery_task_id, terminate=True)
        
        # Update session status
        session.status = 'stopped'
        session.completed_at = timezone.now()
        session.save()
        
        # Update state
        state.is_running = False
        state.current_session = None
        state.save()
        
        return {
            'success': True, 
            'message': f'Scraping stopped for {website.name}',
            'session_id': session.id
        }
        
    except Website.DoesNotExist:
        return {'success': False, 'message': 'Website not found'}
    except ScrapingState.DoesNotExist:
        return {'success': False, 'message': 'No scraping state found'}
    except Exception as e:
        return {'success': False, 'message': f'Error stopping scraping: {str(e)}'}

def resume_scraping_session(session_id, user=None):
    """
    Resume a paused or failed scraping session
    """
    try:
        session = ScrapingSession.objects.get(id=session_id)
        
        if session.status not in ['paused', 'failed', 'stopped']:
            return {'success': False, 'message': 'Session cannot be resumed'}
        
        # Check if website is currently running
        state = ScrapingState.objects.get(website=session.website)
        if state.is_running:
            return {'success': False, 'message': 'Website is already running'}
        
        # Create new session based on the old one (to maintain history)
        new_session = ScrapingSession.objects.create(
            website=session.website,
            status='pending',
            started_by=user,
            last_processed_index=session.last_processed_index,
            resume_data={'resumed_from_session': session.id}
        )
        
        # Start the task from where we left off
        scraper_function = get_scraper_function(session.website.scraper_function)
        task = scraper_function.delay(new_session.id, session.last_processed_index)
        new_session.celery_task_id = task.id
        new_session.save()
        
        return {
            'success': True, 
            'message': f'Scraping resumed for {session.website.name}',
            'session_id': new_session.id,
            'task_id': task.id,
            'resumed_from_index': session.last_processed_index
        }
        
    except ScrapingSession.DoesNotExist:
        return {'success': False, 'message': 'Session not found'}
    except Exception as e:
        return {'success': False, 'message': f'Error resuming scraping: {str(e)}'}

def get_website_status(website_id):
    """
    Get the current status of a website's scraping operation
    """
    try:
        website = Website.objects.get(id=website_id)
        state, created = ScrapingState.objects.get_or_create(website=website)
        
        result = {
            'website_id': website.id,
            'website_name': website.name,
            'website_link': website.url,
            'is_running': state.is_running,
            'last_run': state.last_run,
            'current_session': None
        }
        
        if state.current_session:
            session = state.current_session
            result['current_session'] = {
                'id': session.id,
                'status': session.status,
                'started_at': session.started_at,
                'total_products_found': session.total_products_found,
                'products_scraped': session.products_scraped,
                'products_created': session.products_created,
                'products_updated': session.products_updated,
                'products_failed': session.products_failed,
                'last_processed_index': session.last_processed_index,
            }
            
            # Get task status if available
            if session.celery_task_id:
                try:
                    task_result = current_app.AsyncResult(session.celery_task_id)
                    result['current_session']['task_status'] = task_result.status
                    result['current_session']['task_info'] = task_result.info
                except:
                    pass
        
        return result
    except Website.DoesNotExist:
        return None

def get_session_logs(session_id, limit=100):
    """
    Get logs for a specific scraping session
    """
    try:
        session = ScrapingSession.objects.get(id=session_id)
        logs = ScrapingLog.objects.filter(session=session).order_by('-timestamp')[:limit]
        
        return {
            'session_id': session_id,
            'logs': [
                {
                    'level': log.level,
                    'message': log.message,
                    'timestamp': log.timestamp,
                    'product_url': log.product_url,
                    'product_sku': log.product_sku,
                    'exception_details': log.exception_details
                } for log in logs
            ]
        }
    except ScrapingSession.DoesNotExist:
        return {'error': 'Session not found'}

def initialize_websites():
    """
    Initialize default websites in the database
    """
    websites_data = [
        {
            'name': 'waterdalecollection',
            'url': 'https://waterdalecollection.com',
            'is_active': True,
            'scraper_function': 'waterdalecollection'
        },
        {
            'name': 'btshalom',
            'url': 'https://btshalom.com',
            'is_active': True,
            'scraper_function': 'btshalom'
        },
        {
            'name': 'malchutjudaica',
            'url': 'https://malchutjudaica.com',
            'is_active': True,
            'scraper_function': 'malchutjudaica'
        },
        {
            'name': 'feldart',
            'url': 'https://feldart.com',
            'is_active': True,
            'scraper_function': 'feldart'
        },
        {
            'name': 'menuchapublishers',
            'url': 'https://menuchapublishers.com',
            'is_active': True,
            'scraper_function': 'menuchapublishers'
        },
        {
            'name': 'israelbookshoppublications',
            'url': 'https://israelbookshoppublications.com',
            'is_active': True,
            'scraper_function': 'israelbookshoppublications'
        },
        {
            'name': 'judaicapress',
            'url': 'https://judaicapress.com',
            'is_active': True,
            'scraper_function': 'judaicapress'
        },
        {
            'name': 'hausdecornj',
            'url': 'https://hausdecornj.com',
            'is_active': True,
            'scraper_function': 'hausdecornj'
        },
        {
            'name': 'majesticgiftware',
            'url': 'https://www.majesticgiftware.com',
            'is_active': True,
            'scraper_function': 'majesticgiftware'
        },
        {
            'name': 'sephardicwarehouse',
            'url': 'https://www.sephardicwarehouse.com',
            'is_active': True,
            'scraper_function': 'sephardicwarehouse'
        },
        {
            'name': 'torahjudaica',
            'url': 'https://www.torahjudaica.com',
            'is_active': True,
            'scraper_function': 'torahjudaica'
        }
    ]
    
    for website_data in websites_data:
        website, created = Website.objects.get_or_create(
            name=website_data['name'],
            defaults=website_data
        )
        if created:
            print(f"Created website: {website.name}")
        else:
            print(f"Website already exists: {website.name}")
    
    return f"Initialized {len(websites_data)} websites"
