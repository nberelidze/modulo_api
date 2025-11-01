"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

from rest_framework import routers

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from api.views import ( 
    LabTestsList, LabTestDetail, LabTestWebCategoriesList, LabTestWebCategoryDetail, LabTestParametersDetail,
    GetPatient, CheckPatientExists, RefreshPatientToken, RevokePatientTokens,
    GetPatientSessions, RevokePatientSession
)

# Manual URL patterns for APIView classes
urlpatterns = [
    path('', RedirectView.as_view(url='/api/docs', permanent=False)),
    path('admin/', admin.site.urls),
    path('api/', include([
        # Lab tests
        path('labtests/', LabTestsList.as_view(), name='labtests'),
        path('labtests/<int:id>/', LabTestDetail.as_view(), name='labtest-detail'),
        path('labtest-categories/', LabTestWebCategoriesList.as_view(), name='labtest-categories'),
        path('labtest-category/<web_category_id>/', LabTestWebCategoryDetail.as_view(), name='labtest-category'),
        path('labtest-parameters/<int:id>/', LabTestParametersDetail.as_view(), name='labtest-parameters'),
        
        # Patient endpoints
        path('patient/', GetPatient.as_view(), name='patient'),
        path('patient/check/', CheckPatientExists.as_view(), name='patient-check'),
        path('patient/refresh/', RefreshPatientToken.as_view(), name='patient-refresh'),
        path('patient/revoke/', RevokePatientTokens.as_view(), name='patient-revoke'),
        path('patient/sessions/', GetPatientSessions.as_view(), name='patient-sessions'),
        path('patient/session/revoke/', RevokePatientSession.as_view(), name='patient-session-revoke'),
        
        # API Documentation
        path('schema/', SpectacularAPIView.as_view(), name='schema'),
        path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    ])),
]
