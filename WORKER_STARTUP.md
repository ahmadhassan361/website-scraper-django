# Celery Worker Startup Guide

## Why two workers?

Scraping tasks and sync (import / export) tasks now run in **completely separate queues**
so they can never block each other, even when 2 scraping jobs are occupying all of a
worker's process slots.

| Queue      | Tasks routed to it                                      | Recommended concurrency |
|------------|--------------------------------------------------------|------------------------|
| `scraping` | All `scrape_*` tasks                                   | 2 (max concurrent scrapers) |
| `sync`     | `import_website_products_task`, `export_*` tasks       | 4 (fast, mostly I/O) |
| `default`  | `recover_stuck_sessions_task`, Beat scheduler          | 2 |

---

## Server setup (systemd — Ubuntu)

You currently have one service file. You need **three** total.  
Run all commands as root / with `sudo`.

---

### Step 1 — Replace your existing celery.service (scraping worker)

Edit `/etc/systemd/system/celery.service`:

```ini
[Unit]
Description=Celery Scraping Worker
After=network.target redis.service

[Service]
Type=simple
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/website-scraper-django
Environment="PATH=/home/ubuntu/venv/bin"
ExecStart=/home/ubuntu/venv/bin/celery -A core worker \
    --queues scraping \
    --concurrency 2 \
    --hostname scraping@%%h \
    --loglevel info
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

### Step 2 — Create the sync worker service

Create `/etc/systemd/system/celery-sync.service`:

```ini
[Unit]
Description=Celery Sync Worker (import / export / recovery)
After=network.target redis.service

[Service]
Type=simple
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/website-scraper-django
Environment="PATH=/home/ubuntu/venv/bin"
ExecStart=/home/ubuntu/venv/bin/celery -A core worker \
    --queues sync,default \
    --concurrency 4 \
    --hostname sync@%%h \
    --loglevel info
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

### Step 3 — Create the Celery Beat service (periodic recovery every 5 min)

Create `/etc/systemd/system/celery-beat.service`:

```ini
[Unit]
Description=Celery Beat Scheduler
After=network.target redis.service

[Service]
Type=simple
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/website-scraper-django
Environment="PATH=/home/ubuntu/venv/bin"
ExecStart=/home/ubuntu/venv/bin/celery -A core beat --loglevel info
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

### Step 4 — Enable and start all three services

```bash
# Reload systemd so it picks up the new files
sudo systemctl daemon-reload

# Enable all three to start on boot
sudo systemctl enable celery celery-sync celery-beat

# Restart the scraping worker (now targets the scraping queue)
sudo systemctl restart celery

# Start the new sync worker
sudo systemctl start celery-sync

# Start beat
sudo systemctl start celery-beat

# Verify all three are running
sudo systemctl status celery celery-sync celery-beat
```

---

### Quick reference — daily operations

| Action | Command |
|--------|---------|
| Restart all after a deploy | `sudo systemctl restart celery celery-sync celery-beat` |
| Check logs (scraping worker) | `sudo journalctl -u celery -f` |
| Check logs (sync worker) | `sudo journalctl -u celery-sync -f` |
| Check logs (beat) | `sudo journalctl -u celery-beat -f` |
| Stop everything | `sudo systemctl stop celery celery-sync celery-beat` |

---

## What happens on restart / crash?

When **either** Celery worker starts it fires the `worker_ready` signal which immediately
calls `recover_stuck_sessions()`. This scans every `running` / `pending` DB session,
checks whether its Celery task is actually alive, and marks dead ones as `failed` — so
the UI no longer shows them as stuck and you can start fresh sessions right away.

The `recover_stuck_sessions_task` Beat job also runs automatically every **5 minutes** as a
safety net without any manual intervention.
