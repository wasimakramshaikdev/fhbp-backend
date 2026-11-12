from rest_framework import serializers
from apps.disputes.models import Dispute, DisputeStatus, DisputeResolutionType
from apps.bookings.serializers import BookingListSerializer

class DisputeSerializer(serializers.ModelSerializer):
    booking_number = serializers.CharField(source='booking.booking_number', read_only=True)
    hall_name = serializers.CharField(source='booking.hall.name', read_only=True)
    customer_name = serializers.CharField(source='booking.customer.full_name', read_only=True)
    customer_email = serializers.CharField(source='booking.customer.email', read_only=True)
    owner_name = serializers.CharField(source='booking.hall.owner.full_name', read_only=True)
    total_amount = serializers.DecimalField(source='booking.total_amount', max_digits=12, decimal_places=2, read_only=True)
    amount_paid = serializers.DecimalField(source='booking.amount_paid', max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Dispute
        fields = [
            'id',
            'booking_id',
            'booking_number',
            'hall_name',
            'customer_name',
            'customer_email',
            'owner_name',
            'total_amount',
            'amount_paid',
            'reason',
            'description',
            'evidence_urls',
            'status',
            'resolution_type',
            'refund_amount',
            'admin_notes',
            'resolved_at',
            'created_at'
        ]


class DisputeCreateSerializer(serializers.Serializer):
    booking_id = serializers.UUIDField(required=True)
    reason = serializers.CharField(max_length=150, required=True)
    description = serializers.CharField(min_length=10, required=True)
    evidence_urls = serializers.ListField(child=serializers.URLField(), required=False, default=list)


class DisputeResolveSerializer(serializers.Serializer):
    resolution_type = serializers.ChoiceField(choices=DisputeResolutionType.choices, required=True)
    refund_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0.00)
    admin_notes = serializers.CharField(required=True, min_length=5)
