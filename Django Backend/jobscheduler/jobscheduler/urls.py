from django.contrib import admin
from django.urls import path,include
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from django.views.generic import RedirectView 

schema_view = get_schema_view(
   openapi.Info(
      title="Job Scheduler API",
      default_version='v1',
      description="Job Scheduler API Documentation",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contact@jobscheduler.local"),
      license=openapi.License(name="BSD License"),
      
   ),
   public=True,
   permission_classes=[permissions.AllowAny],
)



urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('jobs.urls')), 
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0),name='schema-swagger-ui'),
    path('', RedirectView.as_view(url='/api/')),
]
