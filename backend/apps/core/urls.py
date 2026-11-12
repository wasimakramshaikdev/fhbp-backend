from django.urls import path
from apps.core.views import LivenessHealthCheckView, ReadinessHealthCheckView

urlpatterns = [
    path('health/', LivenessHealthCheckView.as_view(), name='health-check'),
    path('ready/', ReadinessHealthCheckView.as_view(), name='ready-check'),
]
