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

import pandas as pd
from collections import OrderedDict

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

DATE_FORMAT = settings.DATE_FORMAT
DATETIME_FORMAT = settings.DATETIME_FORMAT

PDF_SERVER_URL = 'https://p.mrcheveli.com/'

# Cache for OpenERP XML-RPC connection parameters
_oerp_xmlrpc_cache = {}

def _get_oerp_xmlrpc_params():
    """
    Get cached OpenERP XML-RPC connection parameters.
    Caches the configuration to avoid repeated dictionary lookups.
    
    Returns:
        Tuple of (url, dbname, uid, password) for XML-RPC authentication
    """
    if not _oerp_xmlrpc_cache:
        config = settings.OERP_XMLRPC
        protocol = config['protocol']
        host = config['host']
        port = config['port']
        url = f"{protocol}{host}:{port}"
        
        # Authenticate and get user ID
        common = rpc_client.ServerProxy(f"{url}/xmlrpc/common")
        uid = common.authenticate(
            config['dbname'],
            config['username'],
            config['password'],
            {}
        )
        
        _oerp_xmlrpc_cache.update({
            'url': url,
            'dbname': config['dbname'],
            'uid': uid,
            'password': config['password']
        })
        logger.debug(f"Cached OpenERP XML-RPC parameters for {url}")
    
    return (
        _oerp_xmlrpc_cache['url'],
        _oerp_xmlrpc_cache['dbname'],
        _oerp_xmlrpc_cache['uid'],
        _oerp_xmlrpc_cache['password']
    )

# Deprecated and unnecessary function, should be removed
def _normalize_oerp(value):
    """
    OpenERP v7 returns boolean False for any unset field over XML-RPC.
    Recursively convert False → None so serializers receive a proper null.
    """
    if value is False:
        return None
    if isinstance(value, dict):
        return {k: _normalize_oerp(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_oerp(v) for v in value]
    return value


def oerp_execute(*args):
    """
    Execute an XML-RPC call to OpenERP v7 server.
    Uses cached connection parameters for efficiency.
    
    Args:
        *args: Arguments to pass to the OpenERP execute method
               Typically: model_name, method_name, [ids], {parameters}
    
    Returns:
        Result from the OpenERP XML-RPC call
        
    Example:
        # Search for partners
        partner_ids = oerp_execute('res.partner', 'search', [('inno_patient', '=', True)])
        
        # Read partner data
        partners = oerp_execute('res.partner', 'read', partner_ids, ['name', 'email'])
    """
    try:
        url, dbname, uid, password = _get_oerp_xmlrpc_params()
        models = rpc_client.ServerProxy(f"{url}/xmlrpc/object")
        result = models.execute_kw(dbname, uid, password, *args)
        logger.debug(f"oerp_execute({args[0]}, {args[1]}) successful")
        return result
    except Exception as e:
        logger.error(f"oerp_execute failed: {e}")
        # Clear cache on authentication errors to allow retry
        if 'authentication' in str(e).lower() or 'login' in str(e).lower():
            _oerp_xmlrpc_cache.clear()
            logger.info("Cleared XML-RPC cache due to authentication error")
        raise

def get_partner_sequence_value(sex):
    """
    Get the next sequence value for patient code based on gender.
    Uses OpenERP ir.sequence via XML-RPC.
    
    Args:
        sex: Gender ('male' or 'female')
        
    Returns:
        int: Next sequence value for the patient code
        
    Raises:
        ValueError: If sequence not found or sex is invalid
    """
    sequence_name = 'Male Patients' if sex == 'male' else 'Female Patients'
    
    try:
        # Search for the sequence by name
        sequence_ids = oerp_execute('ir.sequence', 'search', [[('name', '=', sequence_name)]])
        
        if not sequence_ids:
            raise ValueError(f"Sequence '{sequence_name}' not found in OpenERP")
        
        sequence_id = sequence_ids[0]
        
        # Get the next value from the sequence
        # In OpenERP v7, next_by_id expects [sequence_id] as a list
        next_value = oerp_execute('ir.sequence', 'next_by_id', [sequence_id])
        
        logger.debug(f"get_partner_sequence_value({sex}) = {next_value}")
        return next_value  # Return as string since that's what the sequence returns
        
    except Exception as e:
        logger.error(f"Failed to get sequence value for {sex}: {e}")
        raise

def create_partner(first_name, last_name, birth_date, sex, personal_number, name=None):
    """
    Create a new patient in OpenERP res.partner via XML-RPC.
    Generates patient code based on gender and sequence.
    
    Args:
        first_name: Patient's first name
        last_name: Patient's last name
        birth_date: Date of birth (YYYY-MM-DD format or date object)
        sex: Gender ('male' or 'female')
        personal_number: 11-digit Georgian personal identification number
        name: Optional full name (defaults to "first_name last_name")
        
    Returns:
        tuple: (partner_id, inno_code)
            partner_id: ID of the created partner in OpenERP
            inno_code: Generated patient code (e.g., 'XY12345' or 'XX67890')
            
    Raises:
        ValueError: If sex is invalid or sequence not found
        Exception: If partner creation fails
        
    Example:
        partner_id, code = create_partner('John', 'Doe', '1990-01-15', 'male', '01234567890')
        # Returns: (12345, 'XY12345')
    """
    # Validate sex
    if sex not in ('male', 'female'):
        raise ValueError(f"Invalid sex value: {sex}. Must be 'male' or 'female'")
    
    # Generate patient code
    # code_prefix = 'XY' if sex == 'male' else 'XX'
    # inno_raw_code = get_partner_sequence_value(sex)
    # inno_code = f'{code_prefix}{inno_raw_code}'

    inno_code = get_partner_sequence_value(sex)
    
    # Prepare partner data
    partner = {
        'name': name or f'{first_name} {last_name}',
        'inno_last_name': last_name,
        'inno_first_name': first_name,
        'inno_birthdate': str(birth_date) if birth_date else False,
        'inno_gender': sex,
        'inno_patient': True,
        'inno_code': inno_code,
        'inno_id': personal_number,
    }
    
    try:
        # Create partner via XML-RPC
        # execute_kw expects the values dictionary to be wrapped in a list
        partner_id = oerp_execute('res.partner', 'create', [partner])
        logger.info(f"Created partner {partner_id} with code {inno_code} for {personal_number}")
        return partner_id, inno_code
        
    except Exception as e:
        logger.error(f"Failed to create partner for {personal_number}: {e}")
        raise

def get_or_create_patient(personal_number, first_name=None, last_name=None, birth_date=None, sex=None, name=None):
    """
    Get existing patient by personal number or create a new one if it doesn't exist.
    
    Args:
        personal_number: 11-digit Georgian personal identification number
        first_name: Patient's first name (required for creation)
        last_name: Patient's last name (required for creation)
        birth_date: Date of birth (required for creation)
        sex: Gender ('male' or 'female', required for creation)
        name: Optional full name
        
    Returns:
        tuple: (partner_id, patient_code, created)
            partner_id: ID of the partner in OpenERP
            patient_code: Patient code (inno_code)
            created: Boolean indicating if patient was newly created
    """
    # First try to find existing patient
    patients = get_patient_by_personal_number(personal_number)
    
    if patients:
        # Patient exists, return the first one
        patient = patients[0]
        logger.info(f"Found existing patient {patient['id']} with code {patient.get('inno_code')} for {personal_number}")
        return patient['id'], patient.get('inno_code'), False
    
    # Patient doesn't exist, create new one
    if not all([first_name, last_name, birth_date, sex]):
        raise ValueError("First name, last name, date of birth, and sex are required to create a new patient")
    
    partner_id, patient_code = create_partner(
        first_name=first_name,
        last_name=last_name,
        birth_date=birth_date,
        sex=sex,
        personal_number=personal_number,
        name=name
    )
    
    logger.info(f"Created new patient {partner_id} with code {patient_code} for {personal_number}")
    return partner_id, patient_code, True

def create_sale_order(partner_id, visit_number, test_codes, order_date=None, weight=None, height=None, 
                      volume=None, pregnancy_week=None, urgent=False):
    """
    Create a sale order in OpenERP with lab tests.
    
    Args:
        partner_id: OpenERP partner ID
        visit_number: Visit/reference number for the order
        test_codes: List of test codes (matching product.product.default_code)
        order_date: Order date (defaults to now)
        weight: Patient weight
        height: Patient height
        volume: Sample volume
        pregnancy_week: Pregnancy week
        urgent: Whether the order is urgent
        
    Returns:
        tuple: (order_id, order_name, order_line_ids)
            order_id: ID of the created sale order
            order_name: Sale order number/name
            order_line_ids: List of created order line IDs
            
    Raises:
        ValueError: If test code not found or other validation errors
        Exception: If order creation fails
    """
    try:
        # Find products by test codes
        product_ids = []
        product_map = {}
        
        for test_code in test_codes:
            # Search for product by default_code
            products = oerp_execute('product.product', 'search', [[('default_code', '=', test_code)]])
            
            if not products:
                raise ValueError(f"Test code '{test_code}' not found in product catalog")
            
            product_id = products[0]
            product_ids.append(product_id)
            product_map[test_code] = product_id
        
        logger.info(f"Found {len(product_ids)} products for test codes: {test_codes}")
        
        # Prepare sale order data
        order_data = {
            'partner_id': partner_id,
            'inno_refcode': visit_number,
            'api_call': True,
            'date_order': order_date.strftime('%Y-%m-%d %H:%M:%S') if order_date else False,
        }
        
        # Add optional fields if provided
        if weight:
            order_data['inno_weight'] = weight
        if height:
            order_data['inno_height'] = height
        if volume:
            order_data['inno_volume'] = volume
        if pregnancy_week is not None:
            order_data['inno_pregnancy_week'] = pregnancy_week
        if urgent:
            order_data['inno_urgent'] = urgent
        
        # Create the sale order
        order_id = oerp_execute('sale.order', 'create', [order_data])
        logger.info(f"Created sale order {order_id} for partner {partner_id}, visit number: {visit_number}")
        
        # Get the order name
        order_info = oerp_execute('sale.order', 'read', [order_id], ['name'])
        order_name = order_info[0]['name'] if order_info else str(order_id)
        
        # Create order lines for each test
        order_line_ids = []
        for test_code in test_codes:
            product_id = product_map[test_code]
            
            # Get product info for pricing
            product_info = oerp_execute('product.product', 'read', [product_id], ['list_price', 'name'])
            
            if product_info:
                product_price = product_info[0].get('list_price', 0.0)
                product_name = product_info[0].get('name', test_code)
            else:
                product_price = 0.0
                product_name = test_code
            
            # Create order line
            line_data = {
                'order_id': order_id,
                'product_id': product_id,
                'name': product_name,
                'product_uom_qty': 1,
                'price_unit': product_price,
            }
            
            line_id = oerp_execute('sale.order.line', 'create', [line_data])
            order_line_ids.append(line_id)
            logger.debug(f"Created order line {line_id} for product {product_id} ({test_code})")
        
        logger.info(f"Created sale order {order_id} ({order_name}) with {len(order_line_ids)} order lines")
        return order_id, order_name, order_line_ids
        
    except Exception as e:
        logger.error(f"Failed to create sale order: {e}")
        raise

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


def get_parameter_abnormal_indicator(row):
    """
    Determine if a lab test parameter value is below, above, or within the normal range.
    
    Args:
        row: Dictionary containing 'value', 'value_min', 'value_max', and 'include' keys
    Returns:
        String: 'down' if value is below min, 'up' if value is above max, 'ast' for some textual values, None if value is within range, None if value is None
    """
    value = row.get('value')
    value_min = row.get('value_min')
    value_max = row.get('value_max')
    boundary_include = row.get('include', False)
    value_text = row.get('value_text')
    value_text_ref = row.get('value_text_ref')
    value_text_arrow = row.get('value_text_arrow')

    comment = row.get('comment')
    comment_en = row.get('commenten')

    # '!' has the highest priority, value_text has priority over numeric value for determining abnormality

    if (comment and '!' in comment) or (comment_en and '!' in comment_en):
        return 'exclam'  # Highest priority indicator for abnormal result

    # If value_text is present and indicates an abnormal result, use value_text_arrow
    if value_text is not None and value_text_arrow is not None:
        return value_text_arrow  # Expecting value_text_arrow to be 'up', 'down', or 'ast'

    if value_text_ref is not None and value_text is not None and value_text != value_text_ref:
        return 'ast'  # Asterisk indicator for abnormal textual value
    
    if value is None:
        return None

    retval = None
    if value_min is not None and (value_min != 0) and ((boundary_include and value < value_min) or (not boundary_include and value <= value_min)):
        retval = 'down'
    elif value_max is not None and (value_max != 0) and ((boundary_include and value > value_max) or (not boundary_include and value >= value_max)):
        retval = 'up'
    
    return retval

def generate_reference_range(row):

    value_min = row.get('value_min')
    value_max = row.get('value_max')
    include_boundaries = row.get('include', False)

    has_value_min = value_min is not None and value_min != 0
    has_value_max = value_max is not None and value_max != 0
    
    if include_boundaries:
        less_sign = '≤'
        greater_sign = '≥'
    else:
        less_sign = '<'
        greater_sign = '>'

    if not has_value_min and not has_value_max:
        return "-"
    elif not has_value_min:
        return f"{less_sign} {value_max}"
    elif not has_value_max:
        return f"{greater_sign} {value_min}"
    elif value_min < value_max:
        # return f"{value_min} {less_sign} x {less_sign} {value_max}"
        return f"{value_min} - {value_max}"
    else:
        return 'Error'

def get_lab_orders(personal_number, laborder_id=None, include_parameters=False):
    """
    Query OpenERP database for lab orders by patient's personal number.
    Joins inno_laborder with res_partner to filter by personal number.
    Optionally fetches a single order with parameters.
    
    Args:
        personal_number: 11-digit Georgian personal identification number
        laborder_id: Optional ID of specific lab order to retrieve
        include_parameters: If True, includes parameters from inno_laborder_parameter
        
    Returns:
        If laborder_id is provided: Single dictionary with lab order data (or None if not found)
        Otherwise: List of dictionaries containing lab order data, or empty list if not found
    """
    with get_oerp_connection().cursor() as cursor:
        # Build WHERE clause
        where_clauses = ["rp.inno_id = %(personal_number)s", "rp.inno_patient = true", "lo.create_date >= '2020-01-01'", "lo.state = 'done'"]

        # comment_inside and comment_inside_en are only shown for certain categories (parent_id in 15 (ადგილობრივი), 35 (ფილიალები))
        LOCAL_CATEGORY_PARENT_IDS = (15, 35)
        # categories for which has_details must always be false regardless of parameters present
        # 1.	6 – PAP
        # 2.	58- PAP
        # 3.	94 – PCR/PAP
        # 4.	65 - ადგილობრივი/PAP
        # 5.	157 - Limbach/გენ
        # 6.	17 - გენეტიკა
        # 7.	53 - გენეტიკა
        # 8.	102 - გენეტიკა/პანელი
        # 9.	50 - ლაბორატორია / გენეტიკა
        # 10.	21- პათომორფოლოგია
        # 11.	51 - მორფოლოგია
        # 12.	74 - ადგილობრივი მორფოლოგია
        # 13.	75 - ადგილობრივი მორფოლოგია
        # 14.	77 – morfologia
        # 15.	80 - მორფოლოგიური კვლევები

        NO_DETAILS_CATEGORY_IDS = (238,6,58,59,94,65,157,17,53,102,50,21,51,74,75,77,80)
        NO_PDF_CATEGORY_IDS     = (    6,58,59,94,65,157,17,53,102,50,21,51,74,75,77,80)

        params_dict = {
            'personal_number': personal_number,
            'laborder_id': laborder_id,
            'local_category_parent_ids': LOCAL_CATEGORY_PARENT_IDS,
            'no_details_category_ids': NO_DETAILS_CATEGORY_IDS,
        }

        if laborder_id:
            where_clauses.append("lo.id = %(laborder_id)s")

        sql = f"""
            WITH category_map AS (
                SELECT
                    CASE WHEN wupc.id IS NOT NULL THEN wupc.id ELSE pc.id END AS id,
                    pc.id as pc_categ_id,
                    pc.parent_id as parent_id,
                    CASE WHEN wupc.id IS NOT NULL THEN wupc.name ELSE pc.name END AS name,
                    CASE WHEN wupc.id IS NOT NULL THEN 'web.user.portal.category,name' ELSE 'product.category,name' END AS it_translation_name
                FROM product_category pc
                LEFT JOIN web_user_portal_category wupc
                    ON wupc.id = pc.web_user_portal_category_id
            )
            SELECT 
                lo.id,
                lo.name,
                lo.state,
                --lo.shop_id,
                lo.date_order,
                --lo.partner_id,
                --lo.add_id,
                --lo.inno_height,
                --lo.inno_weight,
                lo.categ_id as categ_id,
                cm.id as user_portal_categ_id,
                cm.name as user_portal_categ_name,
                it.value as user_portal_categ_name_geo,
                lo.date_done,
                --lo.print_urin,
                --lo.active,
                CASE WHEN cm.parent_id IN %(local_category_parent_ids)s THEN lo.comment_inside ELSE NULL END as comment_inside,
                CASE WHEN cm.parent_id IN %(local_category_parent_ids)s THEN lo.comment_inside_en ELSE NULL END as comment_inside_en,
                --lo.cap_blood,
                --lo.erythrocyte,
                --lo.not_read,
                lo.create_date,
                lo.write_date,
                CASE WHEN lo.categ_id IN %(no_details_category_ids)s THEN false ELSE EXISTS (
                    SELECT 1 FROM inno_laborder_parameter lp 
                    WHERE lp.laborder_id = lo.id AND lp.active
                ) END as has_details,
                (
                    SELECT string_agg(
                        concat_ws(',', NULLIF(ip.name, ''), NULLIF(it_kw.value, ''), NULLIF(ip.abbr, '')),
                        ', '
                    )
                    FROM inno_laborder_parameter lp
                    JOIN inno_parameter ip ON lp.parameter_id = ip.id
                    LEFT JOIN ir_translation it_kw ON it_kw.res_id = ip.id
                        AND it_kw.lang = 'ka_GE' AND it_kw."type" = 'model' AND it_kw.name = 'inno.parameter,name'
                    WHERE lp.laborder_id = lo.id AND lp.active
                ) as meta_keywords,
                isa.name as pregnancy_week,
                it_add.value as pregnancy_week_geo
            FROM inno_laborder lo
                JOIN res_partner rp ON lo.partner_id = rp.id
                LEFT JOIN category_map cm ON cm.pc_categ_id = lo.categ_id
                LEFT JOIN ir_translation it ON it.res_id = cm.id 
                    AND it.lang = 'ka_GE' 
                    AND it.name = cm.it_translation_name
                LEFT JOIN inno_standard_add isa ON isa.id = lo.add_id
                LEFT JOIN ir_translation it_add ON it_add.res_id = isa.id 
                    AND it_add.name = 'inno.standard.add,name'
                    AND it_add.lang = 'ka_GE' 
                    AND it_add.module is null
            WHERE {' AND '.join(where_clauses)}
            ORDER BY lo.date_order DESC NULLS LAST, lo.id DESC
        """
        cursor.execute(sql, params_dict)

        
        columns = [col[0] for col in cursor.description]
        
        if laborder_id:
            # Single order
            row = cursor.fetchone()
            if not row:
                logger.debug(f"get_lab_orders({personal_number}, {laborder_id}) not found or access denied")
                return None
            
            lab_order = dict(zip(columns, row))
            
            # Fetch parameters if requested
            if include_parameters:
                sql_params = """
                    SELECT 
                        lp.id,
                        lp.parameter_id,
                        ip.name as parameter_name,
                        it.value as parameter_name_geo,
                        ip.abbr as parameter_abbr,
                        -- lp.research_id,
                        -- pp.name_template as research_name,
                        lp.value,
                        lp.value_min,
                        lp.value_max,
                        lp.include,
                        itx.name as value_text,
                        it2.value as value_text_geo,
                        itx2.name as value_text_ref,
                        it3.value as value_text_ref_geo,
                        itx.arrow as value_text_arrow,
                        --lp.value_auto,
                        --lp.value_1,
                        --lp.value_2,
                        --lp.value_3,
                        --lp.text_value,
                        --lp.value_text_auto,
                        lp.uom_id,
                        pu.name as uom_name,
                        it_uom.value as uom_name_geo,
                        lp.state,
                        lp.comment,
                        lp.commenten,
                        --lp.date_value,
                        lp.sequence,
                        --lp.is_printable,
                        --lp.do_not_print,
                        --lp.instrument_id,
                        lp.instrument_name,
                        --lp.default_instrument_code,
                        lp.updated_at,
                        --lp.updated_by
                        mat_pp.id as material_id,
                        pt.name as material_name,
                        it_mat.value as material_name_geo
                    FROM inno_laborder_parameter lp
                        LEFT JOIN inno_parameter ip ON lp.parameter_id = ip.id
                            LEFT JOIN ir_translation it on it.res_id = ip.id and it.lang = 'ka_GE' and it."type" = 'model' and it.name = 'inno.parameter,name'
                        --LEFT JOIN product_product pp ON lp.research_id = pp.id
                        LEFT JOIN product_uom pu ON lp.uom_id = pu.id
                            LEFT JOIN ir_translation it_uom on it_uom.res_id = pu.id and it_uom.lang = 'ka_GE' and it_uom."type" = 'model' and it_uom.name = 'product.uom,name'
                        LEFT JOIN inno_textvalue itx on itx.id = lp.value_text
                            LEFT JOIN ir_translation it2 on it2.res_id = itx.id and it2.lang = 'ka_GE' and it2."type" = 'model' and it2.name = 'inno.textvalue,name'
                        LEFT JOIN inno_textvalue itx2 on itx2.id = lp.text_value
                            LEFT JOIN ir_translation it3 on it3.res_id = itx2.id and it3.lang = 'ka_GE' and it3."type" = 'model' and it3.name = 'inno.textvalue,name'
                        JOIN inno_laborder_material ilm on ilm.laborder_id = lp.laborder_id and ilm.research_id = lp.research_id
                            JOIN product_product mat_pp ON mat_pp.id = ilm.material_id
                            JOIN product_template pt on pt.id = mat_pp.product_tmpl_id
                            LEFT JOIN ir_translation it_mat on it_mat.res_id = pt.id and it_mat.lang = 'ka_GE' and it_mat."type" = 'model' and it_mat.name = 'product.template,name'

                   WHERE lp.active and lp.laborder_id = %s
                    ORDER BY lp.sequence NULLS LAST, lp.id
                """
                cursor.execute(sql_params, (laborder_id,))
                
                param_columns = [col[0] for col in cursor.description]
                param_columns.append('abnormal_indicator')  # Add computed field to columns list
                param_columns.append('reference_range')  # Add computed field to columns list
                parameters = []
                for param_row in cursor.fetchall():
                    param_dict = dict(zip(param_columns, param_row))
                    param_dict['abnormal_indicator'] = get_parameter_abnormal_indicator(param_dict)
                    param_dict['reference_range'] = generate_reference_range(param_dict)
                    parameters.append(param_dict)

                lab_order['parameters'] = parameters
                
                logger.debug(f"get_lab_orders({personal_number}, {laborder_id}) found order with {len(parameters)} parameter(s)")
            else:
                logger.debug(f"get_lab_orders({personal_number}, {laborder_id}) found order")
            
            if lab_order['categ_id'] in NO_PDF_CATEGORY_IDS:
                lab_order['pdf_files'] = []  # No PDFs for this category
            else:
                # Fetch associated PDFs from modulo_document_registry
                sql_pdfs = """
                    SELECT uuid, store_fname, name, comment
                    FROM modulo_document_registry
                    WHERE res_model = 'inno.laborder'
                    AND res_id = %s
                    AND state = 'published'
                    ORDER BY create_date
                """
                cursor.execute(sql_pdfs, (laborder_id,))
                pdf_columns = [col[0] for col in cursor.description]
                lab_order['pdf_files'] = [
                    {**dict(zip(pdf_columns, row)), 'url': PDF_SERVER_URL + (row[1] or '')}
                    for row in cursor.fetchall()
                ]
            
            return lab_order
        else:
            # Multiple orders
            lab_orders = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            if lab_orders:
                laborder_ids = [o['id'] for o in lab_orders if o['categ_id'] not in NO_PDF_CATEGORY_IDS]
                sql_pdfs = """
                    SELECT uuid, store_fname, name, comment, res_id
                    FROM modulo_document_registry
                    WHERE res_model = 'inno.laborder'
                      AND res_id = ANY(%s)
                      AND state = 'published'
                    ORDER BY create_date
                """
                cursor.execute(sql_pdfs, (laborder_ids,))
                pdfs_by_order = {}
                for pdf_row in cursor.fetchall():
                    pdf_uuid, store_fname, pdf_name, pdf_comment, pdf_res_id = pdf_row
                    pdfs_by_order.setdefault(pdf_res_id, []).append({
                        'uuid': pdf_uuid,
                        'store_fname': store_fname,
                        'name': pdf_name,
                        'comment': pdf_comment,
                        'url': PDF_SERVER_URL + (store_fname or ''),
                    })
                for order in lab_orders:
                    order['pdf_files'] = pdfs_by_order.get(order['id'], [])
            
            logger.debug(f"get_lab_orders({personal_number}) found {len(lab_orders)} lab order(s)")
            return lab_orders


def get_lab_order_detail(personal_number, laborder_id):
    """
    Query OpenERP database for a single lab order with its parameters.
    
    Deprecated: Use get_lab_orders(personal_number, laborder_id, include_parameters=True) instead.
    This function is kept for backward compatibility.
    
    Args:
        personal_number: 11-digit Georgian personal identification number
        laborder_id: ID of the lab order to retrieve
        
    Returns:
        Dictionary containing lab order data with nested parameters list, or None if not found
    """
    return get_lab_orders(personal_number, laborder_id, include_parameters=True)


def get_lab_order_stats(personal_number, categ_id=None):
    """
    Query OpenERP database for lab order statistics by patient's personal number.
    Returns aggregated parameter data across all completed lab orders.
    
    Args:
        personal_number: 11-digit Georgian personal identification number
        categ_id: Optional category ID to filter lab orders by category
        
    Returns:
        List of dictionaries containing lab order statistics, or empty list if not found
    """
    with get_oerp_connection().cursor() as cursor:
        # First get the partner_id for this personal number
        sql_partner = """
            SELECT id FROM res_partner 
            WHERE inno_id = %s AND inno_patient = true
            LIMIT 1
        """
        cursor.execute(sql_partner, (personal_number,))
        partner_row = cursor.fetchone()
        
        if not partner_row:
            logger.debug(f"get_lab_order_stats({personal_number}) patient not found")
            return []
        
        partner_id = partner_row[0]
        
        # Build WHERE clause with optional category filter
        where_clauses = ["ilp.partner_id = %s", "ilp.active", "il.state = 'done'"]
        params = [partner_id]
        
        if categ_id is not None:
            where_clauses.append("il.categ_id = %s")
            params.append(categ_id)
        
        # Now run the stats query
        sql = f"""
            SELECT 
                ilp.laborder_id,
                il.categ_id, pc.name as categ_name_eng, it2.value as categ_name_geo,
                date(ilp.date_value) as date, 
                concat_ws('/', ilp.parameter_id, ilp.uom_id) as param_id_uom, 
                concat_ws(',', coalesce(it.value, ip.name), nullif(pu.name, '.')) as parameter,
                coalesce(nullif(ilp.value, 0)::text, itv.name) as value, 
                ilp.sequence as orderby
            FROM inno_laborder_parameter ilp
            JOIN inno_laborder il ON ilp.laborder_id = il.id
                LEFT JOIN product_category pc ON il.categ_id = pc.id
                LEFT JOIN inno_textvalue itv ON ilp.value_text = itv.id
                LEFT JOIN inno_parameter ip ON ilp.parameter_id = ip.id
                LEFT JOIN product_uom pu ON ilp.uom_id = pu.id
                LEFT JOIN ir_translation it ON it.res_id = ip.id 
                    AND it.lang = 'ka_GE' 
                    AND it.name = 'inno.parameter,name'
                LEFT JOIN ir_translation it2 ON it2.res_id = pc.id 
                    AND it2.lang = 'ka_GE' 
                    AND it2.name = 'product.category,name'
            WHERE {' AND '.join(where_clauses)}
            ORDER BY il.categ_id, ilp.date_value, ilp.laborder_id
        """
        cursor.execute(sql, params)
        
        columns = [col[0] for col in cursor.description]
        stats = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        logger.debug(f"get_lab_order_stats({personal_number}, categ_id={categ_id}) found {len(stats)} stat record(s)")
        return stats

def get_labtests_rpc(labtest_id=None, web_category_id=None, active_only=False):
    kw_dict = {}
    if labtest_id:
        kw_dict['product_id'] = labtest_id
    if web_category_id:
        kw_dict['web_category_id'] = web_category_id
        
    oerp_tests = oerp_execute('product.product', 'get_web_products_data', [], kw_dict)

    logger.info(f"get_labtests_rpc() retrieved {len(oerp_tests)} tests from OpenERP with filters: {kw_dict}")
    logger.debug(f"get_labtests_rpc() raw data: {oerp_tests}")

    for i, test in enumerate(oerp_tests):
        oerp_tests[i]['subtests'] = oerp_execute('product.product', 'get_child_product_names', [test['id'], 'ka_GE'])
        logger.info(f"get_labtests_rpc() test ID {test['id']} has {len(oerp_tests[i]['subtests'])} subtests")
        logger.debug(f"get_labtests_rpc() test ID {test['id']} subtests data: {oerp_tests[i]['subtests']}")
    
    return oerp_tests

def get_labtests(labtest_id=None, active_only=False):
    id_sql = f' and pp.id = {labtest_id}' if labtest_id else ''
    active_sql = ' and pp.active' if active_only else ''

    with get_oerp_connection().cursor() as cursor:
        query = f"""
        select pp.id, pp.default_code as lis_code, pp.inno_code as ss_code, 
            pp.name_template as name, it1.value as name_geo,
            pp.active, pt.list_price, pc.web_category_id, pp.preparation_notes, it2.value as preparation_notes_geo, wpc.country_id, 
            rc.name as country_name, it.value as country_name_geo
        from product_product pp
            join product_template pt on pp.product_tmpl_id = pt.id
            join product_category pc on pt.categ_id = pc.id
            join web_product_category wpc on wpc.id = pc.web_category_id 
            left join res_country rc ON wpc.country_id = rc.id
            left join ir_translation it on it.res_id = rc.id and it.lang = 'ka_GE' and it."type" = 'model' and it.name = 'res.country,name'
            left join ir_translation it1 on it1.res_id = pt.id and it1.lang = 'ka_GE' and it1."type" = 'model' and it1.name = 'product.template,name'
            left join ir_translation it2 on it2.res_id = pt.id and it2.lang = 'ka_GE' and it2."type" = 'model' and it2.name = 'product.product,preparation_notes'
        where pp.inno_research_type = 'research' and pp.show_in_web = TRUE  {active_sql} {id_sql}
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
            SELECT wpc.id, wpc.name, it1.value as name_geo, wpc.country_id, rc.name as country_name, it.value as country_name_geo
            FROM web_product_category wpc
            LEFT JOIN res_country rc ON wpc.country_id = rc.id
            LEFT JOIN ir_translation it on it.res_id = rc.id and it.lang = 'ka_GE' and it."type" = 'model' and it.name = 'res.country,name'
            LEFT JOIN ir_translation it1 on it1.res_id = wpc.id and it1.lang = 'ka_GE' and it1."type" = 'model' and it1.name = 'web.product.category,name'
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
            SELECT pp.id, pp.default_code as lis_code, pp.inno_code as ss_code, 
            pp.name_template as name, it1.value as name_geo,
            pp.active, pt.list_price, pc.web_category_id, pp.preparation_notes, it2.value as preparation_notes_geo, wpc.country_id, rc.name as country_name, it.value as country_name_geo
            FROM product_product pp
                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                JOIN product_category pc ON pt.categ_id = pc.id
                join web_product_category wpc on wpc.id = pc.web_category_id 
                left join res_country rc ON wpc.country_id = rc.id
                left join ir_translation it on it.res_id = rc.id and it.lang = 'ka_GE' and it."type" = 'model' and it.name = 'res.country,name'
                left join ir_translation it1 on it1.res_id = pt.id and it1.lang = 'ka_GE' and it1."type" = 'model' and it1.name = 'product.template,name'
                left join ir_translation it2 on it2.res_id = pt.id and it2.lang = 'ka_GE' and it2."type" = 'model' and it2.name = 'product.product,preparation_notes'
            WHERE pc.web_category_id = %s AND pp.show_in_web = TRUE AND pp.inno_research_type = 'research'
        '''
        logger.debug(f'get_labtests_by_web_category({web_category_id}) SQL: {query}')
        cursor.execute(query, (web_category_id,))
        columns = [col[0] for col in cursor.description]
        res = [dict(zip(columns, row)) for row in cursor.fetchall()]
    return res

def get_labtest_parameters(labtest_id):
    with get_oerp_connection().cursor() as cursor:
        sql = '''select ip.abbr as code, ip.name, it.value as name_geo \
            from inno_product_parameter ipp \
                join inno_parameter ip on ipp.parameter_id = ip.id \
                left join ir_translation it on it.res_id = ip.id and it.lang = 'ka_GE' and it."type" = 'model' and it.name = 'inno.parameter,name' \
            where ipp.product_id = %s'''
        
        query = cursor.mogrify(sql, (labtest_id,))

        logger.debug(f'get_labtest_parameters() SQL: {query}')

        cursor.execute(query)
        columns = [col[0] for col in cursor.description]
        res = [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]

    return res

def get_labtest_pdfs(labtest_id):
    """
    Fetch the English and Georgian PDF attachments for a lab test directly from the DB.
    bytea columns are base64-encoded before returning so the result is JSON-safe.
    Returns a dict with keys: pdf_eng, pdf_eng_filename, pdf_geo, pdf_geo_filename.
    Any missing PDF column is returned as None.
    """
    with get_oerp_connection().cursor() as cursor:
        cursor.execute(
            """
            SELECT inno_pdf_eng, inno_pdf_eng_filename,
                   inno_pdf_geo, inno_pdf_geo_filename
            FROM product_product
            WHERE id = %s
            """,
            (labtest_id,),
        )
        row = cursor.fetchone()

    if row is None:
        return None

    # Data is already stored as base64 text inside the bytea column.
    # Use str(memoryview, 'ascii') to decode directly without an intermediate bytes copy.
    
    # Uncomment _to_str if one prefers to a helper function for clarity, but it's only used 2 times so inlining is also fine.
    # def _to_str(v): return str(v, 'ascii') if v is not None else None
    
    return {
        'pdf_eng': str(row[0], 'ascii') if row[0] is not None else None,
        'pdf_eng_filename': row[1],
        'pdf_geo': str(row[2], 'ascii') if row[2] is not None else None,
        'pdf_geo_filename': row[3],
    }

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


def generate_pivot_table(personal_number, category_id, max_results=5, lang='ka_GE'):
    """
    Generate a pivot table of lab order parameters for a patient.
    Converts lab order parameters into a pivot table with dates as columns and parameters as rows.
    
    Args:
        personal_number: 11-digit Georgian personal identification number
        category_id: Lab test category ID to filter results
        max_results: Maximum number of most recent test results to include (default: 5)
        lang: Language code for translations (default: 'ka_GE')
        
    Returns:
        Dictionary containing:
        - categoryId: The category ID
        - categoryName: Name of the category
        - patientId: Patient partner ID
        - columns: List of column definitions [{laborder_id, date}, ...]
        - rows: List of parameter rows with values [{parameter, orderby, values: {...}}, ...]
        - totalRows: Total number of parameter rows
        
        Returns None if patient not found or no data available
    """

    with get_oerp_connection().cursor() as cursor:
        # First get the partner_id for this personal number
        sql_partner = """
            SELECT id FROM res_partner 
            WHERE inno_id = %s AND inno_patient = true
            LIMIT 1
        """
        cursor.execute(sql_partner, (personal_number,))
        partner_row = cursor.fetchone()
        
        if not partner_row:
            logger.debug(f"generate_pivot_table({personal_number}) patient not found")
            return None
        
        partner_id = partner_row[0]
        
        # Check if the category is CBC (includes special date filter in OpenERP)
        sql_categ = """
            SELECT pc.name, pc.inno_abbr, it.value as name_geo
            FROM product_category pc
            LEFT JOIN ir_translation it ON it.res_id = pc.id 
                AND it.lang = %s 
                AND it.name = 'product.category,name'
            WHERE pc.id = %s
        """
        cursor.execute(sql_categ, (lang, category_id))
        categ_row = cursor.fetchone()
        
        if not categ_row:
            logger.debug(f"generate_pivot_table() category {category_id} not found")
            return None
        
        categ_name_eng, categ_abbr, categ_name_geo = categ_row
        categ_name = categ_name_geo if categ_name_geo else categ_name_eng
        
        is_cbc_test = 'CBC' in categ_abbr if categ_abbr else False
        cbc_date_filter = "AND il.date_order > '2024-09-01'" if is_cbc_test else ''
        
        # Query lab order parameters
        sql_params = f"""
            SELECT 
                ilp.laborder_id, 
                DATE(ilp.date_value) as date, 
                CONCAT_WS('/', ilp.parameter_id, ilp.uom_id) as param_id_uom, 
                CONCAT_WS(',', COALESCE(it.value, ip.name), NULLIF(pu.name, '.')) as parameter,
                COALESCE(NULLIF(ilp.value, 0)::text, itv.name) as value, 
                ilp.sequence as orderby
            FROM inno_laborder_parameter ilp
            JOIN inno_laborder il ON ilp.laborder_id = il.id
            LEFT JOIN inno_textvalue itv ON ilp.value_text = itv.id
            LEFT JOIN inno_parameter ip ON ilp.parameter_id = ip.id
            LEFT JOIN product_uom pu ON ilp.uom_id = pu.id
            LEFT JOIN ir_translation it ON it.res_id = ip.id 
                AND it.lang = %s 
                AND it.name = 'inno.parameter,name'
            WHERE ilp.partner_id = %s 
                AND ilp.active
                AND il.categ_id = %s
                AND il.state = 'done'
                {cbc_date_filter}
            ORDER BY ilp.date_value, ilp.laborder_id
        """
        cursor.execute(sql_params, (lang, partner_id, category_id))
        
        # Fetch results into a pandas DataFrame
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        
        if not rows:
            logger.debug(f"generate_pivot_table() no data found for partner_id={partner_id}, category_id={category_id}")
            return {
                'categoryId': category_id,
                'categoryName': categ_name,
                'patientId': partner_id,
                'columns': [],
                'rows': [],
                'totalRows': 0
            }
        
        raw_df = pd.DataFrame(rows, columns=columns)
        
        # Create pivot table
        pivot_df = pd.pivot_table(
            raw_df, 
            values='value', 
            index=['param_id_uom', 'parameter', 'orderby'], 
            columns=['laborder_id', 'date'], 
            aggfunc=lambda x: x, 
            fill_value='-'
        )
        
        # Keep last N results
        pivot_df = pivot_df.iloc[:, -max_results:]
        
        if pivot_df.empty:
            logger.debug(f"generate_pivot_table() pivot table is empty")
            return {
                'categoryId': category_id,
                'categoryName': categ_name,
                'patientId': partner_id,
                'columns': [],
                'rows': [],
                'totalRows': 0
            }
        
        # Build columns list (dates)
        columns_list = []
        laborder_id_map = {}
        
        for idx, col_tuple in enumerate(pivot_df.columns):
            laborder_id, date = col_tuple
            columns_list.append({
                'laborderId': int(laborder_id),
                'date': str(date)
            })
            laborder_id_map[laborder_id] = idx
        
        # Convert pivot to dictionary and build rows
        pivot_dict = pivot_df.where(pd.notnull(pivot_df), None).to_dict(orient='index', into=OrderedDict)
        
        rows_list = []
        for param_tuple, param_data in pivot_dict.items():
            param_id_uom, parameter_name, orderby = param_tuple
            
            # Build values dict for this parameter across all dates
            values = {}
            for col_tuple, value in param_data.items():
                laborder_id, date = col_tuple
                col_idx = laborder_id_map[laborder_id]
                values[f'col_{col_idx}'] = value
            
            rows_list.append({
                'parameterIdUom': param_id_uom,
                'parameter': parameter_name,
                'orderby': int(orderby) if orderby is not None else 999,
                'values': values
            })
        
        result = {
            'categoryId': category_id,
            'categoryName': categ_name,
            'patientId': partner_id,
            'columns': columns_list,
            'rows': rows_list,
            'totalRows': len(rows_list)
        }
        
        logger.debug(f"generate_pivot_table() generated pivot with {len(columns_list)} columns and {len(rows_list)} rows")
        return result

