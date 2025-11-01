"""
Custom OpenAPI schema extensions for DRF Spectacular.
"""
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class PatientJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """
    Map PatientJWTAuthentication to BearerAuth security scheme in OpenAPI.
    This extension automatically handles security requirements for endpoints
    using PatientJWTAuthentication.
    """
    target_class = 'api.authentication.PatientJWTAuthentication'
    name = 'BearerAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
            'description': 'JWT token obtained from /api/patient/check endpoint'
        }

    def get_security_requirement(self, auto_schema):
        return {self.name: []}
