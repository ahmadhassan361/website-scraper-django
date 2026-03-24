# your_project/celery.py

import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('core')

# Load settings from Django settings file using CELERY_ namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in your apps
app.autodiscover_tasks()

from kombu import Queue, Exchange

# ── Queues ────────────────────────────────────────────────────────────────────
# Two completely independent queues so that scraping and sync (import/export)
# tasks NEVER block each other regardless of worker concurrency.
#
#   scraping  – all scrape_* tasks          → start with: -Q scraping --concurrency 2
#   sync      – import / export / recovery  → start with: -Q sync,default --concurrency 4
#   default   – celery beat / admin tasks   → included in the sync worker above
#
app.conf.task_queues = (
    Queue('default',  Exchange('default'),  routing_key='default'),
    Queue('scraping', Exchange('scraping'), routing_key='scraping'),
    Queue('sync',     Exchange('sync'),     routing_key='sync'),
)
app.conf.task_default_queue = 'default'
app.conf.task_default_exchange = 'default'
app.conf.task_default_routing_key = 'default'

# ── Task routing ──────────────────────────────────────────────────────────────
# All scrape_* tasks → 'scraping' queue
# All import/export/sync tasks → 'sync' queue
# Recovery + beat tasks stay on 'default'
app.conf.task_routes = {
    # Scraping tasks  ──────────────────────────────────────────────────────────
    'scraper.tasks.scrape_waterdale_collection':         {'queue': 'scraping'},
    'scraper.tasks.scrape_btshalom':                     {'queue': 'scraping'},
    'scraper.tasks.scrape_malchutjudaica':               {'queue': 'scraping'},
    'scraper.tasks.scrape_feldart':                      {'queue': 'scraping'},
    'scraper.tasks.scrape_menuchapublishers':             {'queue': 'scraping'},
    'scraper.tasks.scrape_israelbookshoppublications':    {'queue': 'scraping'},
    'scraper.tasks.scrape_judaicapress':                 {'queue': 'scraping'},
    'scraper.tasks.scrape_hausdecornj':                  {'queue': 'scraping'},
    'scraper.tasks.scrape_majesticgiftware':             {'queue': 'scraping'},
    'scraper.tasks.scrape_sephardicwarehouse':           {'queue': 'scraping'},
    'scraper.tasks.scrape_torahjudaica':                 {'queue': 'scraping'},
    'scraper.tasks.scrape_meiros':                       {'queue': 'scraping'},
    'scraper.tasks.scrape_legacyjudaica':                {'queue': 'scraping'},
    'scraper.tasks.scrape_simchonim':                    {'queue': 'scraping'},
    'scraper.tasks.scrape_colourscrafts':                {'queue': 'scraping'},
    'scraper.tasks.scrape_jewisheducationaltoys':        {'queue': 'scraping'},
    'scraper.tasks.scrape_ritelite':                     {'queue': 'scraping'},
    'scraper.tasks.scrape_shaijudaica':                  {'queue': 'scraping'},
    'scraper.tasks.scrape_gramcoschoolsupplies':         {'queue': 'scraping'},
    'scraper.tasks.scrape_ozvehadar':                    {'queue': 'scraping'},
    'scraper.tasks.scrape_craftsandmore':                {'queue': 'scraping'},
    'scraper.tasks.scrape_nermitzvah':                   {'queue': 'scraping'},
    'scraper.tasks.scrape_thekoshercook_collection':     {'queue': 'scraping'},
    'scraper.tasks.scrape_alef_to_tav_collection':       {'queue': 'scraping'},
    'scraper.tasks.scrape_chazakkinder_collection':      {'queue': 'scraping'},
    'scraper.tasks.scrape_kaftorjudaica':                {'queue': 'scraping'},
    'scraper.tasks.scrape_mefoarjudaica':                {'queue': 'scraping'},
    'scraper.tasks.scrape_davidjudaica':                 {'queue': 'scraping'},
    'scraper.tasks.scrape_zionjudaica':                  {'queue': 'scraping'},
    'scraper.tasks.scrape_ezpekalach':                   {'queue': 'scraping'},
    'scraper.tasks.scrape_classictouchdecor':            {'queue': 'scraping'},

    # Sync / import / export tasks  ────────────────────────────────────────────
    'scraper.tasks.import_website_products_task':        {'queue': 'sync'},
    'scraper.tasks.export_products_to_website_task':     {'queue': 'sync'},
    'scraper.tasks.export_products_to_google_sheet':     {'queue': 'sync'},

    # Dashboard export task (defined in dashboard/tasks.py if it exists)
    'dashboard.tasks.export_products_task':              {'queue': 'sync'},

    # Recovery  ────────────────────────────────────────────────────────────────
    'scraper.tasks.recover_stuck_sessions_task':         {'queue': 'default'},
}

# ── Celery Beat: periodic task schedule ──────────────────────────────────────
app.conf.beat_schedule = {
    'recover-stuck-scraping-sessions': {
        'task': 'scraper.tasks.recover_stuck_sessions_task',
        'schedule': 300.0,   # every 5 minutes
        'options': {'queue': 'default'},
    },
}
app.conf.timezone = 'UTC'

# Enable STARTED state so we can distinguish "actively running" from "queued"
app.conf.task_track_started = True

# Keep results long enough for stuck-session detection (24 hours)
app.conf.result_expires = 86400


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
