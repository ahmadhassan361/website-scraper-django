"""
Custom authentication classes for API
"""
from rest_framework import authentication
from rest_framework import exceptions
from django.conf import settings


class StaticTokenAuthentication(authentication.BaseAuthentication):
    """
    Simple static token authentication
    
    Clients should authenticate by passing the token in the "Authorization" header,
    prepended with the string "Bearer ". For example:
    
        Authorization: Bearer your-secret-api-token-here
    
    Alternatively, clients can pass the token in the "X-API-Key" header:
    
        X-API-Key: your-secret-api-token-here
    """
    
    keyword = 'Bearer'
    
    def authenticate(self, request):
        """
        Authenticate the request and return a two-tuple of (user, token).
        """
        # Try Authorization header first
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if auth_header:
            # Check if it starts with "Bearer "
            if auth_header.startswith(self.keyword + ' '):
                token = auth_header[len(self.keyword) + 1:]
            else:
                # Maybe it's just the token without "Bearer"
                token = auth_header
        else:
            # Try X-API-Key header
            token = request.META.get('HTTP_X_API_KEY', '')
        
        if not token:
            # No token provided
            return None
        
        return self.authenticate_credentials(token)
    
    def authenticate_credentials(self, token):
        """
        Validate the token against the configured static token
        """
        expected_token = settings.API_AUTH_TOKEN
        
        if token != expected_token:
            raise exceptions.AuthenticationFailed('Invalid API token')
        
        # Create a simple user object (not tied to database)
        # This allows the request to be authenticated
        from django.contrib.auth.models import AnonymousUser
        
        class APIUser(AnonymousUser):
            """Simple API user object"""
            @property
            def is_authenticated(self):
                return True
            
            @property
            def username(self):
                return 'api_user'
        
        return (APIUser(), token)
    
    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the `WWW-Authenticate`
        header in a `401 Unauthenticated` response.
        """
        return self.keyword
