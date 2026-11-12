from django.urls import path
from apps.bookings.views import (
    BookingCreateIntentView,
    CustomerBookingListView,
    BookingDetailView,
    OwnerBookingListView,
    OwnerAcceptBookingView,
    OwnerRejectBookingView,
    ProcessBookingRefundView,
    CancelBookingView,
)

urlpatterns = [
    path('bookings/create-intent/', BookingCreateIntentView.as_view(), name='booking-create-intent'),
    path('bookings/', CustomerBookingListView.as_view(), name='customer-booking-list'),
    path('bookings/<uuid:pk>/', BookingDetailView.as_view(), name='booking-detail'),
    path('bookings/<uuid:pk>/accept/', OwnerAcceptBookingView.as_view(), name='booking-accept'),
    path('bookings/<uuid:pk>/reject/', OwnerRejectBookingView.as_view(), name='booking-reject'),
    path('bookings/<uuid:pk>/refund/', ProcessBookingRefundView.as_view(), name='booking-process-refund'),
    path('bookings/<uuid:pk>/cancel/', CancelBookingView.as_view(), name='booking-cancel'),

    # Owner Bookings
    path('owner/bookings/', OwnerBookingListView.as_view(), name='owner-booking-list'),
]
