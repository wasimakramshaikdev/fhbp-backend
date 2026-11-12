from django.urls import path
from apps.reviews.views import (
    HallReviewListView,
    SubmitBookingReviewView,
    OwnerRespondReviewView,
    OwnerReviewListView,
)

urlpatterns = [
    path('halls/<str:pk_or_slug>/reviews/', HallReviewListView.as_view(), name='hall-reviews'),
    path('bookings/<uuid:booking_id>/review/', SubmitBookingReviewView.as_view(), name='submit-booking-review'),
    path('reviews/<uuid:pk>/respond/', OwnerRespondReviewView.as_view(), name='respond-review'),
    path('owner/reviews/', OwnerReviewListView.as_view(), name='owner-reviews'),
]
