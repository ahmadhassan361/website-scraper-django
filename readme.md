# Django Website Scraper Management System

A comprehensive Django-based web scraper project with advanced features including logging, state management, resume functionality, and real-time monitoring.

## 🚀 Features

### Core Functionality
- **Multi-Website Support**: Manage scraping for multiple websites from a single dashboard
- **Advanced Logging**: Detailed logs for every scraping action with different log levels
- **State Management**: Track scraping sessions with complete statistics
- **Resume Capability**: Resume interrupted or failed scraping sessions from where they left off
- **Real-time Monitoring**: Live progress tracking with auto-refreshing dashboard
- **Start/Stop Control**: Start, stop, pause, and resume scraping operations
- **Product Management**: Automatic create/update logic for existing products

### Technical Features
- **Celery Background Tasks**: Asynchronous scraping with proper task management
- **Redis Integration**: Fast message broker and result backend
- **Database Models**: Comprehensive data models for websites, sessions, logs, and products
- **Admin Interface**: Full Django admin integration for all models
- **Bootstrap UI**: Modern, responsive web interface
- **Error Handling**: Robust error handling with detailed exception logging
- **Time Limits**: Configurable soft and hard time limits for tasks

## 📦 Installation

### Prerequisites
- Python 3.8+
- Redis server
- Virtual environment (recommended)

### Setup Steps

1. **Clone and Setup Environment**:
   ```bash
   git clone <your-repo>
   cd website-scraper-django
   python -m venv .env
   source .env/bin/activate  # On Windows: .env\Scripts\activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install django celery redis beautifulsoup4 requests lxml django-celery-beat django-celery-results
   ```

3. **Database Setup**:
   ```bash
   python manage.py migrate
   ```

4. **Initialize System**:
   ```bash
   python manage.py init_scraper --create-superuser
   ```

5. **Start Services**:
   
   **Terminal 1 - Redis Server**:
   ```bash
   redis-server
   ```
   
   **Terminal 2 - Celery Worker**:
   ```bash
   celery -A core worker --loglevel=info
   ```
   
   **Terminal 3 - Django Server**:
   ```bash
   python manage.py runserver
   ```

6. **Access the Dashboard**:
   Visit `http://127.0.0.1:8000` and login with your credentials

## 🎯 Usage

### Dashboard Overview
The main dashboard provides:
- **Website Status Cards**: Real-time status for each configured website
- **Session Statistics**: Live statistics for running sessions
- **Recent Sessions Table**: History of all scraping sessions
- **Control Buttons**: Start, stop, resume scraping operations

### Starting a Scraping Session
1. Navigate to the dashboard
2. Find the website card you want to scrape
3. Click "Start Scraping" button
4. Monitor progress in real-time

### Monitoring Sessions
- **Live Updates**: Dashboard auto-refreshes every 30 seconds for running sessions
- **Detailed View**: Click "View Details" to see comprehensive session information
- **Log Filtering**: Filter logs by level (info, success, warning, error)
- **Progress Tracking**: Visual progress bars and statistics

### Managing Sessions
- **Stop**: Click "Stop Scraping" to halt a running session
- **Resume**: Use "Resume" button for paused, failed, or stopped sessions
- **View Logs**: Access detailed logs with exception details

## 🏗️ Architecture

### Models
- **Website**: Configuration for websites to scrape
- **Product**: Scraped product data with create/update logic
- **ScrapingSession**: Session tracking with statistics and state
- **ScrapingLog**: Detailed logging for each action
- **ScrapingState**: Current state management for websites

### Tasks
- **scrape_waterdale_collection**: Enhanced Celery task with full logging and state management
- **Timeout Handling**: Automatic pausing on soft time limits
- **Resume Logic**: Smart resume from last processed index

### Utils
- **start_scraping_session**: Initialize new scraping sessions
- **stop_scraping_session**: Stop running sessions
- **resume_scraping_session**: Resume interrupted sessions
- **get_website_status**: Real-time status information
- **get_session_logs**: Retrieve session logs

## 🔧 Configuration

### Adding New Websites
1. Add website to `scraper/utils.py` in `SCRAPER_FUNCTIONS` dictionary
2. Create scraper script in `scraper/scraper_scripts/`
3. Register website using `initialize_websites()` function

### Environment Variables
Configure in `core/settings.py`:
- `CELERY_BROKER_URL`: Redis URL for Celery broker
- `CELERY_RESULT_BACKEND`: Redis URL for results
- `CELERY_TASK_SERIALIZER`: Task serialization format

### Time Limits
Adjust in task decorators:
```python
@shared_task(bind=True, soft_time_limit=3600, time_limit=3660)
```

## 📊 Monitoring & Logs

### Log Levels
- **Info**: General information and progress updates
- **Success**: Successful product creation/updates
- **Warning**: Non-critical issues (timeouts, pausing)
- **Error**: Failed requests, database errors, exceptions

### Session Statistics
- **Total Products Found**: Number of URLs discovered
- **Products Scraped**: Successfully processed products
- **Products Created**: New products added to database
- **Products Updated**: Existing products updated
- **Products Failed**: Failed processing attempts

### Resume Functionality
- **Last Processed Index**: Tracks progress for resume
- **Resume Data**: Additional context for resuming sessions
- **Smart Resume**: Creates new session linked to original

## 🛠️ Development

### Adding New Scrapers
1. Create scraper script in `scraper/scraper_scripts/`
2. Define extraction logic
3. Add to `SCRAPER_FUNCTIONS` in `utils.py`
4. Register website in database

### Extending Models
- Use Django migrations for model changes
- Update admin interfaces accordingly
- Consider data migration scripts

### Testing
```bash
python manage.py test
```

## 🚨 Troubleshooting

### Common Issues
1. **Redis Connection**: Ensure Redis server is running
2. **Celery Workers**: Check worker logs for errors
3. **Database Locks**: Use transactions for concurrent operations
4. **Memory Usage**: Monitor for large datasets

### Debug Mode
Enable detailed logging:
```bash
celery -A core worker --loglevel=debug
celery -A core worker --concurrency=8 --loglevel=info
```

## 📝 API Endpoints

- `GET /`: Dashboard home
- `POST /start-scraping/<website_id>/`: Start scraping session
- `POST /stop-scraping/<website_id>/`: Stop scraping session
- `POST /resume-scraping/<session_id>/`: Resume session
- `GET /website-status/<website_id>/`: Get website status (JSON)
- `GET /session-details/<session_id>/`: Session details page
- `GET /session-logs/<session_id>/`: Get session logs (JSON)

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Submit pull request

## 📄 License

This project is licensed under the MIT License.

## 🔗 Dependencies

- **Django**: Web framework
- **Celery**: Distributed task queue
- **Redis**: Message broker and result backend
- **Beautiful Soup**: HTML parsing
- **Requests**: HTTP library
- **Bootstrap**: Frontend framework

---

For more information or support, please refer to the documentation or create an issue.
