"""
Google OAuth2 authentication utilities for Google Drive and Sheets API access
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from django.conf import settings
from django.utils import timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from .models import GoogleOAuth2Token

logger = logging.getLogger(__name__)

class GoogleOAuth2Manager:
    """Manager class for Google OAuth2 authentication"""
    
    SCOPES = [
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/spreadsheets'
    ]
    
    def __init__(self):
        self.credentials_file = os.path.join(settings.BASE_DIR, 'credentials', 'oauth2_credentials.json')
        
    def get_oauth2_credentials_config(self) -> Dict[str, Any]:
        """Load OAuth2 credentials from JSON file"""
        try:
            with open(self.credentials_file, 'r') as f:
                credentials_data = json.load(f)
                return credentials_data.get('web', credentials_data.get('installed', {}))
        except FileNotFoundError:
            logger.error(f"OAuth2 credentials file not found at {self.credentials_file}")
            raise Exception("OAuth2 credentials file not found. Please download it from Google Cloud Console.")
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in credentials file: {self.credentials_file}")
            raise Exception("Invalid credentials file format")
    
    def get_authorization_url(self, redirect_uri: str) -> tuple[str, str]:
        """
        Generate authorization URL for OAuth2 flow
        
        Returns:
            tuple: (authorization_url, state)
        """
        try:
            config = self.get_oauth2_credentials_config()
            
            flow = Flow.from_client_config(
                {
                    'web': config
                },
                scopes=self.SCOPES,
                redirect_uri=redirect_uri
            )
            
            authorization_url, state = flow.authorization_url(
                access_type='offline',  # Enables refresh token
                include_granted_scopes='true',
                prompt='consent'  # Forces consent screen to get refresh token
            )
            
            return authorization_url, state
        except Exception as e:
            logger.error(f"Error generating authorization URL: {e}")
            raise
    
    def exchange_code_for_tokens(self, code: str, state: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens
        
        Args:
            code: Authorization code from OAuth2 callback
            state: State parameter from OAuth2 flow
            redirect_uri: Redirect URI used in the flow
            
        Returns:
            dict: Token information
        """
        try:
            config = self.get_oauth2_credentials_config()
            
            flow = Flow.from_client_config(
                {
                    'web': config
                },
                scopes=self.SCOPES,
                redirect_uri=redirect_uri,
                state=state
            )
            
            flow.fetch_token(code=code)
            credentials = flow.credentials
            
            # Calculate expiry time
            expires_at = timezone.now()
            if credentials.expiry:
                expires_at = timezone.make_aware(credentials.expiry) if timezone.is_naive(credentials.expiry) else credentials.expiry
            else:
                # Default to 1 hour if no expiry provided
                expires_at = timezone.now() + timedelta(hours=1)
            
            token_data = {
                'access_token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'token_uri': credentials.token_uri,
                'scopes': list(credentials.scopes) if credentials.scopes else self.SCOPES,
                'expires_at': expires_at
            }
            
            return token_data
        except Exception as e:
            logger.error(f"Error exchanging code for tokens: {e}")
            raise
    
    def save_tokens(self, token_data: Dict[str, Any], user=None) -> GoogleOAuth2Token:
        """
        Save OAuth2 tokens to database
        
        Args:
            token_data: Token information from OAuth2 flow
            user: User associated with tokens (optional)
            
        Returns:
            GoogleOAuth2Token: Saved token instance
        """
        try:
            # Deactivate any existing active tokens
            GoogleOAuth2Token.objects.filter(is_active=True).update(is_active=False)
            
            # Create new token record
            token = GoogleOAuth2Token.objects.create(
                user=user,
                access_token=token_data['access_token'],
                refresh_token=token_data['refresh_token'],
                client_id=token_data['client_id'],
                client_secret=token_data['client_secret'],
                token_uri=token_data['token_uri'],
                scopes=token_data['scopes'],
                expires_at=token_data['expires_at'],
                is_active=True
            )
            
            logger.info(f"OAuth2 tokens saved successfully for user: {user.username if user else 'System'}")
            return token
        except Exception as e:
            logger.error(f"Error saving tokens: {e}")
            raise
    
    def get_active_credentials(self) -> Optional[Credentials]:
        """
        Get active Google credentials, refreshing if necessary
        
        Returns:
            Credentials: Google OAuth2 credentials or None if not available
        """
        try:
            token = GoogleOAuth2Token.objects.filter(is_active=True).first()
            if not token:
                logger.warning("No active OAuth2 tokens found")
                return None
            
            # Create credentials object
            credentials = Credentials(
                token=token.access_token,
                refresh_token=token.refresh_token,
                token_uri=token.token_uri,
                client_id=token.client_id,
                client_secret=token.client_secret,
                scopes=token.scopes
            )
            
            # Check if token needs refresh
            if token.is_expired or not credentials.valid:
                logger.info("Refreshing expired OAuth2 token")
                credentials.refresh(Request())
                
                # Update token in database
                token.access_token = credentials.token
                if credentials.expiry:
                    token.expires_at = timezone.make_aware(credentials.expiry) if timezone.is_naive(credentials.expiry) else credentials.expiry
                else:
                    token.expires_at = timezone.now() + timedelta(hours=1)
                token.save()
                
                logger.info("OAuth2 token refreshed successfully")
            
            return credentials
        except Exception as e:
            logger.error(f"Error getting active credentials: {e}")
            return None
    
    def build_drive_service(self):
        """Build Google Drive service"""
        credentials = self.get_active_credentials()
        if not credentials:
            raise Exception("No valid OAuth2 credentials available. Please authorize the application first.")
        
        return build('drive', 'v3', credentials=credentials)
    
    def build_sheets_service(self):
        """Build Google Sheets service"""
        credentials = self.get_active_credentials()
        if not credentials:
            raise Exception("No valid OAuth2 credentials available. Please authorize the application first.")
        
        return build('sheets', 'v4', credentials=credentials)
    
    def revoke_tokens(self):
        """Revoke all active OAuth2 tokens"""
        try:
            credentials = self.get_active_credentials()
            if credentials:
                credentials.revoke(Request())
            
            # Deactivate tokens in database
            GoogleOAuth2Token.objects.filter(is_active=True).update(is_active=False)
            logger.info("OAuth2 tokens revoked successfully")
        except Exception as e:
            logger.error(f"Error revoking tokens: {e}")
            raise


# Global instance
google_auth_manager = GoogleOAuth2Manager()
