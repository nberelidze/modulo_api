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
    LabTestsList, LabTestDetail, LabTestPDFs, LabTestWebCategoriesList, LabTestWebCategoryDetail, LabTestParametersDetail,
    GetPatient, CheckPatientExists, RefreshPatientToken, RevokePatientTokens,
    GetPatientSessions, RevokePatientSession, GetPatientLabOrders, GetPatientLabOrderDetail, GetPatientLabOrderStats,
    CreatePatient, CreateOrder, GetPatientPivotTable
)

# Manual URL patterns for APIView classes
urlpatterns = [
    path('', RedirectView.as_view(url='/api/docs', permanent=False)),
    path('admin/', admin.site.urls),
    path('api/', include([
        # Lab tests
        path('labtests/', LabTestsList.as_view(), name='labtests'),
        path('labtests/<int:id>/', LabTestDetail.as_view(), name='labtest-detail'),
        path('labtests/<int:id>/pdfs/', LabTestPDFs.as_view(), name='labtest-pdfs'),
        path('labtest-categories/', LabTestWebCategoriesList.as_view(), name='labtest-categories'),
        path('labtest-category/<int:web_category_id>/', LabTestWebCategoryDetail.as_view(), name='labtest-category'),
        path('labtest-parameters/<int:id>/', LabTestParametersDetail.as_view(), name='labtest-parameters'),
        
        # Patient endpoints
        path('patient/', GetPatient.as_view(), name='patient'),
        path('patient/check/', CheckPatientExists.as_view(), name='patient-check'),
        path('patient/create/', CreatePatient.as_view(), name='patient-create'),
        path('patient/refresh/', RefreshPatientToken.as_view(), name='patient-refresh'),
        path('patient/revoke/', RevokePatientTokens.as_view(), name='patient-revoke'),
        path('patient/sessions/', GetPatientSessions.as_view(), name='patient-sessions'),
        path('patient/session/revoke/', RevokePatientSession.as_view(), name='patient-session-revoke'),
        path('patient/laborders/', GetPatientLabOrders.as_view(), name='patient-laborders'),
        path('patient/laborders/stats/', GetPatientLabOrderStats.as_view(), name='patient-laborders-stats'),
        path('patient/laborders/stats/<int:categ_id>/', GetPatientLabOrderStats.as_view(), name='patient-laborders-stats-category'),
        path('patient/laborders/<int:id>/', GetPatientLabOrderDetail.as_view(), name='patient-laborder-detail'),
        path('patient/pivot/', GetPatientPivotTable.as_view(), name='patient-pivot-table'),
        
        # Orders
        path('orders/', CreateOrder.as_view(), name='orders-create'),
        
        # API Documentation
        path('schema/', SpectacularAPIView.as_view(), name='schema'),
        path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    ])),
]
