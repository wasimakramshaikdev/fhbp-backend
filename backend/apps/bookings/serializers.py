# from rest_framework import serializers
# from apps.bookings.models import Booking, BookingStatus, EventType
# from apps.availability.models import TimeSlot
# from apps.halls.serializers import HallListSerializer

# class BookingCreateIntentSerializer(serializers.Serializer):
#     hall_id = serializers.UUIDField(required=True)
#     event_type = serializers.ChoiceField(choices=EventType.choices, default=EventType.WEDDING)
#     event_date = serializers.DateField(required=True)
#     time_slot = serializers.ChoiceField(choices=TimeSlot.choices, required=True)
#     guest_count = serializers.IntegerField(required=True, min_value=1)
#     contact_name = serializers.CharField(max_length=150, required=True)
#     contact_phone = serializers.CharField(max_length=20, required=True)
#     special_requests = serializers.CharField(required=False, allow_blank=True, default="")
#     has_catering = serializers.BooleanField(required=False, default=False)
#     catering_type = serializers.ChoiceField(choices=['VEG', 'NON_VEG'], required=False, default='VEG')
#     has_decor = serializers.BooleanField(required=False, default=False)
#     has_dj = serializers.BooleanField(required=False, default=False)


# class BookingListSerializer(serializers.ModelSerializer):
#     hall_name = serializers.CharField(source='hall.name', read_only=True)
#     hall_slug = serializers.CharField(source='hall.slug', read_only=True)
#     hall_locality = serializers.CharField(source='hall.locality', read_only=True)
#     hall_city = serializers.CharField(source='hall.city', read_only=True)
#     primary_image = serializers.CharField(source='hall.primary_image', read_only=True)
#     customer_name = serializers.CharField(source='customer.full_name', read_only=True)
#     customer_email = serializers.CharField(source='customer.email', read_only=True)

#     class Meta:
#         model = Booking
#         fields = [
#             'id',
#             'booking_number',
#             'hall_id',
#             'hall_name',
#             'hall_slug',
#             'hall_locality',
#             'hall_city',
#             'primary_image',
#             'customer_name',
#             'customer_email',
#             'event_type',
#             'event_date',
#             'time_slot',
#             'guest_count',
#             'total_amount',
#             'advance_amount',
#             'balance_amount',
#             'amount_paid',
#             'status',
#             'created_at'
#         ]


# class BookingDetailSerializer(serializers.ModelSerializer):
#     hall = HallListSerializer(read_only=True)
#     customer_name = serializers.CharField(source='customer.full_name', read_only=True)
#     customer_email = serializers.CharField(source='customer.email', read_only=True)
#     customer_phone = serializers.CharField(source='customer.phone', read_only=True)

#     class Meta:
#         model = Booking
#         fields = [
#             'id',
#             'booking_number',
#             'customer_id',
#             'customer_name',
#             'customer_email',
#             'customer_phone',
#             'contact_name',
#             'contact_phone',
#             'hall',
#             'event_type',
#             'event_date',
#             'time_slot',
#             'guest_count',
#             'special_requests',
#             'has_catering',
#             'catering_plate_type',
#             'catering_plate_price',
#             'has_decor',
#             'has_dj',
#             'hall_rent',
#             'catering_amount',
#             'decor_amount',
#             'dj_amount',
#             'subtotal',
#             'discount_amount',
#             'tax_rate',
#             'tax_amount',
#             'total_amount',
#             'advance_percentage',
#             'advance_amount',
#             'balance_amount',
#             'amount_paid',
#             'status',
#             'owner_response_notes',
#             'cancellation_reason',
#             'cancellation_fee',
#             'refund_amount',
#             'expires_at',
#             'created_at',
#             'updated_at'
#         ]


# class BookingOwnerDecisionSerializer(serializers.Serializer):
#     notes = serializers.CharField(required=False, allow_blank=True, default="")


# class BookingCancellationSerializer(serializers.Serializer):
#     reason = serializers.CharField(required=True)


# from rest_framework import serializers

# from apps.bookings.models import Booking, EventType
# from apps.availability.models import TimeSlot
# from apps.halls.serializers import HallListSerializer
# from django.utils import timezones
# from datetime import timedelta

# MIN_BOOKING_NOTICE_DAYS = 1
# MAX_ADVANCE_BOOKING_DAYS = 180

# class BookingCreateIntentSerializer(serializers.Serializer):
#     hall_id = serializers.UUIDField(
#         required=True,
#     )

#     event_type = serializers.ChoiceField(
#         choices=EventType.choices,
#         default=EventType.WEDDING,
#     )

#     event_date = serializers.DateField(
#         required=True,
#     )

#     time_slot = serializers.ChoiceField(
#         choices=TimeSlot.choices,
#         required=True,
#     )

#     guest_count = serializers.IntegerField(
#         required=True,
#         min_value=1,
#     )

#     contact_name = serializers.CharField(
#         max_length=150,
#         required=True,
#     )

#     contact_phone = serializers.CharField(
#         max_length=20,
#         required=True,
#     )

#     special_requests = serializers.CharField(
#         required=False,
#         allow_blank=True,
#         default="",
#     )

#     has_catering = serializers.BooleanField(
#         required=False,
#         default=False,
#     )

#     catering_type = serializers.ChoiceField(
#         choices=["VEG", "NON_VEG"],
#         required=False,
#         default="VEG",
#     )

#     has_decor = serializers.BooleanField(
#         required=False,
#         default=False,
#     )

#     has_dj = serializers.BooleanField(
#         required=False,
#         default=False,
#     )

#     def validate_event_date(self, value):
#         if value < timezone.localdate():
#             raise serializers.ValidationError(
#                "Event date cannot be in the past."
#             )
#         return value


#     def validate_event_date(self, value):
#         today = timezone.localdate()


#         earliest_allowed_date = (
#             today + timedelta(days=MIN_BOOKING_NOTICE_DAYS)
#         )

#         latest_allowed_date = (
#             today + timedelta(days=MAX_ADVANCE_BOOKING_DAYS)
#         )

#         if value < earliest_allowed_date:
#             raise serializers.ValidationError(
#                 f"Bookings must be made at least "
#                 f"{MIN_BOOKING_NOTICE_DAYS} day in advance."
#             )

#         if value > latest_allowed_date:
#              raise serializers.ValidationError(
#                 f"Bookings can only be made up to "
#                 f"{MAX_ADVANCE_BOOKING_DAYS} days in advance."
#             )

#         return value


#     def validate(self, attrs):
#         hall = attrs.get("hall")
#         event_date = attrs.get("event_date")

#         if hall and event_date:
#             if not Booking.is_date_available(
#                 hall_id=hall.id,
#                 event_date=event_date,
#             ):
#             raise serializers.ValidationError({
#                 "event_date": [
#                     "This hall is already booked for the selected date."
#                 ]
#             })

#     return attrs


# class BookingListSerializer(serializers.ModelSerializer):
#     hall_name = serializers.CharField(
#         source="hall.name",
#         read_only=True,
#     )

#     hall_slug = serializers.CharField(
#         source="hall.slug",
#         read_only=True,
#     )

#     hall_locality = serializers.CharField(
#         source="hall.locality",
#         read_only=True,
#     )

#     hall_city = serializers.CharField(
#         source="hall.city",
#         read_only=True,
#     )

#     primary_image = serializers.CharField(
#         source="hall.primary_image",
#         read_only=True,
#     )

#     customer_name = serializers.CharField(
#         source="customer.full_name",
#         read_only=True,
#     )

#     customer_email = serializers.CharField(
#         source="customer.email",
#         read_only=True,
#     )

#     class Meta:
#         model = Booking

#         fields = [
#             "id",
#             "booking_number",
#             "hall_id",
#             "hall_name",
#             "hall_slug",
#             "hall_locality",
#             "hall_city",
#             "primary_image",
#             "customer_name",
#             "customer_email",
#             "event_type",
#             "event_date",
#             "time_slot",
#             "guest_count",
#             "total_amount",
#             "advance_amount",
#             "balance_amount",
#             "amount_paid",
#             "status",
#             "created_at",
#         ]


# class BookingDetailSerializer(serializers.ModelSerializer):
#     hall = HallListSerializer(
#         read_only=True,
#     )

#     customer_name = serializers.CharField(
#         source="customer.full_name",
#         read_only=True,
#     )

#     customer_email = serializers.CharField(
#         source="customer.email",
#         read_only=True,
#     )

#     customer_phone = serializers.CharField(
#         source="customer.phone",
#         read_only=True,
#     )

#     class Meta:
#         model = Booking

#         fields = [
#             "id",
#             "booking_number",
#             "customer_id",
#             "customer_name",
#             "customer_email",
#             "customer_phone",
#             "contact_name",
#             "contact_phone",
#             "hall",
#             "event_type",
#             "event_date",
#             "time_slot",
#             "guest_count",
#             "special_requests",
#             "has_catering",
#             "catering_plate_type",
#             "catering_plate_price",
#             "has_decor",
#             "has_dj",
#             "hall_rent",
#             "catering_amount",
#             "decor_amount",
#             "dj_amount",
#             "subtotal",
#             "discount_amount",
#             "tax_rate",
#             "tax_amount",
#             "total_amount",
#             "advance_percentage",
#             "advance_amount",
#             "balance_amount",
#             "amount_paid",
#             "status",
#             "owner_response_notes",
#             "cancellation_reason",
#             "cancellation_fee",
#             "refund_amount",
#             "expires_at",
#             "created_at",
#             "updated_at",
#         ]


# class BookingOwnerDecisionSerializer(serializers.Serializer):
#     notes = serializers.CharField(
#         required=False,
#         allow_blank=True,
#         default="",
#     )


# class BookingCancellationSerializer(serializers.Serializer):
#     reason = serializers.CharField(
#         required=True,
#     )



# from datetime import timedelta

# from django.utils import timezone
# from rest_framework import serializers

# from apps.availability.models import TimeSlot
# from apps.bookings.models import Booking, BookingStatus, EventType
# from apps.halls.serializers import HallListSerializer


# # Customer must book at least this many days before the event.
# MIN_BOOKING_NOTICE_DAYS = 1

# # Customer can book a maximum of this many days in advance.
# MAX_ADVANCE_BOOKING_DAYS = 180


# # These booking statuses should block the date/time slot from being
# # selected by another customer.
# BLOCKING_BOOKING_STATUSES = [
#     BookingStatus.PENDING_OWNER_CONFIRMATION,
#     BookingStatus.CONFIRMED,
#     BookingStatus.PAYMENT_PENDING,
# ]


# class BookingCreateIntentSerializer(serializers.Serializer):
#     hall_id = serializers.UUIDField(
#         required=True,
#     )

#     event_type = serializers.ChoiceField(
#         choices=EventType.choices,
#         default=EventType.WEDDING,
#     )

#     event_date = serializers.DateField(
#         required=True,
#     )

#     time_slot = serializers.ChoiceField(
#         choices=TimeSlot.choices,
#         required=True,
#     )

#     guest_count = serializers.IntegerField(
#         required=True,
#         min_value=1,
#     )

#     contact_name = serializers.CharField(
#         max_length=150,
#         required=True,
#     )

#     contact_phone = serializers.CharField(
#         max_length=20,
#         required=True,
#     )

#     special_requests = serializers.CharField(
#         required=False,
#         allow_blank=True,
#         default="",
#     )

#     has_catering = serializers.BooleanField(
#         required=False,
#         default=False,
#     )

#     catering_type = serializers.ChoiceField(
#         choices=["VEG", "NON_VEG"],
#         required=False,
#         default="VEG",
#     )

#     has_decor = serializers.BooleanField(
#         required=False,
#         default=False,
#     )

#     has_dj = serializers.BooleanField(
#         required=False,
#         default=False,
#     )

#     def validate_event_date(self, value):
#         today = timezone.localdate()

#         earliest_allowed_date = (
#             today + timedelta(days=MIN_BOOKING_NOTICE_DAYS)
#         )

#         latest_allowed_date = (
#             today + timedelta(days=MAX_ADVANCE_BOOKING_DAYS)
#         )

#         if value < earliest_allowed_date:
#             raise serializers.ValidationError(
#                 f"Bookings must be made at least "
#                 f"{MIN_BOOKING_NOTICE_DAYS} day(s) in advance."
#             )

#         if value > latest_allowed_date:
#             raise serializers.ValidationError(
#                 f"Bookings can only be made up to "
#                 f"{MAX_ADVANCE_BOOKING_DAYS} days in advance."
#             )

#         return value

#     def validate(self, attrs):
#         hall_id = attrs.get("hall_id")
#         event_date = attrs.get("event_date")
#         time_slot = attrs.get("time_slot")

#         if hall_id and event_date and time_slot:
#             existing_booking = Booking.objects.filter(
#                 hall_id=hall_id,
#                 event_date=event_date,
#                 time_slot=time_slot,
#                 status__in=BLOCKING_BOOKING_STATUSES,
#             ).exists()

#             if existing_booking:
#                 raise serializers.ValidationError(
#                     {
#                         "event_date": [
#                             "This hall is already booked for the selected date and time slot."
#                         ]
#                     }
#                 )

#         return attrs


# class BookingListSerializer(serializers.ModelSerializer):
#     hall_name = serializers.CharField(
#         source="hall.name",
#         read_only=True,
#     )

#     hall_slug = serializers.CharField(
#         source="hall.slug",
#         read_only=True,
#     )

#     hall_locality = serializers.CharField(
#         source="hall.locality",
#         read_only=True,
#     )

#     hall_city = serializers.CharField(
#         source="hall.city",
#         read_only=True,
#     )

#     primary_image = serializers.CharField(
#         source="hall.primary_image",
#         read_only=True,
#     )

#     customer_name = serializers.CharField(
#         source="customer.full_name",
#         read_only=True,
#     )

#     customer_email = serializers.CharField(
#         source="customer.email",
#         read_only=True,
#     )

#     class Meta:
#         model = Booking

#         fields = [
#             "id",
#             "booking_number",
#             "hall_id",
#             "hall_name",
#             "hall_slug",
#             "hall_locality",
#             "hall_city",
#             "primary_image",
#             "customer_name",
#             "customer_email",
#             "event_type",
#             "event_date",
#             "time_slot",
#             "guest_count",
#             "total_amount",
#             "advance_amount",
#             "balance_amount",
#             "amount_paid",
#             "status",
#             "created_at",
#         ]


# class BookingDetailSerializer(serializers.ModelSerializer):
#     hall = HallListSerializer(
#         read_only=True,
#     )

#     customer_name = serializers.CharField(
#         source="customer.full_name",
#         read_only=True,
#     )

#     customer_email = serializers.CharField(
#         source="customer.email",
#         read_only=True,
#     )

#     customer_phone = serializers.CharField(
#         source="customer.phone",
#         read_only=True,
#     )

#     class Meta:
#         model = Booking

#         fields = [
#             "id",
#             "booking_number",
#             "customer_id",
#             "customer_name",
#             "customer_email",
#             "customer_phone",
#             "contact_name",
#             "contact_phone",
#             "hall",
#             "event_type",
#             "event_date",
#             "time_slot",
#             "guest_count",
#             "special_requests",
#             "has_catering",
#             "catering_plate_type",
#             "catering_plate_price",
#             "has_decor",
#             "has_dj",
#             "hall_rent",
#             "catering_amount",
#             "decor_amount",
#             "dj_amount",
#             "subtotal",
#             "discount_amount",
#             "tax_rate",
#             "tax_amount",
#             "total_amount",
#             "advance_percentage",
#             "advance_amount",
#             "balance_amount",
#             "amount_paid",
#             "status",
#             "owner_response_notes",
#             "cancellation_reason",
#             "cancellation_fee",
#             "refund_amount",
#             "expires_at",
#             "created_at",
#             "updated_at",
#         ]


# class BookingOwnerDecisionSerializer(serializers.Serializer):
#     notes = serializers.CharField(
#         required=False,
#         allow_blank=True,
#         default="",
#     )


# class BookingCancellationSerializer(serializers.Serializer):
#     reason = serializers.CharField(
#         required=True,
#     )





from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from apps.availability.models import TimeSlot
from apps.bookings.models import Booking, BookingStatus, EventType
from apps.halls.serializers import HallListSerializer


# Customer must book at least this many days before the event.
MIN_BOOKING_NOTICE_DAYS = 1

# Customer can book a maximum of this many days in advance.
MAX_ADVANCE_BOOKING_DAYS = 180


# Only these statuses reserve a hall date/time slot.
# Cancelled, rejected, completed, disputed, refunded, etc. do not
# block a new booking with this logic.
BLOCKING_BOOKING_STATUSES = [
    BookingStatus.PAYMENT_PENDING,
    BookingStatus.PENDING_OWNER_CONFIRMATION,
    BookingStatus.CONFIRMED,
]


class BookingCreateIntentSerializer(serializers.Serializer):
    hall_id = serializers.UUIDField(
        required=True,
    )

    event_type = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        default=EventType.WEDDING,
    )

    event_date = serializers.DateField(
        required=True,
    )

    time_slot = serializers.CharField(
        required=True,
    )

    guest_count = serializers.IntegerField(
        required=True,
        min_value=1,
    )

    contact_name = serializers.CharField(
        max_length=150,
        required=True,
    )

    contact_phone = serializers.CharField(
        max_length=20,
        required=True,
    )

    special_requests = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )

    has_catering = serializers.BooleanField(
        required=False,
        default=False,
    )

    catering_type = serializers.ChoiceField(
        choices=["VEG", "NON_VEG"],
        required=False,
        default="VEG",
    )

    has_decor = serializers.BooleanField(
        required=False,
        default=False,
    )

    has_dj = serializers.BooleanField(
        required=False,
        default=False,
    )

    def validate_event_date(self, value):
        today = timezone.localdate()

        earliest_allowed_date = (
            today + timedelta(days=MIN_BOOKING_NOTICE_DAYS)
        )

        latest_allowed_date = (
            today + timedelta(days=MAX_ADVANCE_BOOKING_DAYS)
        )

        if value < earliest_allowed_date:
            raise serializers.ValidationError(
                f"Bookings must be made at least "
                f"{MIN_BOOKING_NOTICE_DAYS} day(s) in advance."
            )

        if value > latest_allowed_date:
            raise serializers.ValidationError(
                f"Bookings can only be made up to "
                f"{MAX_ADVANCE_BOOKING_DAYS} days in advance."
            )

        return value

    def validate_time_slot(self, value):
        normalized = (value or "").strip().upper()
        if normalized not in dict(TimeSlot.choices):
            raise serializers.ValidationError("Invalid time slot selected.")
        return normalized

    def validate(self, attrs):
        event_type = (attrs.get("event_type") or "").strip().upper()
        if not event_type:
            event_type = EventType.WEDDING
        if event_type not in dict(EventType.choices):
            event_type = EventType.WEDDING
        attrs["event_type"] = event_type
        attrs["time_slot"] = (attrs.get("time_slot") or "").strip().upper()
        return attrs


class BookingListSerializer(serializers.ModelSerializer):
    hall_name = serializers.CharField(
        source="hall.name",
        read_only=True,
    )

    hall_slug = serializers.CharField(
        source="hall.slug",
        read_only=True,
    )

    hall_locality = serializers.CharField(
        source="hall.locality",
        read_only=True,
    )

    hall_city = serializers.CharField(
        source="hall.city",
        read_only=True,
    )

    primary_image = serializers.CharField(
        source="hall.primary_image",
        read_only=True,
    )

    customer_name = serializers.CharField(
        source="customer.full_name",
        read_only=True,
    )

    customer_email = serializers.CharField(
        source="customer.email",
        read_only=True,
    )

    class Meta:
        model = Booking

        fields = [
            "id",
            "booking_number",
            "hall_id",
            "hall_name",
            "hall_slug",
            "hall_locality",
            "hall_city",
            "primary_image",
            "customer_name",
            "customer_email",
            "event_type",
            "event_date",
            "time_slot",
            "guest_count",
            "total_amount",
            "advance_amount",
            "balance_amount",
            "amount_paid",
            "status",
            "created_at",
        ]


class BookingDetailSerializer(serializers.ModelSerializer):
    hall = HallListSerializer(
        read_only=True,
    )

    customer_name = serializers.CharField(
        source="customer.full_name",
        read_only=True,
    )

    customer_email = serializers.CharField(
        source="customer.email",
        read_only=True,
    )

    customer_phone = serializers.CharField(
        source="customer.phone",
        read_only=True,
    )

    class Meta:
        model = Booking

        fields = [
            "id",
            "booking_number",
            "customer_id",
            "customer_name",
            "customer_email",
            "customer_phone",
            "contact_name",
            "contact_phone",
            "hall",
            "event_type",
            "event_date",
            "time_slot",
            "guest_count",
            "special_requests",
            "has_catering",
            "catering_plate_type",
            "catering_plate_price",
            "has_decor",
            "has_dj",
            "hall_rent",
            "catering_amount",
            "decor_amount",
            "dj_amount",
            "subtotal",
            "discount_amount",
            "tax_rate",
            "tax_amount",
            "total_amount",
            "advance_percentage",
            "advance_amount",
            "balance_amount",
            "amount_paid",
            "status",
            "owner_response_notes",
            "cancellation_reason",
            "cancellation_fee",
            "refund_amount",
            "expires_at",
            "created_at",
            "updated_at",
        ]


class BookingOwnerDecisionSerializer(serializers.Serializer):
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )


class BookingCancellationSerializer(serializers.Serializer):
    reason = serializers.CharField(
        required=True,
    )


class BookingRefundSerializer(serializers.Serializer):
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        default="Booking cancellation refund",
    )
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        min_value=0.01,
        default=None,
        allow_null=True,
    )