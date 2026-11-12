from datetime import datetime, timezone
from django.db.models import Avg, Count
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from apps.core.responses import api_response
from apps.core.pagination import StandardPagination
from apps.core.services.audit import AuditService
from apps.halls.models import Hall
from apps.bookings.models import Booking, BookingStatus
from apps.reviews.models import Review
from apps.reviews.serializers import ReviewSerializer, ReviewCreateSerializer, ReviewResponseSerializer
from apps.notifications.tasks import send_in_app_notification_task
from apps.notifications.models import NotificationType

class HallReviewListView(APIView):
    """
    Public paginated list of verified customer reviews for a function hall with rating distribution.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, pk_or_slug):
        import uuid
        is_uuid = False
        try:
            uuid.UUID(str(pk_or_slug))
            is_uuid = True
        except (ValueError, TypeError, AttributeError):
            is_uuid = False

        if is_uuid:
            hall = Hall.objects.filter(id=pk_or_slug).first()
        else:
            hall = Hall.objects.filter(slug=pk_or_slug).first()

        if not hall:
            return api_response(message="Venue not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

        reviews = Review.objects.filter(hall=hall, is_published=True).select_related('customer').order_by('-created_at')

        # Rating Distribution Statistics
        stats = {
            "avg_rating": float(hall.avg_rating),
            "review_count": hall.review_count,
            "distribution": {
                "5": reviews.filter(rating=5).count(),
                "4": reviews.filter(rating=4).count(),
                "3": reviews.filter(rating=3).count(),
                "2": reviews.filter(rating=2).count(),
                "1": reviews.filter(rating=1).count(),
            }
        }

        paginator = StandardPagination()
        page = paginator.paginate_queryset(reviews, request)
        serializer = ReviewSerializer(page, many=True)
        response = paginator.get_paginated_response(serializer.data)
        response.data['stats'] = stats
        return response


class SubmitBookingReviewView(APIView):
    """
    Customer submits a review on a verified COMPLETED booking.
    Strictly restricted to completed bookings and booking owner.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, booking_id):
        booking = Booking.objects.filter(id=booking_id).select_related('hall', 'hall__owner').first()
        if not booking:
            return api_response(message="Booking not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

        # 1. Authorization: must be customer who booked
        if booking.customer != request.user:
            return api_response(
                message="You can only review bookings made under your own account.",
                status_code=status.HTTP_403_FORBIDDEN,
                success=False
            )

        # 2. State Check: must be COMPLETED
        if booking.status != BookingStatus.COMPLETED:
            return api_response(
                message=f"Reviews are only permitted after your event has concluded (Current status: {booking.status}).",
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False
            )

        # 3. Duplicate check: only one review per booking
        if hasattr(booking, 'review') and booking.review:
            return api_response(
                message="You have already submitted a review for this booking.",
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False
            )

        serializer = ReviewCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return api_response(
                message="Review validation failed.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False
            )

        review = Review.objects.create(
            booking=booking,
            customer=request.user,
            hall=booking.hall,
            rating=serializer.validated_data['rating'],
            comment=serializer.validated_data['comment'],
            is_published=True
        )

        AuditService.log_action(
            actor=request.user,
            action="CUSTOMER_REVIEW_SUBMITTED",
            obj=review,
            changes={"rating": review.rating, "hall": booking.hall.name}
        )

        # Notify hall owner of new review
        send_in_app_notification_task.delay(
            user_id=str(booking.hall.owner.id),
            title=f"New {review.rating}★ Review on {booking.hall.name}",
            message=f"{request.user.full_name} left a review: \"{review.comment[:80]}...\"",
            notification_type=NotificationType.EVENT_COMPLETED,
            related_entity_type="Review",
            related_entity_id=str(review.id)
        )

        return api_response(
            data=ReviewSerializer(review).data,
            message="Thank you! Your verified review has been published.",
            status_code=status.HTTP_201_CREATED
        )


class OwnerRespondReviewView(APIView):
    """
    Hall Owner responds publicly to a customer review on their venue.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        review = Review.objects.filter(id=pk).select_related('hall', 'customer').first()
        if not review:
            return api_response(message="Review not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

        # Authorization: must be hall owner or admin
        if review.hall.owner != request.user and not request.user.is_admin:
            return api_response(
                message="You can only respond to reviews on your own venues.",
                status_code=status.HTTP_403_FORBIDDEN,
                success=False
            )

        serializer = ReviewResponseSerializer(data=request.data)
        if not serializer.is_valid():
            return api_response(errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST, success=False)

        review.owner_response = serializer.validated_data['owner_response']
        review.owner_responded_at = datetime.now(timezone.utc)
        review.save(update_fields=['owner_response', 'owner_responded_at'])

        AuditService.log_action(
            actor=request.user,
            action="OWNER_RESPONDED_TO_REVIEW",
            obj=review,
            changes={"response": review.owner_response}
        )

        return api_response(
            data=ReviewSerializer(review).data,
            message="Your response has been published."
        )


class OwnerReviewListView(APIView):
    """
    Lists all reviews across all venues owned by the authenticated owner.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reviews = Review.objects.filter(hall__owner=request.user).select_related('hall', 'customer').order_by('-created_at')
        paginator = StandardPagination()
        page = paginator.paginate_queryset(reviews, request)
        serializer = ReviewSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
