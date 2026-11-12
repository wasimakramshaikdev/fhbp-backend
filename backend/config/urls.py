from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path('django-admin/', admin.site.urls),
    
    # OpenAPI 3 Schema & Swagger UI
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # Core & Health Probes
    path('api/v1/', include('apps.core.urls')),
    
    # Domain APIs
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/', include('apps.halls.urls')),
    path('api/v1/', include('apps.availability.urls')),
    path('api/v1/', include('apps.bookings.urls')),
    path('api/v1/', include('apps.payments.urls')),
    path('api/v1/', include('apps.notifications.urls')),
    path('api/v1/', include('apps.reviews.urls')),
    path('api/v1/', include('apps.favorites.urls')),
    path('api/v1/', include('apps.dashboard.urls')),
    path('api/v1/', include('apps.disputes.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
