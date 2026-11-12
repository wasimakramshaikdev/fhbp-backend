from datetime import datetime, timezone
from decimal import Decimal
from django.db.models import Sum, Avg, Count, Q
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from apps.core.responses import api_response
from apps.accounts.permissions import IsOwnerRole
from apps.halls.models import Hall
from apps.bookings.models import Booking, BookingStatus
from apps.payouts.services.payout import PayoutService
from apps.notifications.models import Notification

class OwnerDashboardOverviewView(APIView):
    """
    Overview metrics and upcoming events table for the Hall Owner dashboard (Wireframe Screen 5).
    """
    permission_classes = [IsAuthenticated, IsOwnerRole]

    def get(self, request):
        owner = request.user
        now_utc = datetime.now(timezone.utc)
        current_year = now_utc.year
        current_month = now_utc.month

        # Owner Halls
        owner_halls = Hall.objects.filter(owner=owner)
        total_halls = owner_halls.count()
        avg_rating = owner_halls.aggregate(Avg('avg_rating'))['avg_rating__avg'] or 0.0

        # Pending Requests
        pending_requests_count = Booking.objects.filter(
            hall__owner=owner,
            status=BookingStatus.PENDING_OWNER_CONFIRMATION
        ).count()

        # Confirmed MTD Bookings
        confirmed_mtd = Booking.objects.filter(
            hall__owner=owner,
            status__in=[BookingStatus.CONFIRMED, BookingStatus.COMPLETED],
            created_at__year=current_year,
            created_at__month=current_month
        )
        confirmed_mtd_count = confirmed_mtd.count()
        revenue_mtd = confirmed_mtd.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')

        # Upcoming Events Table (Wireframe Screen 5)
        upcoming_bookings = Booking.objects.filter(
            hall__owner=owner,
            status__in=[BookingStatus.CONFIRMED, BookingStatus.PENDING_OWNER_CONFIRMATION],
            event_date__gte=now_utc.date()
        ).select_related('customer', 'hall').order_by('event_date')[:6]

        events_data = []
        for b in upcoming_bookings:
            events_data.append({
                "id": str(b.id),
                "booking_number": b.booking_number,
                "event_date": b.event_date.isoformat(),
                "time_slot": b.time_slot,
                "hall_name": b.hall.name,
                "customer_name": b.contact_name or b.customer.full_name,
                "guest_count": b.guest_count,
                "total_amount": float(b.total_amount),
                "advance_amount": float(b.advance_amount),
                "status": b.status,
                "status_display": "Awaiting your response" if b.status == BookingStatus.PENDING_OWNER_CONFIRMATION else "Confirmed",
            })

        # Unread notifications
        unread_notifs = Notification.objects.filter(user=owner, is_read=False).count()

        return api_response(data={
            "metrics": {
                "pending_requests": pending_requests_count,
                "confirmed_this_month": confirmed_mtd_count,
                "revenue_this_month": float(revenue_mtd),
                "avg_rating": round(float(avg_rating), 1),
                "total_venues": total_halls,
                "unread_notifications": unread_notifs,
            },
            "upcoming_events": events_data,
        })


class OwnerEarningsView(APIView):
    """
    Financial earnings, commission deductions (10%), and payout settlement schedule (Wireframe Screen 6).
    """
    permission_classes = [IsAuthenticated, IsOwnerRole]

    def get(self, request):
        data = PayoutService.get_owner_earnings_summary(request.user)
        return api_response(data=data)
