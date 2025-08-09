#!/bin/bash

echo "Setting up Google OAuth2 for Django Website Scraper"
echo "================================================="

# Install the new requirement
echo "Installing google-auth-oauthlib..."
pip install google-auth-oauthlib==1.2.0

# Create database migrations
echo "Creating database migrations..."
python manage.py makemigrations scraper

# Apply migrations
echo "Applying migrations..."
python manage.py migrate

echo ""
echo "Setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Create OAuth2 credentials in Google Cloud Console"
echo "2. Download the credentials JSON file as 'oauth2_credentials.json'"
echo "3. Place it in the 'credentials/' directory"
echo "4. Run your Django server: python manage.py runserver"
echo "5. Visit /scraper/google/setup/ for detailed setup instructions"
echo "6. Authorize the application by visiting /scraper/google/authorize/"
echo ""
echo "The system will now use your personal Google Drive instead of service account!"
echo "This resolves the storage quota issue you were experiencing."
