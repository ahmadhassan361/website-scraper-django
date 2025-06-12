from django.core.management.base import BaseCommand
from scraper.utils import initialize_websites
from scraper.models import Website
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Initialize the scraper system with default websites and data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-superuser',
            action='store_true',
            help='Create a superuser if none exists',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Initializing scraper system...'))
        
        # Initialize websites
        result = initialize_websites()
        self.stdout.write(self.style.SUCCESS(result))
        
        # Show current websites
        websites = Website.objects.all()
        self.stdout.write(f"\nConfigured websites:")
        for website in websites:
            self.stdout.write(f"  - {website.name} ({website.url}) - {'Active' if website.is_active else 'Inactive'}")
        
        # Create superuser if requested and none exists
        if options['create_superuser']:
            if not User.objects.filter(is_superuser=True).exists():
                self.stdout.write("\nCreating superuser...")
                User.objects.create_superuser(
                    username='admin',
                    email='admin@example.com',
                    password='admin123'
                )
                self.stdout.write(self.style.SUCCESS('Superuser created: admin/admin123'))
            else:
                self.stdout.write(self.style.WARNING('Superuser already exists'))
        
        self.stdout.write(self.style.SUCCESS('\nScraper system initialized successfully!'))
        self.stdout.write('\nNext steps:')
        self.stdout.write('1. Start Redis: redis-server')
        self.stdout.write('2. Start Celery worker: celery -A core worker --loglevel=info')
        self.stdout.write('3. Start Django server: python manage.py runserver')
        self.stdout.write('4. Visit http://127.0.0.1:8000 to access the dashboard')
