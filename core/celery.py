# your_project/celery.py

import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('core')

# Load settings from Django settings file using CELERY_ namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in your apps
app.autodiscover_tasks()

# ── Celery Beat: periodic task schedule ──────────────────────────────────────
app.conf.beat_schedule = {
    # Scan for stuck scraping sessions every 5 minutes
    'recover-stuck-scraping-sessions': {
        'task': 'scraper.tasks.recover_stuck_sessions_task',
        'schedule': 300.0,   # every 5 minutes
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
