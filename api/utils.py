import os
import subprocess
import traceback
import logging
from unittest import result
from xmlrpc import client as rpc_client
from typing import Generator
from contextlib import ExitStack

import psycopg2
from psycopg2.extensions import AsIs
from django.conf import settings
from django.db import connections
from django.utils import timezone

from datetime import datetime, timedelta

import uuid

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from .models import PatientToken

logger = logging.getLogger(__name__)

DATE_FORMAT = settings.DATE_FORMAT
DATETIME_FORMAT = settings.DATETIME_FORMAT

def get_oerp_connection():
    """
    Get Django database connection for OpenERP database.
    Uses Django's DATABASES configuration instead of hardcoded credentials.
    """
    return connections['openerp']

def get_patient_by_personal_number(personal_number):
    """
    Query OpenERP database for patient(s) by personal number.
    Returns a list of patient dictionaries with their details.
    
    Args:
        personal_number: 11-digit Georgian personal identification number
        
    Returns:
        List of dictionaries containing patient data, or empty list if not found
    """
    patients = []
    
    with get_oerp_connection().cursor() as cursor:
        sql = """
            SELECT id, inno_first_name, inno_last_name, inno_birthdate, 
                   street, mobile, email, inno_code
            FROM res_partner
            WHERE inno_id = %s AND inno_patient = true
        """
        cursor.execute(sql, (personal_number,))
        
        columns = ['id', 'first_name', 'last_name', 'date_of_birth', 
                  'address', 'mobile_phone', 'email', 'inno_code']
        
        for row in cursor.fetchall():
            patients.append(dict(zip(columns, row)))
    
    logger.debug(f"get_patient_by_personal_number({personal_number}) found {len(patients)} patient(s)")
    return patients


def check_patient_exists(personal_number, mobile_phone):
    """
    Check if a patient exists in OpenERP database with matching personal number and mobile phone.
    Handles multiple phone numbers separated by comma, semicolon, or period.
    
    Args:
        personal_number: 11-digit Georgian personal identification number
        mobile_phone: 9-digit mobile phone number (without country code)
        
    Returns:
        Boolean: True if patient exists with matching phone, False otherwise
    """
    with get_oerp_connection().cursor() as cursor:
        # Use regexp_split_to_table to handle comma/semicolon/period separated phone numbers
        sql = """
            SELECT COUNT(*) 
            FROM res_partner
            WHERE inno_id = %s 
              AND inno_patient = true
              AND EXISTS (
                  SELECT 1 
                  FROM regexp_split_to_table(trim(mobile), '[,;.]') AS phone
                  WHERE trim(phone) = %s
              )
        """
        cursor.execute(sql, (personal_number, mobile_phone))
        count = cursor.fetchone()[0]
    
    exists = count > 0
    logger.debug(f"check_patient_exists({personal_number}, {mobile_phone}) = {exists}")
    return exists

def get_labtests(labtest_id=None, active_only=False):
    id_sql = f' and pp.id = {labtest_id}' if labtest_id else ''
    active_sql = ' and pp.active' if active_only else ''

    with get_oerp_connection().cursor() as cursor:
        query = f"""
            select pp.id, pp.default_code as lis_code, pp.inno_code as ss_code, pp.name_template as name, pp.active, pt.list_price, pc.web_category_id
            from product_product pp
            join product_template pt on pp.product_tmpl_id = pt.id
            join product_category pc on pt.categ_id = pc.id
            where pp.inno_research_type = 'research' and pp.show_in_web = TRUE {active_sql} {id_sql}
        """
        logger.debug(f'get_labtests() SQL: {query}')
        cursor.execute(query)
        columns = [col[0] for col in cursor.description]
        res = [dict(zip(columns, row)) for row in cursor.fetchall()]
    return res


# New: Get all web_product_category records
def get_web_product_categories():
    with get_oerp_connection().cursor() as cursor:
        query = '''
            SELECT wpc.id, wpc.name, wpc.country_id, rc.name as country_name
            FROM web_product_category wpc
            LEFT JOIN res_country rc ON wpc.country_id = rc.id
            ORDER BY wpc.id
        '''
        logger.debug(f'get_web_product_categories() SQL: {query}')
        cursor.execute(query)
        columns = [col[0] for col in cursor.description]
        res = [dict(zip(columns, row)) for row in cursor.fetchall()]
    return res

# New: Get all product_product under a web_category (show_in_web only)
def get_labtests_by_web_category(web_category_id):
    with get_oerp_connection().cursor() as cursor:
        query = '''
            SELECT pp.id, pp.default_code as lis_code, pp.inno_code as ss_code, pp.name_template as name, pp.active, pt.list_price, pc.web_category_id
            FROM product_product pp
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            JOIN product_category pc ON pt.categ_id = pc.id
            WHERE pc.web_category_id = %s AND pp.show_in_web = TRUE AND pp.inno_research_type = 'research'
        '''
        logger.debug(f'get_labtests_by_web_category({web_category_id}) SQL: {query}')
        cursor.execute(query, (web_category_id,))
        columns = [col[0] for col in cursor.description]
        res = [dict(zip(columns, row)) for row in cursor.fetchall()]
    return res

def get_labtest_parameters(labtest_id):
    with get_oerp_connection().cursor() as cursor:
        sql = "select ip.abbr as code, ip.name \
            from inno_product_parameter ipp \
                join inno_parameter ip on ipp.parameter_id = ip.id \
            where ipp.product_id = %s"
        
        query = cursor.mogrify(sql, (labtest_id,))

        logger.debug('get_labtest_parameters() SQL: {query}')

        cursor.execute(query)
        columns = [col[0] for col in cursor.description]
        res = [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]

    return res

# ==================== JWT Token Management Functions ====================
def parse_device_name(user_agent):
    """
    Parse user agent string to extract friendly device name.
    Returns simplified device/browser name.
    """
    if not user_agent:
        return "Unknown Device"
    
    user_agent = user_agent.lower()
    
    # Browser detection
    browser = "Unknown Browser"
    if 'edg' in user_agent or 'edge' in user_agent:
        browser = "Edge"
    elif 'chrome' in user_agent and 'safari' in user_agent:
        browser = "Chrome"
    elif 'firefox' in user_agent:
        browser = "Firefox"
    elif 'safari' in user_agent:
        browser = "Safari"
    elif 'opera' in user_agent or 'opr' in user_agent:
        browser = "Opera"
    
    # OS detection
    os_name = "Unknown OS"
    if 'windows' in user_agent:
        os_name = "Windows"
    elif 'mac' in user_agent and 'iphone' not in user_agent and 'ipad' not in user_agent:
        os_name = "macOS"
    elif 'iphone' in user_agent:
        os_name = "iPhone"
    elif 'ipad' in user_agent:
        os_name = "iPad"
    elif 'android' in user_agent:
        os_name = "Android"
    elif 'linux' in user_agent:
        os_name = "Linux"
    
    return f"{browser} on {os_name}"


def generate_patient_tokens(personal_number, mobile_phone, client_ip=None, user_agent=None):
    """
    Generate access and refresh tokens for a patient.
    Creates a new session and stores tokens in PatientToken model.
    
    Args:
        personal_number: Patient's 11-digit personal identification number
        mobile_phone: Patient's 9-digit mobile phone number
        client_ip: IP address of the client (optional)
        user_agent: User agent string (optional)
        
    Returns:
        dict: {
            'access_token': str,
            'refresh_token': str,
            'access_expires_in': int (seconds),
            'refresh_expires_in': int (seconds),
            'session_id': str (UUID)
        }
    """
    # Generate a unique session ID for this token pair
    session_id = uuid.uuid4()
    
    # Parse device name from user agent
    device_name = parse_device_name(user_agent)
    
    # Create refresh token (which automatically creates access token)
    refresh = RefreshToken()
    
    # Add custom claims
    refresh['personal_number'] = personal_number
    refresh['mobile_phone'] = mobile_phone
    refresh['patient_type'] = 'patient'  # Use different claim name to avoid conflict
    refresh['session_id'] = str(session_id)  # Add session ID to token claims
    
    # Get access token from refresh
    access = refresh.access_token
    access['personal_number'] = personal_number
    access['mobile_phone'] = mobile_phone
    access['patient_type'] = 'patient'  # Use different claim name to avoid conflict
    access['session_id'] = str(session_id)
    
    # Calculate expiration times
    access_lifetime = settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']
    refresh_lifetime = settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME']
    
    now = timezone.now()
    access_expires_at = now + access_lifetime
    refresh_expires_at = now + refresh_lifetime
    
    # Store access token in database
    PatientToken.objects.create(
        jti=str(access['jti']),
        personal_number=personal_number,
        mobile_phone=mobile_phone,
        token_type='access',
        session_id=session_id,
        device_name=device_name,
        expires_at=access_expires_at,
        client_ip=client_ip,
        user_agent=user_agent
    )
    
    # Store refresh token in database
    PatientToken.objects.create(
        jti=str(refresh['jti']),
        personal_number=personal_number,
        mobile_phone=mobile_phone,
        token_type='refresh',
        session_id=session_id,
        device_name=device_name,
        expires_at=refresh_expires_at,
        client_ip=client_ip,
        user_agent=user_agent
    )
    
    logger.info(f"Generated tokens for patient {personal_number}, session_id={session_id}, device={device_name}")
    
    return {
        'access_token': str(access),
        'refresh_token': str(refresh),
        'access_expires_in': int(access_lifetime.total_seconds()),
        'refresh_expires_in': int(refresh_lifetime.total_seconds()),
        'session_id': str(session_id)
    }


def refresh_patient_token(refresh_token_string):
    """
    Refresh an access token using a refresh token.
    
    Args:
        refresh_token_string: The refresh token JWT string
        
    Returns:
        dict: {
            'access_token': str,
            'refresh_token': str (optional, if rotation enabled),
            'access_expires_in': int (seconds)
        }
        
    Raises:
        ValueError: If refresh token is invalid or revoked
    """
    try:
        # Decode the refresh token
        refresh = RefreshToken(refresh_token_string)
        refresh_jti = str(refresh['jti'])
        
        # Check if refresh token exists and is valid
        try:
            patient_token = PatientToken.objects.get(
                jti=refresh_jti,
                token_type='refresh'
            )
        except PatientToken.DoesNotExist:
            raise ValueError('Refresh token not found')
        
        if patient_token.is_revoked:
            raise ValueError(f'Refresh token has been revoked: {patient_token.revocation_reason}')
        
        if patient_token.expires_at < timezone.now():
            raise ValueError('Refresh token has expired')
        
        # Get patient data and session info from token
        personal_number = refresh.get('personal_number')
        mobile_phone = refresh.get('mobile_phone')
        session_id = refresh.get('session_id', patient_token.session_id)  # Preserve session_id
        
        # Generate new access token
        access = refresh.access_token
        access['personal_number'] = personal_number
        access['mobile_phone'] = mobile_phone
        access['patient_type'] = 'patient'  # Use different claim name to avoid conflict
        access['session_id'] = str(session_id)
        
        # Calculate expiration
        access_lifetime = settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']
        access_expires_at = timezone.now() + access_lifetime
        
        # Store new access token (preserve session_id and device info)
        PatientToken.objects.create(
            jti=str(access['jti']),
            personal_number=personal_number,
            mobile_phone=mobile_phone,
            token_type='access',
            session_id=patient_token.session_id,
            device_name=patient_token.device_name,
            expires_at=access_expires_at,
            client_ip=patient_token.client_ip,
            user_agent=patient_token.user_agent
        )
        
        result = {
            'access_token': str(access),
            'access_expires_in': int(access_lifetime.total_seconds())
        }
        
        # If token rotation is enabled, generate new refresh token
        if settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS', False):
            new_refresh = RefreshToken()
            new_refresh['personal_number'] = personal_number
            new_refresh['mobile_phone'] = mobile_phone
            new_refresh['patient_type'] = 'patient'  # Use different claim name to avoid conflict
            new_refresh['session_id'] = str(session_id)
            
            refresh_lifetime = settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME']
            refresh_expires_at = timezone.now() + refresh_lifetime
            
            # Store new refresh token (preserve session info)
            PatientToken.objects.create(
                jti=str(new_refresh['jti']),
                personal_number=personal_number,
                mobile_phone=mobile_phone,
                token_type='refresh',
                session_id=patient_token.session_id,
                device_name=patient_token.device_name,
                expires_at=refresh_expires_at,
                client_ip=patient_token.client_ip,
                user_agent=patient_token.user_agent
            )
            
            # Revoke old refresh token
            patient_token.revoke(reason='Token rotated')
            
            result['refresh_token'] = str(new_refresh)
        
        logger.info(f"Refreshed token for patient {personal_number}, session_id={session_id}")
        
        return result
        
    except TokenError as e:
        raise ValueError(f'Invalid refresh token: {str(e)}')


def revoke_patient_tokens(personal_number, reason=None):
    """
    Revoke all tokens for a patient.
    
    Args:
        personal_number: Patient's personal identification number
        reason: Optional reason for revocation
        
    Returns:
        int: Number of tokens revoked
    """
    count = PatientToken.revoke_all_for_patient(personal_number, reason)
    logger.info(f"Revoked {count} tokens for patient {personal_number}, reason: {reason}")
    return count


def cleanup_expired_tokens(days_old=30):
    """
    Clean up expired tokens older than specified days.
    Should be run periodically (e.g., daily cron job).
    
    Args:
        days_old: Delete tokens expired more than this many days ago
        
    Returns:
        int: Number of tokens deleted
    """
    cutoff_date = timezone.now() - timedelta(days=days_old)
    deleted_count = PatientToken.objects.filter(
        expires_at__lt=cutoff_date
    ).delete()[0]
    
    logger.info(f"Cleaned up {deleted_count} expired tokens older than {days_old} days")
    return deleted_count
