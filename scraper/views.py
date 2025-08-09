from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.urls import reverse
from django.conf import settings
import logging

from .google_auth import google_auth_manager
from .models import GoogleOAuth2Token

logger = logging.getLogger(__name__)

# Create your views here.

@login_required
def google_oauth2_authorize(request):
    """Initiate Google OAuth2 authorization flow"""
    try:
        redirect_uri = request.build_absolute_uri(reverse('google_oauth2_callback'))
        authorization_url, state = google_auth_manager.get_authorization_url(redirect_uri)
        
        # Store state in session for security
        request.session['oauth2_state'] = state
        
        return redirect(authorization_url)
    except Exception as e:
        logger.error(f"Error initiating OAuth2 flow: {e}")
        messages.error(request, f"Failed to initiate Google authorization: {str(e)}")
        return redirect('dashboard:index')  # Adjust this redirect as needed

@login_required
def google_oauth2_callback(request):
    """Handle Google OAuth2 callback"""
    try:
        # Get authorization code and state from callback
        code = request.GET.get('code')
        state = request.GET.get('state')
        error = request.GET.get('error')
        
        if error:
            logger.error(f"OAuth2 authorization error: {error}")
            messages.error(request, f"Google authorization failed: {error}")
            return redirect('dashboard:index')  # Adjust this redirect as needed
        
        if not code or not state:
            logger.error("Missing authorization code or state in callback")
            messages.error(request, "Invalid authorization callback")
            return redirect('dashboard:index')  # Adjust this redirect as needed
        
        # Verify state parameter for security
        session_state = request.session.get('oauth2_state')
        if not session_state or session_state != state:
            logger.error("OAuth2 state mismatch - possible CSRF attack")
            messages.error(request, "Authorization failed - security check failed")
            return redirect('dashboard:index')  # Adjust this redirect as needed
        
        # Exchange code for tokens
        redirect_uri = request.build_absolute_uri(reverse('google_oauth2_callback'))
        token_data = google_auth_manager.exchange_code_for_tokens(code, state, redirect_uri)
        
        # Save tokens
        google_auth_manager.save_tokens(token_data, user=request.user)
        
        # Clean up session
        if 'oauth2_state' in request.session:
            del request.session['oauth2_state']
        
        messages.success(request, "Google Drive authorization successful! You can now export to Google Sheets.")
        logger.info(f"OAuth2 authorization completed successfully for user: {request.user.username}")
        
        return redirect('dashboard:index')  # Adjust this redirect as needed
        
    except Exception as e:
        logger.error(f"Error handling OAuth2 callback: {e}")
        messages.error(request, f"Authorization failed: {str(e)}")
        return redirect('dashboard:index')  # Adjust this redirect as needed

@login_required
def google_oauth2_status(request):
    """Check Google OAuth2 authorization status"""
    try:
        active_token = GoogleOAuth2Token.objects.filter(is_active=True).first()
        
        if active_token:
            # Test if credentials are still valid
            credentials = google_auth_manager.get_active_credentials()
            if credentials:
                status = {
                    'authorized': True,
                    'user': active_token.user.username if active_token.user else 'System',
                    'scopes': active_token.scopes,
                    'expires_at': active_token.expires_at.isoformat(),
                    'is_expired': active_token.is_expired
                }
            else:
                status = {
                    'authorized': False,
                    'error': 'Invalid or expired credentials'
                }
        else:
            status = {
                'authorized': False,
                'error': 'No active OAuth2 tokens found'
            }
        
        return JsonResponse(status)
    except Exception as e:
        logger.error(f"Error checking OAuth2 status: {e}")
        return JsonResponse({
            'authorized': False,
            'error': str(e)
        })

@login_required
def google_oauth2_revoke(request):
    """Revoke Google OAuth2 tokens"""
    if request.method == 'POST':
        try:
            google_auth_manager.revoke_tokens()
            messages.success(request, "Google Drive authorization revoked successfully.")
            logger.info(f"OAuth2 tokens revoked by user: {request.user.username}")
        except Exception as e:
            logger.error(f"Error revoking OAuth2 tokens: {e}")
            messages.error(request, f"Failed to revoke authorization: {str(e)}")
    
    return redirect('dashboard:index')  # Adjust this redirect as needed

def google_oauth2_setup_instructions(request):
    """Display setup instructions for OAuth2"""
    return render(request, 'scraper/oauth2_setup.html')
