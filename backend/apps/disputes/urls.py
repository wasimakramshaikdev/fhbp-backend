from django.urls import path
from apps.disputes.views import (
    AdminDisputeListView,
    AdminDisputeResolveView,
    CustomerCreateDisputeView,
)

urlpatterns = [
    path('admin/disputes/', AdminDisputeListView.as_view(), name='admin-disputes'),
    path('admin/disputes/<uuid:pk>/resolve/', AdminDisputeResolveView.as_view(), name='admin-resolve-dispute'),
    path('disputes/', CustomerCreateDisputeView.as_view(), name='customer-create-dispute'),
]
