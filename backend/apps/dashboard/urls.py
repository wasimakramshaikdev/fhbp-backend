from django.urls import path
from apps.dashboard.views import OwnerDashboardOverviewView, OwnerEarningsView
from apps.dashboard.admin_views import (
    AdminDashboardOverviewView,
    AdminOwnerListView,
    AdminOwnerActionView,
    AdminBookingListView,
    AdminSettingsView,
    AdminAuditLogListView,
)

urlpatterns = [
    # Owner Dashboard
    path('owner/dashboard/', OwnerDashboardOverviewView.as_view(), name='owner-dashboard-overview'),
    path('owner/earnings/', OwnerEarningsView.as_view(), name='owner-earnings'),

    # Super Admin Control Plane
    path('admin/dashboard/', AdminDashboardOverviewView.as_view(), name='admin-dashboard-overview'),
    path('admin/owners/', AdminOwnerListView.as_view(), name='admin-owners'),
    path('admin/owners/<uuid:pk>/action/', AdminOwnerActionView.as_view(), name='admin-owner-action'),
    path('admin/bookings/', AdminBookingListView.as_view(), name='admin-bookings'),
    path('admin/settings/', AdminSettingsView.as_view(), name='admin-settings'),
    path('admin/audit-logs/', AdminAuditLogListView.as_view(), name='admin-audit-logs'),
]
