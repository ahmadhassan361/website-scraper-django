# Google OAuth2 Setup Guide

This guide will help you switch from service account authentication to OAuth2 authentication, resolving the Google Drive storage quota issues.

## Overview

The system has been updated to use OAuth2 authentication instead of service account authentication. This provides several benefits:

- **Higher Storage Quota**: Uses your personal Google Drive storage (15GB+ free)
- **No Service Account Limits**: Eliminates service account storage restrictions  
- **Better Security**: Token-based authentication with automatic refresh
- **Direct Access**: Files are created directly in your personal Google Drive
- **Easy Management**: View and manage exported files in your Drive

## Files Changed

The following files have been created/modified:

### New Files:
- `scraper/google_auth.py` - OAuth2 authentication manager
- `scraper/urls.py` - OAuth2 URL patterns  
- `templates/scraper/oauth2_setup.html` - Setup instructions page
- `setup_oauth2.sh` - Setup script
- `OAUTH2_SETUP_GUIDE.md` - This guide

### Modified Files:
- `requirements.txt` - Added `google-auth-oauthlib==1.2.0`
- `scraper/models.py` - Added `GoogleOAuth2Token` model
- `scraper/views.py` - Added OAuth2 views
- `scraper/tasks.py` - Updated `export_products_to_google_sheet` to use OAuth2
- `core/urls.py` - Added scraper app URLs

## Setup Instructions

### Step 1: Install Dependencies

Run the setup script to install the new dependency:

```bash
chmod +x setup_oauth2.sh
./setup_oauth2.sh
```

Or manually install:
```bash
pip install google-auth-oauthlib==1.2.0
```

### Step 2: Create Database Migration

```bash
python manage.py makemigrations scraper
python manage.py migrate
```

### Step 3: Google Cloud Console Setup

1. **Go to Google Cloud Console**
   - Visit https://console.cloud.google.com/
   - Select your existing project or create a new one

2. **Enable Required APIs**
   - Navigate to "APIs & Services" > "Library"
   - Enable:
     - Google Drive API
     - Google Sheets API

3. **Create OAuth2 Credentials**
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth 2.0 Client IDs"
   - Choose "Web application"
   - Set name: "Website Scraper OAuth2"
   - Add authorized redirect URIs:
     - `http://localhost:8000/scraper/google/callback/` (for local development)
     - `https://yourdomain.com/scraper/google/callback/` (for production)

4. **Download Credentials**
   - Download the JSON file
   - Rename it to `oauth2_credentials.json`
   - Place it in the `credentials/` directory

### Step 4: Authorize the Application

1. Start your Django server:
   ```bash
   python manage.py runserver
   ```

2. Visit the setup instructions page:
   ```
   http://localhost:8000/scraper/google/setup/
   ```

3. Follow the authorization process:
   ```
   http://localhost:8000/scraper/google/authorize/
   ```

4. Sign in with your personal Google account and grant permissions

## How It Works

### Authentication Flow

1. **Initial Setup**: User visits `/scraper/google/authorize/`
2. **Google Authorization**: User is redirected to Google's OAuth2 consent screen
3. **Callback**: Google redirects back with authorization code
4. **Token Exchange**: Application exchanges code for access and refresh tokens
5. **Token Storage**: Tokens are securely stored in the database
6. **API Calls**: Subsequent API calls use stored tokens with automatic refresh

### Export Process

1. **Token Validation**: System checks for valid OAuth2 tokens
2. **Credential Refresh**: Automatically refreshes expired tokens
3. **File Upload**: Uploads directly to your personal Google Drive
4. **Public Sharing**: Makes files publicly accessible (optional)
5. **Link Generation**: Provides direct Google Sheets links

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/scraper/google/authorize/` | Start OAuth2 authorization flow |
| `/scraper/google/callback/` | Handle OAuth2 callback |
| `/scraper/google/status/` | Check authorization status (JSON) |
| `/scraper/google/revoke/` | Revoke OAuth2 tokens |
| `/scraper/google/setup/` | Setup instructions page |

## Troubleshooting

### Common Issues

1. **"No valid OAuth2 credentials" Error**
   - Ensure `oauth2_credentials.json` is in the `credentials/` directory
   - Check file permissions and format
   - Verify APIs are enabled in Google Cloud Console

2. **"Invalid redirect URI" Error**
   - Add the correct redirect URI in Google Cloud Console
   - Match the exact URL format used by your application

3. **Token Expired Issues**
   - The system automatically refreshes tokens
   - If issues persist, re-authorize the application

4. **Permission Denied**
   - Ensure you granted all required permissions during authorization
   - Check that the Google account has sufficient Drive storage

### Debug Information

Check OAuth2 status:
```bash
curl http://localhost:8000/scraper/google/status/
```

View stored tokens (admin only):
- Django Admin > Scraper > Google OAuth2 Tokens

### Logs

Enable logging to debug OAuth2 issues:
```python
# In settings.py
LOGGING = {
    'loggers': {
        'scraper.google_auth': {
            'level': 'DEBUG',
            'handlers': ['console'],
        },
    },
}
```

## Security Considerations

1. **Token Storage**: Tokens are stored encrypted in the database
2. **HTTPS**: Use HTTPS in production for OAuth2 callbacks
3. **State Parameter**: CSRF protection is implemented in the OAuth2 flow
4. **Token Expiry**: Access tokens automatically refresh
5. **Revocation**: Tokens can be revoked through the admin interface

## Migration from Service Account

The old service account method will continue to work if OAuth2 tokens are not available. However, for the best experience and to resolve quota issues:

1. Complete the OAuth2 setup
2. Test the export functionality
3. Remove or backup the old service account JSON file
4. Update any deployment scripts to use OAuth2

## Benefits Summary

| Feature | Service Account | OAuth2 |
|---------|----------------|--------|
| Storage Quota | Very Limited | 15GB+ Personal |
| Setup Complexity | Medium | Medium |
| File Location | Service Account Drive | Personal Drive |
| Token Management | Static Key | Auto-refresh |
| Storage Cost | Paid upgrades | Free personal quota |
| File Access | Need sharing setup | Direct personal access |

## Support

If you encounter issues:

1. Check the setup instructions page: `/scraper/google/setup/`
2. Review the Django logs for error details
3. Verify Google Cloud Console configuration
4. Test OAuth2 status endpoint: `/scraper/google/status/`

The OAuth2 implementation provides a robust, scalable solution for Google Drive integration while eliminating storage quota limitations.
