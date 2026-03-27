from .tasks import (scrape_waterdale_collection, scrape_btshalom,
                    scrape_malchutjudaica, scrape_feldart, scrape_menuchapublishers,
                    scrape_israelbookshoppublications, scrape_judaicapress,
                    scrape_hausdecornj,scrape_majesticgiftware, scrape_sephardicwarehouse,
                    scrape_torahjudaica, scrape_meiros, scrape_legacyjudaica, scrape_simchonim,
                    scrape_colourscrafts, scrape_jewisheducationaltoys, scrape_ritelite,
                    scrape_shaijudaica, scrape_gramcoschoolsupplies, scrape_ozvehadar, scrape_craftsandmore,
                    scrape_nermitzvah, scrape_thekoshercook_collection, scrape_alef_to_tav_collection, 
                    scrape_chazakkinder_collection, scrape_kaftorjudaica, scrape_mefoarjudaica,
                    scrape_davidjudaica, scrape_zionjudaica, scrape_ezpekalach, scrape_classictouchdecor, scrape_toys4u,
                    scrape_feldheim)
from .models import Website, ScrapingSession, ScrapingState, ScrapingLog
from django.contrib.auth.models import User
from django.utils import timezone
from celery import current_app
import importlib
import logging

logger = logging.getLogger(__name__)

# ==================== TASK HEALTH UTILITIES ====================

def is_celery_task_alive(task_id):
    """
    Check if a Celery task is actually alive/running.

    Returns:
        True  - Task is actively running (STARTED state) - requires CELERY_TASK_TRACK_STARTED=True
        False - Task is confirmed dead (SUCCESS / FAILURE / REVOKED, or no task_id)
        None  - Unknown / PENDING (could be legitimately queued OR worker died mid-run)
    """
    if not task_id:
        return False
    try:
        result = current_app.AsyncResult(task_id)
        state = result.state
        if state in ('SUCCESS', 'FAILURE', 'REVOKED'):
            return False
        if state == 'STARTED':
            return True
        # PENDING is ambiguous: task could be waiting in queue OR worker died
        return None
    except Exception as e:
        logger.warning(f"Error checking Celery task {task_id} status: {e}")
        return False


def _reset_stuck_session(session, state=None, new_status='failed'):
    """
    Reset a stuck scraping session and its associated ScrapingState.
    Safe to call on sessions that are already in a terminal state.
    """
    try:
        if session.status not in ('completed', 'stopped', 'failed'):
            session.status = new_status
            session.completed_at = timezone.now()
            session.save()
            logger.info(
                f"[Recovery] Reset session #{session.id} ({session.website.name}, "
                f"was={session.status}) → {new_status}"
            )

        # Resolve the ScrapingState if not provided
        if state is None:
            try:
                state = ScrapingState.objects.get(website=session.website)
            except ScrapingState.DoesNotExist:
                return

        if state and (state.is_running or state.current_session_id == session.id):
            state.is_running = False
            state.current_session = None
            state.save()

    except Exception as e:
        logger.error(f"[Recovery] Error resetting session #{session.id}: {e}")


def recover_stuck_sessions():
    """
    Scan all 'running' and 'pending' sessions and recover those whose Celery
    tasks are no longer alive.

    Called on:
      - Celery worker startup (worker_ready signal in tasks.py)
      - Every 5 minutes by the recover_stuck_sessions_task periodic task
      - Manually via the /recover-stuck-scrapers/ endpoint

    Returns:
        int: Number of sessions / states that were recovered / fixed
    """
    recovered = 0
    now = timezone.now()
    # A session stuck in PENDING for longer than this is considered orphaned
    STUCK_PENDING_MINUTES = 15
    # A session stuck in RUNNING with an ambiguous (PENDING) Celery state
    STUCK_RUNNING_MINUTES = 15

    # ── 1. Find all DB-level active sessions ──────────────────────────────
    stuck_sessions = ScrapingSession.objects.filter(
        status__in=['running', 'pending']
    ).select_related('website').order_by('started_at')

    for session in stuck_sessions:
        task_alive = is_celery_task_alive(session.celery_task_id)
        age_minutes = (now - session.started_at).total_seconds() / 60
        should_recover = False
        reason = ''

        if task_alive is False:
            # Confirmed dead: task finished / was revoked / has no ID
            should_recover = True
            reason = 'Celery task confirmed dead (SUCCESS/FAILURE/REVOKED or missing ID)'

        elif task_alive is None:
            # PENDING state - could be queued OR dead worker
            if session.status == 'running' and age_minutes > STUCK_RUNNING_MINUTES:
                should_recover = True
                reason = (
                    f'session marked running but Celery task is PENDING for '
                    f'{age_minutes:.0f} min (> {STUCK_RUNNING_MINUTES} min) — worker likely died'
                )
            elif session.status == 'pending' and age_minutes > STUCK_PENDING_MINUTES:
                should_recover = True
                reason = (
                    f'session stuck in pending for {age_minutes:.0f} min '
                    f'(> {STUCK_PENDING_MINUTES} min threshold)'
                )

        elif not session.celery_task_id and age_minutes > 5:
            # No task ID and session has been around for a while
            should_recover = True
            reason = 'no Celery task ID and session is older than 5 minutes'

        if should_recover:
            logger.info(
                f"[Recovery] Recovering session #{session.id} "
                f"({session.website.name}, status={session.status}): {reason}"
            )
            _reset_stuck_session(session, new_status='failed')
            recovered += 1

    # ── 2. Fix orphaned ScrapingState records ─────────────────────────────
    orphaned_states = ScrapingState.objects.filter(
        is_running=True
    ).select_related('website', 'current_session')

    for state in orphaned_states:
        if not state.current_session:
            state.is_running = False
            state.save()
            recovered += 1
            logger.info(f"[Recovery] Fixed orphaned ScrapingState for {state.website.name} (no current_session)")
        elif state.current_session.status not in ('running', 'pending'):
            state.is_running = False
            state.current_session = None
            state.save()
            recovered += 1
            logger.info(
                f"[Recovery] Fixed orphaned ScrapingState for {state.website.name} "
                f"(session status={state.current_session.status})"
            )

    logger.info(f"[Recovery] Complete — {recovered} session(s)/state(s) recovered")
    return recovered


def force_stop_all_scraping():
    """
    Force-stop ALL scraping sessions across all websites regardless of task state.
    Revokes Celery tasks, marks sessions as stopped, resets all ScrapingState records.

    Returns:
        dict with 'stopped' list, 'errors' list, 'total_stopped' count
    """
    stopped = []
    errors = []

    active_sessions = ScrapingSession.objects.filter(
        status__in=['running', 'pending']
    ).select_related('website')

    for session in active_sessions:
        try:
            if session.celery_task_id:
                try:
                    current_app.control.revoke(session.celery_task_id, terminate=True)
                    logger.info(f"[StopAll] Revoked task {session.celery_task_id} for {session.website.name}")
                except Exception as re:
                    logger.warning(f"[StopAll] Could not revoke task {session.celery_task_id}: {re}")

            session.status = 'stopped'
            session.completed_at = timezone.now()
            session.save()
            stopped.append(f"{session.website.name} (session #{session.id})")
        except Exception as e:
            errors.append(f"{session.website.name}: {str(e)}")

    # Bulk-reset all running states
    updated = ScrapingState.objects.filter(is_running=True).update(is_running=False, current_session=None)
    logger.info(f"[StopAll] Reset {updated} ScrapingState record(s) to idle")

    return {
        'stopped': stopped,
        'errors': errors,
        'total_stopped': len(stopped),
    }

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
    'torahjudaica':scrape_torahjudaica,
    'meiros':scrape_meiros,
    'legacyjudaica':scrape_legacyjudaica,
    'simchonim':scrape_simchonim,
    'colourscrafts':scrape_colourscrafts,
    'jewisheducationaltoys': scrape_jewisheducationaltoys,
    'ritelite': scrape_ritelite,
    'shaijudaica': scrape_shaijudaica,
    'gramcoschoolsupplies': scrape_gramcoschoolsupplies,
    'ozvehadar': scrape_ozvehadar,
    'craftsandmore': scrape_craftsandmore,
    'nermitzvah': scrape_nermitzvah,
    'thekoshercook': scrape_thekoshercook_collection,
    'alef_to_tav': scrape_alef_to_tav_collection,
    'chazakkinder': scrape_chazakkinder_collection,
    'mefoarjudaica': scrape_mefoarjudaica,
    'kaftorjudaica': scrape_kaftorjudaica,
    'davidjudaica': scrape_davidjudaica,
    'zionjudaica': scrape_zionjudaica,
    'ezpekalach': scrape_ezpekalach,
    'classictouchdecor': scrape_classictouchdecor,
    'toys4u': scrape_toys4u,
    'feldheim': scrape_feldheim,
}

def get_scraper_function(function_name):
    """Get scraper function by name"""
    return SCRAPER_FUNCTIONS.get(function_name)

def start_scraping_session(website_id, user=None, resume_from_index=0):
    """
    Start a new scraping session for a website.

    Includes:
    - Duplicate prevention: checks both DB state AND actual Celery task liveness
    - Auto-recovery: dead/stuck sessions for this website are cleaned up automatically
      before attempting to start a new one
    """
    try:
        website = Website.objects.get(id=website_id)

        # ── Duplicate / stuck-session check ───────────────────────────────
        # Look for ANY active (running or pending) sessions for this website in the DB.
        # We intentionally check the DB directly rather than relying solely on
        # ScrapingState.is_running because that flag can be stale after a crash.
        active_sessions = ScrapingSession.objects.filter(
            website=website,
            status__in=['running', 'pending']
        ).order_by('-started_at')

        for active_session in active_sessions:
            task_alive = is_celery_task_alive(active_session.celery_task_id)
            age_minutes = (timezone.now() - active_session.started_at).total_seconds() / 60

            if task_alive is True:
                # Genuinely alive – refuse to start a duplicate
                return {
                    'success': False,
                    'message': f'Scraping is already running for {website.name}',
                    'session_id': active_session.id,
                }

            elif task_alive is False:
                # Confirmed dead – auto-recover and continue
                logger.info(
                    f"[StartSession] Auto-recovering dead session #{active_session.id} "
                    f"for {website.name} before starting new one"
                )
                _reset_stuck_session(active_session)

            else:
                # PENDING (ambiguous): decide based on age
                if age_minutes < 15:
                    # Recently queued – treat as still active to avoid duplicates
                    return {
                        'success': False,
                        'message': (
                            f'A scraping task for {website.name} is already queued or starting '
                            f'(session #{active_session.id}, {age_minutes:.0f} min ago). '
                            f'Wait a moment or use the recovery option if it appears stuck.'
                        ),
                        'session_id': active_session.id,
                    }
                else:
                    # Old PENDING – likely a dead-worker orphan, recover it
                    logger.info(
                        f"[StartSession] Auto-recovering stale PENDING session #{active_session.id} "
                        f"for {website.name} ({age_minutes:.0f} min old)"
                    )
                    _reset_stuck_session(active_session)

        # ── Ensure ScrapingState is clean before starting ─────────────────
        state, _ = ScrapingState.objects.get_or_create(website=website)
        if state.is_running:
            # No active sessions remain after recovery above – reset the flag
            state.is_running = False
            state.current_session = None
            state.save()

        # ── Create new session ────────────────────────────────────────────
        session = ScrapingSession.objects.create(
            website=website,
            status='pending',
            started_by=user,
            last_processed_index=resume_from_index,
        )

        scraper_function = get_scraper_function(website.scraper_function)
        if not scraper_function:
            session.status = 'failed'
            session.save()
            return {
                'success': False,
                'message': f'No scraper function found for {website.scraper_function}',
            }

        task = scraper_function.delay(session.id, resume_from_index)
        session.celery_task_id = task.id
        session.save()

        logger.info(f"[StartSession] Started session #{session.id} for {website.name}, task={task.id}")
        return {
            'success': True,
            'message': f'Scraping started for {website.name}',
            'session_id': session.id,
            'task_id': task.id,
        }

    except Website.DoesNotExist:
        return {'success': False, 'message': 'Website not found'}
    except Exception as e:
        logger.exception(f"[StartSession] Unexpected error for website_id={website_id}")
        return {'success': False, 'message': f'Error starting scraping: {str(e)}'}

def stop_scraping_session(website_id):
    """
    Stop the current scraping session for a website.

    Improvements over the old version:
    - Stops ALL active sessions for the website (not just the one in ScrapingState),
      so orphaned duplicates are also cleaned up.
    - Revoke errors are silently swallowed (task may already be dead).
    - ScrapingState is reset regardless, so the UI always reflects the correct state.
    """
    try:
        website = Website.objects.get(id=website_id)

        # Find ALL active sessions for this website (handles duplicates / orphans too)
        active_sessions = ScrapingSession.objects.filter(
            website=website,
            status__in=['running', 'pending']
        )

        stopped_ids = []
        for session in active_sessions:
            if session.celery_task_id:
                try:
                    current_app.control.revoke(session.celery_task_id, terminate=True)
                    logger.info(f"[StopSession] Revoked task {session.celery_task_id} for {website.name}")
                except Exception as revoke_err:
                    logger.warning(
                        f"[StopSession] Could not revoke task {session.celery_task_id} "
                        f"(may already be dead): {revoke_err}"
                    )

            session.status = 'stopped'
            session.completed_at = timezone.now()
            session.save()
            stopped_ids.append(session.id)

        # Always reset ScrapingState regardless of whether sessions were found
        state, _ = ScrapingState.objects.get_or_create(website=website)
        state.is_running = False
        state.current_session = None
        state.save()

        if stopped_ids:
            return {
                'success': True,
                'message': f'Scraping stopped for {website.name}',
                'session_ids': stopped_ids,
            }
        else:
            return {
                'success': True,
                'message': (
                    f'No active sessions found for {website.name} — '
                    'state has been reset to idle'
                ),
                'session_ids': [],
            }

    except Website.DoesNotExist:
        return {'success': False, 'message': 'Website not found'}
    except Exception as e:
        logger.exception(f"[StopSession] Unexpected error for website_id={website_id}")
        return {'success': False, 'message': f'Error stopping scraping: {str(e)}'}


def resume_scraping_session(session_id, user=None):
    """
    Resume a paused / failed / stopped scraping session.

    Includes alive-check: if the website already has a genuinely running task,
    the resume is blocked. If the running state is stale (dead task), it is
    auto-recovered before the resume proceeds.
    """
    try:
        session = ScrapingSession.objects.get(id=session_id)

        if session.status not in ['paused', 'failed', 'stopped']:
            return {'success': False, 'message': 'Session cannot be resumed (wrong status)'}

        website = session.website

        # Check for any genuinely alive sessions for this website
        active_sessions = ScrapingSession.objects.filter(
            website=website,
            status__in=['running', 'pending']
        )

        for active in active_sessions:
            task_alive = is_celery_task_alive(active.celery_task_id)
            age_minutes = (timezone.now() - active.started_at).total_seconds() / 60

            if task_alive is True:
                return {
                    'success': False,
                    'message': f'Website {website.name} is already running (session #{active.id})',
                }
            elif task_alive is False or (task_alive is None and age_minutes >= 15):
                # Dead or stale – recover it so resume can proceed
                logger.info(
                    f"[ResumeSession] Auto-recovering {'dead' if task_alive is False else 'stale'} "
                    f"session #{active.id} for {website.name} before resume"
                )
                _reset_stuck_session(active)
            else:
                # PENDING and recent – block the resume
                return {
                    'success': False,
                    'message': (
                        f'A task for {website.name} appears to be starting up '
                        f'(session #{active.id}, {age_minutes:.0f} min ago). '
                        'Wait a moment or use the recovery option if it appears stuck.'
                    ),
                }

        # Ensure state is clean
        state, _ = ScrapingState.objects.get_or_create(website=website)
        if state.is_running:
            state.is_running = False
            state.current_session = None
            state.save()

        # Create new session from where the old one left off
        new_session = ScrapingSession.objects.create(
            website=website,
            status='pending',
            started_by=user,
            last_processed_index=session.last_processed_index,
            resume_data={'resumed_from_session': session.id},
        )

        scraper_function = get_scraper_function(website.scraper_function)
        if not scraper_function:
            new_session.status = 'failed'
            new_session.save()
            return {
                'success': False,
                'message': f'No scraper function found for {website.scraper_function}',
            }

        task = scraper_function.delay(new_session.id, session.last_processed_index)
        new_session.celery_task_id = task.id
        new_session.save()

        logger.info(
            f"[ResumeSession] Resumed as session #{new_session.id} for {website.name}, "
            f"from index={session.last_processed_index}, task={task.id}"
        )
        return {
            'success': True,
            'message': f'Scraping resumed for {website.name}',
            'session_id': new_session.id,
            'task_id': task.id,
            'resumed_from_index': session.last_processed_index,
        }

    except ScrapingSession.DoesNotExist:
        return {'success': False, 'message': 'Session not found'}
    except Exception as e:
        logger.exception(f"[ResumeSession] Unexpected error for session_id={session_id}")
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
        },
        {
            'name': 'meiros',
            'url': 'https://meiros.com',
            'is_active': True,
            'scraper_function': 'meiros'
        },
        {
            'name': 'gramcoschoolsupplies',
            'url': 'https://www.gramcoschoolsupplies.com',
            'is_active': True,
            'scraper_function': 'gramcoschoolsupplies'
        },
        {
            'name': 'legacyjudaica',
            'url': 'https://legacyjudaica.com',
            'is_active': True,
            'scraper_function': 'legacyjudaica'
        },
        {
            'name': 'simchonim',
            'url': 'https://simchonim.com',
            'is_active': True,
            'scraper_function': 'simchonim'
        },
        {
            'name': 'colourscrafts',
            'url': 'https://colourscrafts.com',
            'is_active': True,
            'scraper_function': 'colourscrafts'
        },
        {
            'name': 'jewisheducationaltoys',
            'url': 'https://jewisheducationaltoys.com',
            'is_active': True,
            'scraper_function': 'jewisheducationaltoys'
        },
        {
            'name': 'ritelite',
            'url': 'https://ritelite.com',
            'is_active': True,
            'scraper_function': 'ritelite'
        },
        {
            'name': 'shaijudaica',
            'url': 'https://www.shaijudaica.co.il',
            'is_active': True,
            'scraper_function': 'shaijudaica'
        },
        {
            'name': 'ozvehadar',
            'url': 'https://ozvehadar.us',
            'is_active': True,
            'scraper_function': 'ozvehadar'
        },
        {
            'name': 'craftsandmore',
            'url': 'https://craftsandmore.com',
            'is_active': True,
            'scraper_function': 'craftsandmore'
        },
        {
            'name': 'nermitzvah',
            'url': 'https://www.nermitzvah.com',
            'is_active': True,
            'scraper_function': 'nermitzvah'
        },
        {
            'name': 'thekoshercook',
            'url': 'https://www.thekoshercook.com',
            'is_active': True,
            'scraper_function': 'thekoshercook'
        },
        {
            'name': 'alef-to-tav',
            'url': 'https://alef-to-tav.com',
            'is_active': True,
            'scraper_function': 'alef_to_tav'
        },
        {
            'name': 'chazakkinder',
            'url': 'https://www.chazakkinder.com',
            'is_active': True,
            'scraper_function': 'chazakkinder'
        },
        {
            'name': 'mefoarjudaica',
            'url': 'https://mefoarjudaica.com',
            'is_active': True,
            'scraper_function': 'mefoarjudaica'
        },
        {
            'name': 'kaftorjudaica',
            'url': 'https://www.kaftorjudaica.com',
            'is_active': True,
            'scraper_function': 'kaftorjudaica'
        },
        {
            'name': 'www.davidjudaica.shop',
            'url': 'https://www.davidjudaica.shop',
            'is_active': True,
            'scraper_function': 'davidjudaica'
        },
        {
            'name': 'zionjudaica.com',
            'url': 'https://zionjudaica.com',
            'is_active': True,
            'scraper_function': 'zionjudaica'
        },
        {
            'name': 'ezpekalach.com',
            'url': 'https://ezpekalach.com',
            'is_active': True,
            'scraper_function': 'ezpekalach'
        },
        {
            'name': 'classictouchdecor',
            'url': 'https://www.classictouchdecor.com',
            'is_active': True,
            'scraper_function': 'classictouchdecor'
        },
        {
            'name': 'toys4u',
            'url': 'https://www.toys4u.com',
            'is_active': True,
            'scraper_function': 'toys4u'
        },
        {
            'name': 'feldheim',
            'url': 'https://feldheim.com',
            'is_active': True,
            'scraper_function': 'feldheim'
        },
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
