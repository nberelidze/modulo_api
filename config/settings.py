from .django_settings import *

import environ
from datetime import timedelta

env = environ.Env()

env.read_env('.env/django.env')
env.read_env('.env/oerp.env')

# OpenERP XML-RPC Configuration
OERP_XMLRPC = {
    'username': env('OERP_USERNAME', default='admin'),
    'password': env('OERP_PASSWORD', default='admin'),
    'dbname': env('OERP_DBNAME', default='modulo'),
    'host': env('OERP_HOST', default='192.168.0.1'),
    'port': env('OERP_PORT', default=8069),
    'protocol': env('OERP_PROTOCOL', default='http://'),
    'pdf_location': env('OERP_PDF_LOCATION', default='/pdf/1/'),
}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    },
    # 'default': {
    #     'ENGINE': env('DATABASE_ENGINE', default='django.db.backends.postgresql'),
    #     'NAME': env('DATABASE_NAME'),
    #     'USER': env('DATABASE_USER'),
    #     'PASSWORD': env('DATABASE_PASSWORD'),
    #     'HOST': env('DATABASE_HOST'),
    #     'PORT': env('DATABASE_PORT'),
    # },
    'openerp': {
        'ENGINE': env('OERP_DATABASE_ENGINE', default='django.db.backends.postgresql'),
        'NAME': env('OERP_DATABASE_NAME'),
        'USER': env('OERP_DATABASE_USER'),
        'PASSWORD': env('OERP_DATABASE_PASSWORD'),
        'HOST': env('OERP_DATABASE_HOST'),
        'PORT': env('OERP_DATABASE_PORT', default='5432'),
    },
    # 'sqlite': {
    #     'ENGINE': 'django.db.backends.sqlite3',
    #     'NAME': BASE_DIR / 'db.sqlite3',
    # }
}

# JWT Authentication Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=env.int('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', default=60*24)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=env.int('JWT_REFRESH_TOKEN_LIFETIME_DAYS', default=7)),
    'ROTATE_REFRESH_TOKENS': True,  # Issue new refresh token on refresh
    'BLACKLIST_AFTER_ROTATION': False,  # We handle revocation in PatientToken model
    'UPDATE_LAST_LOGIN': False,
    
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': 'limsproxy-doctra',
    
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    
    'JTI_CLAIM': 'jti',  # JWT ID for tracking
    
    # We'll add custom claims for patient data
    'TOKEN_USER_CLASS': None,  # We're not using Django users
}

# REST Framework settings - add JWT authentication
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'api.authentication.PatientJWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend'
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# DRF Spectacular settings for Swagger/OpenAPI
SPECTACULAR_SETTINGS = {
    'TITLE': 'LIMS Proxy API',
    'DESCRIPTION': 'Laboratory Information Management System Proxy API',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SWAGGER_UI_SETTINGS': {
        'persistAuthorization': True,
    },
}
