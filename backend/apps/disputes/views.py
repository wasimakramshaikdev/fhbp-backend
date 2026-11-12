from datetime import datetime, timezone
from decimal import Decimal
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from apps.core.responses import api_response
from apps.core.pagination import StandardPagination
from apps.core.services.audit import AuditService
from apps.accounts.permissions import IsAdminRole
from apps.bookings.models import Booking, BookingStatus
from apps.disputes.models import Dispute, DisputeStatus, DisputeResolutionType
from apps.disputes.serializers import DisputeSerializer, DisputeCreateSerializer, DisputeResolveSerializer
from apps.payments.services.payment import PaymentService
from apps.payouts.models import Payout, PayoutStatus

class AdminDisputeListView(APIView):
    """
    Super Admin listing of all platform dispute cases.
    """
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        status_filter = request.query_params.get('status')
        queryset = Dispute.objects.all().select_related('booking', 'booking__hall', 'booking__customer', 'booking__hall__owner').order_by('-created_at')

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = DisputeSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminDisputeResolveView(APIView):
    """
    Super Admin settles a dispute: issues refund to customer or releases funds to owner.
    """
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        dispute = Dispute.objects.filter(id=pk).select_related('booking', 'booking__hall', 'booking__customer').first()
        if not dispute:
            return api_response(message="Dispute case not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

        serializer = DisputeResolveSerializer(data=request.data)
        if not serializer.is_valid():
            return api_response(errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST, success=False)

        resolution = serializer.validated_data['resolution_type']
        refund_amount = serializer.validated_data.get('refund_amount', Decimal('0.00'))
        admin_notes = serializer.validated_data['admin_notes']

        with transaction.atomic():
            booking = dispute.booking

            if resolution == DisputeResolutionType.CUSTOMER_REFUND:
                refund_amount = booking.amount_paid
                successful_payment = booking.payments.filter(status='SUCCESS').first()
                if successful_payment:
                    PaymentService.execute_refund(
                        payment_id=str(successful_payment.id),
                        amount=refund_amount,
                        reason=f"Dispute #{str(dispute.id)[:8]} resolved in favor of customer",
                        actor=request.user
                    )
                # Put owner payout on hold/cancel
                Payout.objects.filter(booking=booking).update(status=PayoutStatus.FAILED, failure_reason="Dispute resolved in customer favor")

            elif resolution == DisputeResolutionType.PARTIAL_REFUND:
                successful_payment = booking.payments.filter(status='SUCCESS').first()
                if successful_payment and refund_amount > 0:
                    PaymentService.execute_refund(
                        payment_id=str(successful_payment.id),
                        amount=refund_amount,
                        reason=f"Dispute #{str(dispute.id)[:8]} partial settlement",
                        actor=request.user
                    )

            elif resolution == DisputeResolutionType.OWNER_FAVORED:
                booking.status = BookingStatus.COMPLETED
                booking.save(update_fields=['status'])
                # Release payout
                Payout.objects.filter(booking=booking).update(status=PayoutStatus.SCHEDULED)

            dispute.status = DisputeStatus.RESOLVED
            dispute.resolution_type = resolution
            dispute.refund_amount = refund_amount
            dispute.admin_notes = admin_notes
            dispute.resolved_by = request.user
            dispute.resolved_at = datetime.now(timezone.utc)
            dispute.save()

            AuditService.log_action(
                actor=request.user,
                action="ADMIN_RESOLVED_DISPUTE",
                obj=dispute,
                changes={"resolution": resolution, "refund": str(refund_amount), "notes": admin_notes}
            )

            return api_response(
                data=DisputeSerializer(dispute).data,
                message=f"Dispute resolved successfully with '{resolution}'."
            )


class CustomerCreateDisputeView(APIView):
    """
    Customer lodges a formal dispute on a confirmed or completed booking.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DisputeCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return api_response(errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST, success=False)

        booking_id = serializer.validated_data['booking_id']
        booking = Booking.objects.filter(id=booking_id).first()
        if not booking:
            return api_response(message="Booking not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

        if booking.customer != request.user:
            return api_response(message="You can only dispute your own bookings.", status_code=status.HTTP_403_FORBIDDEN, success=False)

        if hasattr(booking, 'dispute') and booking.dispute:
            return api_response(message="A dispute has already been filed for this booking.", status_code=status.HTTP_400_BAD_REQUEST, success=False)

        with transaction.atomic():
            dispute = Dispute.objects.create(
                booking=booking,
                opened_by=request.user,
                reason=serializer.validated_data['reason'],
                description=serializer.validated_data['description'],
                evidence_urls=serializer.validated_data.get('evidence_urls', []),
                status=DisputeStatus.OPEN
            )

            booking.status = BookingStatus.DISPUTED
            booking.save(update_fields=['status'])

            # Put owner payout on hold during dispute investigation
            Payout.objects.filter(booking=booking).update(status=PayoutStatus.ON_HOLD)

            AuditService.log_action(
                actor=request.user,
                action="DISPUTE_FILED",
                obj=dispute,
                changes={"booking": booking.booking_number, "reason": dispute.reason}
            )

            return api_response(
                data=DisputeSerializer(dispute).data,
                message="Dispute lodged successfully. Our platform compliance team will review all claims within 24 hours.",
                status_code=status.HTTP_201_CREATED
            )
