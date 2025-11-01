"""
Custom JWT authentication for patient API access.
"""
import logging
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from .models import PatientToken

logger = logging.getLogger(__name__)


class PatientJWTAuthentication(BaseAuthentication):
    """
    Custom JWT authentication that validates tokens against the PatientToken model.
    Checks for token revocation and updates last_used_at timestamp.
    """
    
    def authenticate(self, request):
        """
        Authenticate the request using JWT token.
        Returns None if no auth header, or (user_data, token) tuple if authenticated.
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return None  # No token provided, not an error
        
        token_string = auth_header.split(' ')[1]
        
        try:
            # Decode and validate the token structure
            access_token = AccessToken(token_string)
            jti = access_token.get('jti')
            
            if not jti:
                raise AuthenticationFailed('Token does not contain JTI claim')
            
            # Check if token exists in database and is not revoked
            try:
                patient_token = PatientToken.objects.get(
                    jti=jti,
                    token_type='access'
                )
            except PatientToken.DoesNotExist:
                logger.warning(f"Token with jti {jti} not found in database")
                raise AuthenticationFailed('Token not found or invalid')
            
            # Check if token is revoked
            if patient_token.is_revoked:
                logger.warning(f"Revoked token used: jti={jti}, reason={patient_token.revocation_reason}")
                raise AuthenticationFailed('Token has been revoked')
            
            # Check if token is expired
            if patient_token.expires_at < timezone.now():
                logger.warning(f"Expired token used: jti={jti}, expired_at={patient_token.expires_at}")
                raise AuthenticationFailed('Token has expired')
            
            # Update last used timestamp
            patient_token.last_used_at = timezone.now()
            patient_token.save(update_fields=['last_used_at'])
            
            # Create a patient data object from token claims
            patient_data = {
                'personal_number': access_token.get('personal_number'),
                'mobile_phone': access_token.get('mobile_phone'),
                'jti': jti,
                'token_created_at': patient_token.created_at,
            }
            
            logger.debug(f"Successfully authenticated patient: {patient_data['personal_number']}")
            
            # Return patient data and token
            # Django expects (user, auth) tuple, but we can use custom objects
            return (patient_data, access_token)
            
        except (InvalidToken, TokenError) as e:
            logger.warning(f"Invalid token: {str(e)}")
            raise AuthenticationFailed(f'Invalid token: {str(e)}')
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}", exc_info=True)
            raise AuthenticationFailed('Authentication failed')
    
    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the WWW-Authenticate
        header in a 401 Unauthenticated response.
        """
        return 'Bearer realm="api"'
