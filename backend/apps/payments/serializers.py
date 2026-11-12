from rest_framework import serializers
from apps.payments.models import Payment, Refund, PaymentType, PaymentMethod, PaymentStatus

class PaymentInitiateSerializer(serializers.Serializer):
    booking_id = serializers.UUIDField(required=True)
    payment_type = serializers.ChoiceField(choices=PaymentType.choices, default=PaymentType.ADVANCE)
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices, default=PaymentMethod.UPI)


class PaymentVerifySerializer(serializers.Serializer):
    gateway_order_id = serializers.CharField(required=True)
    gateway_payment_id = serializers.CharField(required=True)
    gateway_signature = serializers.CharField(required=True)


class PaymentListSerializer(serializers.ModelSerializer):
    booking_number = serializers.CharField(source='booking.booking_number', read_only=True)
    hall_name = serializers.CharField(source='booking.hall.name', read_only=True)
    event_date = serializers.DateField(source='booking.event_date', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id',
            'payment_reference',
            'booking_id',
            'booking_number',
            'hall_name',
            'event_date',
            'amount',
            'currency',
            'payment_type',
            'payment_method',
            'status',
            'gateway',
            'gateway_payment_id',
            'paid_at',
            'created_at'
        ]


class RefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = [
            'id',
            'refund_reference',
            'payment_id',
            'booking_id',
            'amount',
            'currency',
            'reason',
            'status',
            'gateway_refund_id',
            'created_at'
        ]
