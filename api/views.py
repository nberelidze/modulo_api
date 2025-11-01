from django.shortcuts import render

# Create your views here.

import base64
import logging
import traceback
from datetime import datetime, time

from django.http import FileResponse
from django.views import View
from django.http import HttpResponse, HttpRequest
from django.template.response import TemplateResponse
from django.shortcuts import render
from drf_spectacular.utils import extend_schema, OpenApiParameter

from rest_framework import status
from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PatientToken
from .serializers import LabTestSerializer, LabTestsSerializer, LabTestCategoriesSerializer, LabTestParametersSerializer, \
    GetPatientRequestSerializer, GetPatientResponseListSerializer, \
    CheckPatientExistsRequestSerializer, CheckPatientExistsResponseSerializer, \
    TokenRefreshRequestSerializer, TokenRefreshResponseSerializer, \
    RevokeTokenRequestSerializer, RevokeTokenResponseSerializer, \
    PatientSessionSerializer, GetSessionsResponseSerializer, \
    RevokeSessionRequestSerializer, RevokeSessionResponseSerializer

from .authentication import PatientJWTAuthentication

from .utils import get_labtests, get_labtest_parameters, get_patient_by_personal_number, check_patient_exists, \
    get_web_product_categories, get_labtests_by_web_category, \
    generate_patient_tokens, refresh_patient_token, revoke_patient_tokens 

logger = logging.getLogger(__name__)

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@extend_schema(
    tags=['LabTests'],
    responses={
        200: LabTestsSerializer(many=True)
    },
)
class LabTestsList(APIView):
    """List all laboratory tests."""
    authentication_classes = []

    def get(self, request):
        results = get_labtests(active_only=False)
        logger.debug(f'{len(results)} laboratory tests found')
        
        response_serializer = LabTestsSerializer(data={'results':results})
        
        if response_serializer.is_valid():
            return Response(response_serializer.data)
        
        return Response(response_serializer.errors)


# Return a specific lab test by id
@extend_schema(
    tags=['LabTests'],
    responses={
        200: LabTestSerializer(),
        404: None
    },
)
class LabTestDetail(APIView):
    """Retrieve a specific laboratory test by id."""
    authentication_classes = []

    def get(self, request, id):
        result = get_labtests(labtest_id=id, active_only=False)

        if result:
            serializer = LabTestSerializer(result[0])
            return Response(serializer.data)
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

# New: List all web_product_category
@extend_schema(
    tags=['LabTests'],
    responses={
        200: LabTestCategoriesSerializer(many=True)
    },
)
class LabTestWebCategoriesList(APIView):
    """List all web product categories."""
    authentication_classes = []

    def get(self, request):
        results = get_web_product_categories()
        logger.debug(f'{len(results)} web product categories found')
        response_serializer = LabTestCategoriesSerializer(data={'results':results})
        if response_serializer.is_valid():
            return Response(response_serializer.data)
        return Response(response_serializer.errors)

# New: List all product_product under a web_category
@extend_schema(
    tags=['LabTests'],
    responses={
        200: LabTestsSerializer(many=True)
    },
)
class LabTestWebCategoryDetail(APIView):
    """List all products under a web product category (show_in_web only)."""
    authentication_classes = []

    def get(self, request, web_category_id):
        results = get_labtests_by_web_category(web_category_id)
        logger.debug(f'{len(results)} products found for web_category_id={web_category_id}')
        response_serializer = LabTestsSerializer(data={'results':results})
        if response_serializer.is_valid():
            return Response(response_serializer.data)
        return Response(response_serializer.errors)

@extend_schema(
    tags=['LabTests'],
    responses={
        200: LabTestParametersSerializer(many=True)
    },
)
class LabTestParametersDetail(APIView):
    """Get parameters for a specific laboratory test."""
    authentication_classes = []

    def get(self, request, id):
        results = get_labtest_parameters(id)
        logger.debug(f'{len(results)} laboratory test parameters found for labtest_id:{id}')
        
        response_serializer = LabTestParametersSerializer(data={'results':results})
        if response_serializer.is_valid():
            return Response(response_serializer.data)
        return Response(response_serializer.errors)


@extend_schema(
    tags=['Patient'],
    request=GetPatientRequestSerializer,
    responses={
        200: GetPatientResponseListSerializer,
        404: None
    },
    description="""
    Get patient information by personal number.
    
    **Authentication Required:** This endpoint requires a valid JWT access token.
    Click the 'Authorize' button at the top of this page and enter your token in the format: `Bearer <your_access_token>`
    
    You can obtain an access token by calling the `/api/patient/check` endpoint with valid credentials.
    """
)
class GetPatient(APIView):
    serializer_class = GetPatientRequestSerializer
    authentication_classes = [PatientJWTAuthentication]
    permission_classes = []

    def post(self, request):
        logger.info("/api/patient request raw body %s", request.body.decode())
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            data = serializer.data
            logger.info("/api/patient request deserialized data %s", serializer.validated_data)

            # Security check: ensure authenticated patient can only query their own data
            if not request.auth:
                logger.error("/api/patient authentication failed: request.auth is None")
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            authenticated_personal_number = request.auth.get('personal_number')
            if authenticated_personal_number != data['personalNumber']:
                logger.warning(
                    f"/api/patient security violation: patient {authenticated_personal_number} "
                    f"attempted to query data for {data['personalNumber']}"
                )
                return Response(
                    {'error': 'You can only access your own patient data'},
                    status=status.HTTP_403_FORBIDDEN
                )

            patient_data_list = get_patient_by_personal_number(data['personalNumber'])
            
            if patient_data_list:
                logger.info(f"/api/patient found {len(patient_data_list)} patient(s): {patient_data_list}")
                response_serializer = GetPatientResponseListSerializer(data={'patients': patient_data_list})
                if response_serializer.is_valid():
                    logger.info('/api/patient response is %s', response_serializer.data)
                    return Response(response_serializer.data)
                return Response(response_serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                logger.info(f"/api/patient patient not found for personal number: {data['personalNumber']}")
                return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    tags=['Patient'],
    request=CheckPatientExistsRequestSerializer,
    responses={
        200: CheckPatientExistsResponseSerializer
    }
)
class CheckPatientExists(APIView):
    serializer_class = CheckPatientExistsRequestSerializer
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        logger.info("/api/patient/check request raw body %s", request.body.decode())
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            logger.info("/api/patient/check request deserialized data %s", data)

            exists = check_patient_exists(data['personalNumber'], data['mobilePhone'])
            
            logger.info(f"/api/patient/check patient exists: {exists} for personal number: {data['personalNumber']}, mobile: {data['mobilePhone']}")
            
            response_data = {'exists': exists}
            
            # If patient exists, generate and return JWT tokens
            if exists:
                try:
                    # Extract client IP and user agent from request
                    client_ip = get_client_ip(request)
                    user_agent = request.META.get('HTTP_USER_AGENT', '')
                    
                    tokens = generate_patient_tokens(
                        personal_number=data['personalNumber'],
                        mobile_phone=data['mobilePhone'],
                        client_ip=client_ip,
                        user_agent=user_agent
                    )
                    
                    response_data['accessToken'] = tokens['access_token']
                    response_data['refreshToken'] = tokens['refresh_token']
                    response_data['expiresIn'] = tokens['access_expires_in']
                    
                    logger.info(f"/api/patient/check generated tokens for patient {data['personalNumber']}")
                    
                except Exception as e:
                    logger.error(f"/api/patient/check error generating tokens: {str(e)}", exc_info=True)
                    return Response(
                        {'error': 'Failed to generate authentication tokens'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            
            response_serializer = CheckPatientExistsResponseSerializer(data=response_data)
            if response_serializer.is_valid():
                logger.info('/api/patient/check response is %s', response_serializer.data)
                return Response(response_serializer.data)
            return Response(response_serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=['Patient', 'Authentication'],
    request=TokenRefreshRequestSerializer,
    responses={
        200: TokenRefreshResponseSerializer
    }
)
class RefreshPatientToken(APIView):
    """
    Refresh an access token using a refresh token.
    """
    serializer_class = TokenRefreshRequestSerializer
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        logger.info("/api/patient/token/refresh request")
        serializer = self.serializer_class(data=request.data)
        
        if serializer.is_valid():
            data = serializer.validated_data
            
            try:
                result = refresh_patient_token(data['refreshToken'])
                
                response_data = {
                    'accessToken': result['access_token'],
                    'expiresIn': result['access_expires_in']
                }
                
                if 'refresh_token' in result:
                    response_data['refreshToken'] = result['refresh_token']
                
                response_serializer = TokenRefreshResponseSerializer(data=response_data)
                if response_serializer.is_valid():
                    logger.info('/api/patient/token/refresh successful')
                    return Response(response_serializer.data)
                return Response(response_serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
            except Exception as e:
                logger.error(f"/api/patient/token/refresh error: {str(e)}", exc_info=True)
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_401_UNAUTHORIZED
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=['Patient', 'Authentication'],
    request=RevokeTokenRequestSerializer,
    responses={
        200: RevokeTokenResponseSerializer
    }
)
class RevokePatientTokens(APIView):
    """
    Revoke all tokens for a specific patient.
    Requires authentication.
    """
    serializer_class = RevokeTokenRequestSerializer
    authentication_classes = []  # TODO: Add admin authentication
    permission_classes = []

    def post(self, request):
        logger.info("/api/patient/token/revoke request")
        serializer = self.serializer_class(data=request.data)
        
        if serializer.is_valid():
            data = serializer.validated_data
            
            try:
                count = revoke_patient_tokens(
                    personal_number=data['personalNumber'],
                    reason=data.get('reason', 'Manual revocation')
                )
                
                response_data = {
                    'success': True,
                    'tokensRevoked': count,
                    'message': f'Successfully revoked {count} token(s)'
                }
                
                response_serializer = RevokeTokenResponseSerializer(data=response_data)
                if response_serializer.is_valid():
                    logger.info(f'/api/patient/token/revoke revoked {count} tokens for {data["personalNumber"]}')
                    return Response(response_serializer.data)
                return Response(response_serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
            except Exception as e:
                logger.error(f"/api/patient/token/revoke error: {str(e)}", exc_info=True)
                return Response(
                    {
                        'success': False,
                        'tokensRevoked': 0,
                        'message': str(e)
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=['Patient', 'Session Management'],
    responses={
        200: GetSessionsResponseSerializer
    },
    description="""
    Get all active sessions for the authenticated patient.
    
    **Authentication Required:** Click 'Authorize' at the top and enter: `Bearer <your_access_token>`
    
    Returns a list of all active sessions including device information, IP addresses, and last activity timestamps.
    """
)
class GetPatientSessions(APIView):
    """
    Get all active sessions for the authenticated patient.
    Requires patient JWT authentication.
    """
    authentication_classes = [PatientJWTAuthentication]
    permission_classes = []

    def get(self, request):
        logger.info("/api/patient/sessions request")
        
        try:
            # Get personal_number from authenticated token
            personal_number = request.auth.get('personal_number')
            
            # Get active sessions using model method
            sessions_data = PatientToken.get_active_sessions(personal_number)
            
            response_data = {
                'sessions': sessions_data,
                'totalSessions': len(sessions_data)
            }
            
            response_serializer = GetSessionsResponseSerializer(data=response_data)
            if response_serializer.is_valid():
                logger.info(f'/api/patient/sessions returned {len(sessions_data)} sessions')
                return Response(response_serializer.data)
            return Response(response_serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            logger.error(f"/api/patient/sessions error: {str(e)}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Patient', 'Session Management'],
    request=RevokeSessionRequestSerializer,
    responses={
        200: RevokeSessionResponseSerializer
    },
    description="""
    Revoke a specific session for the authenticated patient.
    
    **Authentication Required:** Click 'Authorize' at the top and enter: `Bearer <your_access_token>`
    
    This will invalidate all tokens associated with the specified session ID, effectively logging out that device/session.
    """
)
class RevokePatientSession(APIView):
    """
    Revoke a specific session for the authenticated patient.
    Requires patient JWT authentication.
    """
    serializer_class = RevokeSessionRequestSerializer
    authentication_classes = [PatientJWTAuthentication]
    permission_classes = []

    def post(self, request):
        logger.info("/api/patient/sessions/revoke request")
        serializer = self.serializer_class(data=request.data)
        
        if serializer.is_valid():
            data = serializer.validated_data
            
            try:
                # Get personal_number from authenticated token
                personal_number = request.auth.get('personal_number')
                
                # Revoke session using model method
                count = PatientToken.revoke_session(
                    personal_number=personal_number,
                    session_id=data['sessionId'],
                    reason='Manual session revocation'
                )
                
                response_data = {
                    'success': True,
                    'tokensRevoked': count,
                    'message': f'Successfully revoked session (revoked {count} token(s))'
                }
                
                response_serializer = RevokeSessionResponseSerializer(data=response_data)
                if response_serializer.is_valid():
                    logger.info(f'/api/patient/sessions/revoke revoked session {data["sessionId"]} ({count} tokens)')
                    return Response(response_serializer.data)
                return Response(response_serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
            except Exception as e:
                logger.error(f"/api/patient/sessions/revoke error: {str(e)}", exc_info=True)
                return Response(
                    {
                        'success': False,
                        'tokensRevoked': 0,
                        'message': str(e)
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)