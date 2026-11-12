from django.urls import path
from apps.availability.views import (
    HallMonthAvailabilityView,
    HallCheckAvailabilityView,
    HallBlockSlotView,
    HallUnblockSlotView
)

urlpatterns = [
    path('halls/<uuid:pk>/availability/', HallMonthAvailabilityView.as_view(), name='hall-month-availability'),
    path('halls/<uuid:pk>/availability/check/', HallCheckAvailabilityView.as_view(), name='hall-check-availability'),
    path('halls/<uuid:pk>/availability/block/', HallBlockSlotView.as_view(), name='hall-block-slot'),
    path('halls/<uuid:pk>/availability/unblock/', HallUnblockSlotView.as_view(), name='hall-unblock-slot'),
]
