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
    RevokeSessionRequestSerializer, RevokeSessionResponseSerializer, \
    LabOrdersSerializer, LabOrderDetailSerializer, LabOrderStatsSerializer, \
    CreatePatientRequestSerializer, CreatePatientResponseSerializer, \
    CreateOrderRequestSerializer, CreateOrderResponseSerializer, \
    PivotTableRequestSerializer, PivotTableResponseSerializer, LabTestPDFsSerializer

from .authentication import PatientJWTAuthentication

from .utils import get_labtests, get_labtest_parameters, get_patient_by_personal_number, check_patient_exists, \
    get_web_product_categories, get_labtests_by_web_category, \
    generate_patient_tokens, refresh_patient_token, revoke_patient_tokens, get_lab_orders, get_lab_order_stats, \
    create_partner, get_or_create_patient, create_sale_order, generate_pivot_table, \
    get_labtests_rpc, get_labtest_pdfs

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
        # results = get_labtests(active_only=False)
        results = get_labtests_rpc()
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
        # result = get_labtests(labtest_id=id, active_only=False)
        result = get_labtests_rpc(labtest_id=id)

        if result:
            serializer = LabTestSerializer(result[0])
            return Response(serializer.data)
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    tags=['LabTests'],
    responses={
        200: LabTestPDFsSerializer,
        404: None,
    },
)
class LabTestPDFs(APIView):
    """Retrieve the English and Georgian PDF attachments for a lab test by id."""
    authentication_classes = []

    def get(self, request, id):
        result = get_labtest_pdfs(id)
        if result is None:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = LabTestPDFsSerializer(data=result)
        if serializer.is_valid():
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
        # results = get_labtests_by_web_category(web_category_id)
        results = get_labtests_rpc(web_category_id=web_category_id)
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


@extend_schema(
    tags=['Patient'],
    responses={
        200: LabOrdersSerializer,
        401: None,
        404: None
    },
    description="""
    Get lab orders for the authenticated patient.
    
    **Authentication Required:** This endpoint requires a valid JWT access token.
    Click the 'Authorize' button at the top of this page and enter your token in the format: `Bearer <your_access_token>`
    
    Returns all lab orders associated with the authenticated patient's personal number, ordered by date (most recent first).
    """
)
class GetPatientLabOrders(APIView):
    """
    Retrieve lab orders for the authenticated patient.
    Requires patient JWT authentication.
    """
    authentication_classes = [PatientJWTAuthentication]
    permission_classes = []

    def get(self, request):
        logger.info("/api/patient/laborders request")
        
        # Get personal_number from authenticated token
        if not request.auth:
            logger.error("/api/patient/laborders authentication failed: request.auth is None")
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        personal_number = request.auth.get('personal_number')
        logger.info(f"/api/patient/laborders fetching lab orders for personal_number: {personal_number}")
        
        try:
            lab_orders = get_lab_orders(personal_number)
            
            response_data = {
                'labOrders': lab_orders,
                'totalLabOrders': len(lab_orders)
            }
            
            response_serializer = LabOrdersSerializer(data=response_data)
            if response_serializer.is_valid():
                logger.info(f'/api/patient/laborders found {len(lab_orders)} lab order(s)')
                return Response(response_serializer.data)
            
            logger.error(f'/api/patient/laborders serializer errors: {response_serializer.errors}')
            return Response(response_serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            logger.error(f"/api/patient/laborders error: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to fetch lab orders'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Patient'],
    responses={
        200: LabOrderDetailSerializer,
        401: None,
        403: None,
        404: None
    },
    description="""
    Get detailed information for a specific lab order including all test parameters.
    
    **Authentication Required:** This endpoint requires a valid JWT access token.
    Click the 'Authorize' button at the top of this page and enter your token in the format: `Bearer <your_access_token>`
    
    Returns the lab order with all associated parameters from inno_laborder_parameter.
    Patients can only access their own lab orders.
    """
)
class GetPatientLabOrderDetail(APIView):
    """
    Retrieve detailed information for a specific lab order.
    Requires patient JWT authentication.
    """
    authentication_classes = [PatientJWTAuthentication]
    permission_classes = []

    def get(self, request, id):
        logger.info(f"/api/patient/laborders/{id} request")
        
        # Get personal_number from authenticated token
        if not request.auth:
            logger.error(f"/api/patient/laborders/{id} authentication failed: request.auth is None")
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        personal_number = request.auth.get('personal_number')
        logger.info(f"/api/patient/laborders/{id} fetching lab order for personal_number: {personal_number}")
        
        try:
            lab_order = get_lab_orders(personal_number, laborder_id=id, include_parameters=True)
            
            if not lab_order:
                logger.warning(f'/api/patient/laborders/{id} not found or access denied for personal_number: {personal_number}')
                return Response(
                    {'error': 'Lab order not found or you do not have permission to access it'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            response_serializer = LabOrderDetailSerializer(data=lab_order)
            if response_serializer.is_valid():
                logger.info(f'/api/patient/laborders/{id} found order with {len(lab_order.get("parameters", []))} parameter(s)')
                return Response(response_serializer.data)
            
            logger.error(f'/api/patient/laborders/{id} serializer errors: {response_serializer.errors}')
            return Response(response_serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            logger.error(f"/api/patient/laborders/{id} error: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to fetch lab order details'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Patient'],
    responses={
        200: LabOrderStatsSerializer,
        401: None
    },
    description="""
    Get lab order statistics for the authenticated patient.
    
    **Authentication Required:** This endpoint requires a valid JWT access token.
    Click the 'Authorize' button at the top of this page and enter your token in the format: `Bearer <your_access_token>`
    
    Returns aggregated parameter data across all completed lab orders for the authenticated patient.
    Data includes parameter values over time, ordered by date and lab order.
    
    **Usage:**
    - `/api/patient/laborders/stats/` - Get all lab order statistics
    - `/api/patient/laborders/stats/{categ_id}/` - Get statistics filtered by category ID
    """
)
class GetPatientLabOrderStats(APIView):
    """
    Retrieve lab order statistics for the authenticated patient.
    Requires patient JWT authentication.
    """
    authentication_classes = [PatientJWTAuthentication]
    permission_classes = []

    def get(self, request, categ_id=None):
        logger.info(f"/api/patient/laborders/stats request with categ_id: {categ_id}")
        
        # Get personal_number from authenticated token
        if not request.auth:
            logger.error("/api/patient/laborders/stats authentication failed: request.auth is None")
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        personal_number = request.auth.get('personal_number')
        logger.info(f"/api/patient/laborders/stats fetching stats for personal_number: {personal_number}, categ_id: {categ_id}")
        
        try:
            stats = get_lab_order_stats(personal_number, categ_id=categ_id)
            
            response_data = {
                'stats': stats,
                'totalRecords': len(stats)
            }
            
            response_serializer = LabOrderStatsSerializer(data=response_data)
            if response_serializer.is_valid():
                logger.info(f'/api/patient/laborders/stats found {len(stats)} stat record(s)')
                return Response(response_serializer.data)
            
            logger.error(f'/api/patient/laborders/stats serializer errors: {response_serializer.errors}')
            return Response(response_serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            logger.error(f"/api/patient/laborders/stats error: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to fetch lab order statistics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Patient'],
    request=CreatePatientRequestSerializer,
    responses={
        201: CreatePatientResponseSerializer,
        400: None
    },
    description="""
    Create a new patient in the OpenERP system.
    
    This endpoint creates a new patient record with the provided information.
    A unique patient code will be automatically generated based on the gender.
    
    **Note:** This endpoint does not require authentication.
    """
)
class CreatePatient(APIView):
    """
    Create a new patient in OpenERP.
    No authentication required.
    """
    serializer_class = CreatePatientRequestSerializer
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        logger.info("/api/patient/create request raw body %s", request.body.decode())
        serializer = self.serializer_class(data=request.data)
        
        if not serializer.is_valid():
            logger.error(f"/api/patient/create validation errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        logger.info("/api/patient/create request deserialized data %s", data)
        
        try:
            # Create patient using the utility function
            partner_id, patient_code = create_partner(
                first_name=data['firstName'],
                last_name=data['lastName'],
                birth_date=data['dateOfBirth'],
                sex=data['sex'],
                personal_number=data['personalNumber'],
                name=data.get('name')  # Will use firstName + lastName if not provided
            )
            
            # Prepare response data
            response_data = {
                'partnerId': partner_id,
                'patientCode': patient_code,
                'personalNumber': data['personalNumber'],
                'firstName': data['firstName'],
                'lastName': data['lastName'],
                'name': data.get('name') or f"{data['firstName']} {data['lastName']}",
                'dateOfBirth': data['dateOfBirth'],
                'sex': data['sex'],
                'externalCode': data.get('externalCode'),
                'note': data.get('note')
            }
            
            response_serializer = CreatePatientResponseSerializer(data=response_data)
            if response_serializer.is_valid():
                logger.info(f"/api/patient/create successfully created patient {partner_id} with code {patient_code}")
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
            logger.error(f"/api/patient/create response serializer errors: {response_serializer.errors}")
            return Response(response_serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except ValueError as e:
            logger.error(f"/api/patient/create validation error: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"/api/patient/create error: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Failed to create patient: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Orders'],
    request=CreateOrderRequestSerializer,
    responses={
        201: CreateOrderResponseSerializer,
        400: None
    },
    description="""
    Create a new sale order with lab tests in OpenERP.
    
    This endpoint:
    - Creates or retrieves the patient record
    - Finds products by test codes (matching product.product.default_code)
    - Creates a sale order with the specified tests
    - Sets visitNumber to inno_refcode
    - Marks the order as api_call=true
    
    **Note:** This endpoint does not require authentication.
    """
)
class CreateOrder(APIView):
    """
    Create a sale order with lab tests in OpenERP.
    No authentication required.
    """
    serializer_class = CreateOrderRequestSerializer
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        logger.info("/api/orders request raw body %s", request.body.decode())
        serializer = self.serializer_class(data=request.data)
        
        if not serializer.is_valid():
            logger.error(f"/api/orders validation errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        logger.info("/api/orders request deserialized data %s", data)
        
        try:
            # Extract patient info
            patient_data = data['patient']
            personal_number = patient_data['personalNumber']
            
            # Get or create patient
            partner_id, patient_code, created = get_or_create_patient(
                personal_number=personal_number,
                first_name=patient_data.get('firstName'),
                last_name=patient_data.get('lastName'),
                birth_date=patient_data.get('dateOfBirth'),
                sex=patient_data.get('sex'),
                name=patient_data.get('name')
            )
            
            if created:
                logger.info(f"/api/orders created new patient {partner_id}")
            else:
                logger.info(f"/api/orders using existing patient {partner_id}")
            
            # Extract test codes
            test_codes = [test['testCode'] for test in data['tests']]
            visit_number = data['externalInfo']['visitNumber']
            
            # Create sale order
            order_id, order_name, order_line_ids = create_sale_order(
                partner_id=partner_id,
                visit_number=visit_number,
                test_codes=test_codes,
                order_date=data.get('datetime'),
                weight=data.get('weight'),
                height=data.get('height'),
                volume=data.get('volume'),
                pregnancy_week=data.get('pregnancyWeek'),
                urgent=data.get('urgent', False)
            )
            
            # Prepare response data
            response_data = {
                'orderId': order_id,
                'orderName': order_name,
                'partnerId': partner_id,
                'patientCode': patient_code,
                'visitNumber': visit_number,
                'testCount': len(test_codes),
                'orderLines': order_line_ids
            }
            
            response_serializer = CreateOrderResponseSerializer(data=response_data)
            if response_serializer.is_valid():
                logger.info(f"/api/orders successfully created order {order_id} ({order_name}) with {len(test_codes)} tests")
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
            logger.error(f"/api/orders response serializer errors: {response_serializer.errors}")
            return Response(response_serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except ValueError as e:
            logger.error(f"/api/orders validation error: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"/api/orders error: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Failed to create order: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Patient'],
    parameters=[
        OpenApiParameter(
            name='categoryId',
            type=int,
            location=OpenApiParameter.QUERY,
            required=True,
            description='Lab test category ID'
        ),
        OpenApiParameter(
            name='maxResults',
            type=int,
            location=OpenApiParameter.QUERY,
            required=False,
            description='Maximum number of most recent test results (default: 5, max: 50)'
        ),
    ],
    responses={
        200: PivotTableResponseSerializer,
        400: None,
        401: None,
        404: None
    },
    description="""
    Generate a pivot table of lab order parameters for the authenticated patient.
    
    This endpoint retrieves lab order parameters for a specific category and converts them
    into a pivot table format with dates as columns and parameters as rows.
    
    **Query Parameters:**
    - `categoryId` (required): The lab test category ID to filter results
    - `maxResults` (optional): Maximum number of most recent test results to include (default: 5, max: 50)
    
    **Response Format:**
    - `categoryId`: The category ID
    - `categoryName`: Name of the category (localized)
    - `patientId`: Patient partner ID
    - `columns`: List of column definitions with laborder_id and date
    - `rows`: List of parameter rows with values for each date
    - `totalRows`: Total number of parameter rows
    
    **Example Response:**
    ```json
    {
        "categoryId": 123,
        "categoryName": "ზოგადი სისხლის ანალიზი",
        "patientId": 456,
        "columns": [
            {"laborderId": 1001, "date": "2024-01-15"},
            {"laborderId": 1002, "date": "2024-02-20"}
        ],
        "rows": [
            {
                "parameterIdUom": "10/1",
                "parameter": "ჰემოგლობინი,გ/ლ",
                "orderby": 1,
                "values": {"col_0": "145", "col_1": "148"}
            }
        ],
        "totalRows": 15
    }
    ```
    
    Requires patient JWT authentication.
    """
)
class GetPatientPivotTable(APIView):
    """
    Generate a pivot table of lab order parameters for the authenticated patient.
    Requires patient JWT authentication.
    """
    authentication_classes = [PatientJWTAuthentication]
    permission_classes = []

    def get(self, request):
        logger.info("/api/patient/pivot request")
        
        # Get personal_number from authenticated token
        if not request.auth:
            logger.error("/api/patient/pivot authentication failed: request.auth is None")
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        personal_number = request.auth.get('personal_number')
        
        # Get query parameters
        category_id = request.query_params.get('categoryId')
        max_results = request.query_params.get('maxResults', 5)
        
        # Validate categoryId
        if not category_id:
            logger.error("/api/patient/pivot missing categoryId parameter")
            return Response(
                {'error': 'categoryId parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            category_id = int(category_id)
        except ValueError:
            logger.error(f"/api/patient/pivot invalid categoryId: {category_id}")
            return Response(
                {'error': 'categoryId must be an integer'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate maxResults
        try:
            max_results = int(max_results)
            if max_results < 1 or max_results > 50:
                logger.error(f"/api/patient/pivot maxResults out of range: {max_results}")
                return Response(
                    {'error': 'maxResults must be between 1 and 50'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except ValueError:
            logger.error(f"/api/patient/pivot invalid maxResults: {max_results}")
            return Response(
                {'error': 'maxResults must be an integer'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        logger.info(f"/api/patient/pivot generating pivot for personal_number: {personal_number}, categoryId: {category_id}, maxResults: {max_results}")
        
        try:
            # Get preferred language from request (default to Georgian)
            lang = request.headers.get('Accept-Language', 'ka_GE')
            if lang not in ['ka_GE', 'en_US']:
                lang = 'ka_GE'
            
            pivot_data = generate_pivot_table(personal_number, category_id, max_results, lang)
            
            if pivot_data is None:
                logger.warning(f"/api/patient/pivot patient or category not found")
                return Response(
                    {'error': 'Patient or category not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            response_serializer = PivotTableResponseSerializer(data=pivot_data)
            if response_serializer.is_valid():
                logger.info(f"/api/patient/pivot generated pivot with {pivot_data['totalRows']} rows")
                return Response(response_serializer.data)
            
            logger.error(f"/api/patient/pivot serializer errors: {response_serializer.errors}")
            return Response(response_serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            logger.error(f"/api/patient/pivot error: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to generate pivot table'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
