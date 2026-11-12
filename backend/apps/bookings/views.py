# import logging
# from rest_framework.views import APIView
# from rest_framework.permissions import IsAuthenticated
# from rest_framework import status
# from apps.core.responses import api_response
# from apps.core.pagination import StandardPagination
# from apps.halls.models import Hall
# from apps.bookings.models import Booking, BookingStatus
# from apps.bookings.services.booking import BookingService, BookingValidationError
# from apps.bookings.serializers import (
#     BookingCreateIntentSerializer,
#     BookingListSerializer,
#     BookingDetailSerializer,
#     BookingOwnerDecisionSerializer,
#     BookingCancellationSerializer,
# )

# logger = logging.getLogger(__name__)

# class BookingCreateIntentView(APIView):
#     """
#     Step 1 of checkout: validates slot, acquires pessimistic concurrency lock,
#     calculates frozen quotation, and creates booking with status PAYMENT_PENDING.
#     """
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         serializer = BookingCreateIntentSerializer(data=request.data)
#         if not serializer.is_valid():
#             return api_response(
#                 message="Booking parameters invalid.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="VALIDATION_ERROR"
#             )

#         data = serializer.validated_data
#         hall = Hall.objects.filter(id=data['hall_id']).first()
#         if not hall:
#             return api_response(message="Function hall not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

#         try:
#             booking = BookingService.create_booking_intent(
#                 customer=request.user,
#                 hall=hall,
#                 event_type=data['event_type'],
#                 event_date=data['event_date'],
#                 time_slot=data['time_slot'],
#                 guest_count=data['guest_count'],
#                 contact_name=data['contact_name'],
#                 contact_phone=data['contact_phone'],
#                 special_requests=data.get('special_requests', ''),
#                 has_catering=data.get('has_catering', False),
#                 catering_type=data.get('catering_type', 'VEG'),
#                 has_decor=data.get('has_decor', False),
#                 has_dj=data.get('has_dj', False),
#             )

#             return api_response(
#                 data=BookingDetailSerializer(booking).data,
#                 message="Booking intent created. Slot held for 15 minutes to complete payment.",
#                 status_code=status.HTTP_201_CREATED
#             )
#         except BookingValidationError as exc:
#             return api_response(
#                 message=str(exc),
#                 status_code=status.HTTP_409_CONFLICT,
#                 success=False,
#                 code="SLOT_CONFLICT"
#             )


# class CustomerBookingListView(APIView):
#     """
#     Lists all bookings created by the authenticated customer.
#     """
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         bookings = Booking.objects.filter(customer=request.user).select_related('hall').order_by('-created_at')
#         paginator = StandardPagination()
#         page = paginator.paginate_queryset(bookings, request)
#         serializer = BookingListSerializer(page, many=True)
#         return paginator.get_paginated_response(serializer.data)


# class BookingDetailView(APIView):
#     """
#     Retrieves full booking details with IDOR object-level protection.
#     """
#     permission_classes = [IsAuthenticated]

#     def get(self, request, pk):
#         booking = Booking.objects.filter(id=pk).select_related('hall', 'customer', 'hall__owner', 'hall__owner__owner_profile').first()
#         if not booking:
#             return api_response(message="Booking not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

#         # IDOR Authorization Guard
#         is_customer = booking.customer == request.user
#         is_owner = booking.hall.owner == request.user
#         is_admin = request.user.is_admin

#         if not (is_customer or is_owner or is_admin):
#             return api_response(
#                 message="You do not have authorization to view this booking.",
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 success=False,
#                 code="FORBIDDEN"
#             )

#         serializer = BookingDetailSerializer(booking)
#         return api_response(data=serializer.data)


# class OwnerBookingListView(APIView):
#     """
#     Lists incoming booking requests for the authenticated venue owner.
#     """
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         status_filter = request.query_params.get('status')
#         bookings = Booking.objects.filter(hall__owner=request.user).select_related('hall', 'customer').order_by('-created_at')
        
#         if status_filter:
#             bookings = bookings.filter(status=status_filter)

#         paginator = StandardPagination()
#         page = paginator.paginate_queryset(bookings, request)
#         serializer = BookingListSerializer(page, many=True)
#         return paginator.get_paginated_response(serializer.data)


# class OwnerAcceptBookingView(APIView):
#     """
#     Owner confirms a pending booking request.
#     """
#     permission_classes = [IsAuthenticated]

#     def post(self, request, pk):
#         booking = Booking.objects.filter(id=pk).select_related('hall', 'hall__owner').first()
#         if not booking:
#             return api_response(message="Booking not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

#         serializer = BookingOwnerDecisionSerializer(data=request.data)
#         serializer.is_valid()
#         notes = serializer.validated_data.get('notes', '') if serializer.is_valid() else ""

#         try:
#             confirmed_booking = BookingService.owner_accept_booking(booking, request.user, notes=notes)
#             return api_response(
#                 data=BookingDetailSerializer(confirmed_booking).data,
#                 message=f"Booking #{confirmed_booking.booking_number} accepted and confirmed!"
#             )
#         except BookingValidationError as exc:
#             return api_response(message=str(exc), status_code=status.HTTP_400_BAD_REQUEST, success=False)


# class OwnerRejectBookingView(APIView):
#     """
#     Owner rejects a pending booking request.
#     """
#     permission_classes = [IsAuthenticated]

#     def post(self, request, pk):
#         booking = Booking.objects.filter(id=pk).select_related('hall', 'hall__owner').first()
#         if not booking:
#             return api_response(message="Booking not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

#         serializer = BookingOwnerDecisionSerializer(data=request.data)
#         if not serializer.is_valid():
#             return api_response(errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST, success=False)

#         reason = serializer.validated_data.get('notes', 'Unavailable')

#         try:
#             rejected_booking = BookingService.owner_reject_booking(booking, request.user, reason=reason)
#             return api_response(
#                 data=BookingDetailSerializer(rejected_booking).data,
#                 message=f"Booking #{rejected_booking.booking_number} declined."
#             )
#         except BookingValidationError as exc:
#             return api_response(message=str(exc), status_code=status.HTTP_400_BAD_REQUEST, success=False)


# class CancelBookingView(APIView):
#     """
#     Customer or Owner cancels an active booking.
#     """
#     permission_classes = [IsAuthenticated]

#     def post(self, request, pk):
#         booking = Booking.objects.filter(id=pk).select_related('hall', 'customer', 'hall__owner').first()
#         if not booking:
#             return api_response(message="Booking not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

#         serializer = BookingCancellationSerializer(data=request.data)
#         if not serializer.is_valid():
#             return api_response(errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST, success=False)

#         reason = serializer.validated_data['reason']

#         try:
#             cancelled_booking = BookingService.cancel_booking(booking, request.user, reason=reason)
#             return api_response(
#                 data=BookingDetailSerializer(cancelled_booking).data,
#                 message=f"Booking cancelled. Refund eligible: ₹{cancelled_booking.refund_amount}."
#             )
#         except BookingValidationError as exc:
#             return api_response(message=str(exc), status_code=status.HTTP_400_BAD_REQUEST, success=False)



import logging

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from apps.core.responses import api_response
from apps.core.pagination import StandardPagination

from apps.halls.models import Hall
from apps.bookings.models import Booking, BookingStatus, EventType
from apps.bookings.services.booking import (
    BookingService,
    BookingValidationError,
)
from apps.bookings.serializers import (
    BookingCreateIntentSerializer,
    BookingListSerializer,
    BookingDetailSerializer,
    BookingOwnerDecisionSerializer,
    BookingCancellationSerializer,
    BookingRefundSerializer,
)


logger = logging.getLogger(__name__)


class BookingCreateIntentView(APIView):
    """
    Step 1 of checkout: validates slot, acquires pessimistic concurrency lock,
    calculates frozen quotation, and creates booking with status PAYMENT_PENDING.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=BookingCreateIntentSerializer,
        responses={
            201: BookingDetailSerializer,
        },
        tags=["Bookings"],
        summary="Create booking intent",
        description=(
            "Creates a booking intent after validating the requested hall, "
            "date, time slot, guest count and optional services. "
            "The slot is held for 15 minutes while payment is completed."
        ),
    )
    def post(self, request):
        serializer = BookingCreateIntentSerializer(data=request.data)

        if not serializer.is_valid():
            validation_message = "Invalid Booking Parameters."
            error_values = serializer.errors.values()
            for error_value in error_values:
                if isinstance(error_value, list) and error_value:
                    validation_message = str(error_value[0])
                    break
                if isinstance(error_value, dict):
                    nested_errors = []
                    for nested_value in error_value.values():
                        if isinstance(nested_value, list) and nested_value:
                            nested_errors.extend(nested_value)
                    if nested_errors:
                        validation_message = str(nested_errors[0])
                        break

            return api_response(
                message=validation_message,
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
                code="VALIDATION_ERROR",
            )

        data = serializer.validated_data

        hall = Hall.objects.filter(id=data["hall_id"]).first()

        if not hall:
            return api_response(
                message="Function hall not found.",
                status_code=status.HTTP_404_NOT_FOUND,
                success=False,
            )

        try:
            booking = BookingService.create_booking_intent(
                customer=request.user,
                hall=hall,
                event_type=data.get("event_type", EventType.WEDDING),
                event_date=data["event_date"],
                time_slot=data["time_slot"],
                guest_count=data["guest_count"],
                contact_name=data["contact_name"],
                contact_phone=data["contact_phone"],
                special_requests=data.get("special_requests", ""),
                has_catering=data.get("has_catering", False),
                catering_type=data.get("catering_type", "VEG"),
                has_decor=data.get("has_decor", False),
                has_dj=data.get("has_dj", False),
            )

            return api_response(
                data=BookingDetailSerializer(booking).data,
                message=(
                    "Booking intent created. Slot held for 15 minutes "
                    "to complete payment."
                ),
                status_code=status.HTTP_201_CREATED,
            )

        except BookingValidationError as exc:
            return api_response(
                message=str(exc),
                status_code=status.HTTP_409_CONFLICT,
                success=False,
                code="SLOT_CONFLICT",
            )


class CustomerBookingListView(APIView):
    """
    Lists all bookings created by the authenticated customer.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: BookingListSerializer(many=True),
        },
        tags=["Bookings"],
        summary="List customer bookings",
        description="Returns bookings belonging to the authenticated customer.",
    )
    def get(self, request):
        bookings = (
            Booking.objects
            .filter(customer=request.user)
            .select_related("hall")
            .order_by("-created_at")
        )

        paginator = StandardPagination()
        page = paginator.paginate_queryset(bookings, request)

        serializer = BookingListSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)


class BookingDetailView(APIView):
    """
    Retrieves full booking details with IDOR object-level protection.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="pk",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                required=True,
                description="Booking ID",
            ),
        ],
        responses={
            200: BookingDetailSerializer,
        },
        tags=["Bookings"],
        summary="Get booking details",
        description=(
            "Returns complete booking details. Access is restricted "
            "to the customer, hall owner, or administrator."
        ),
    )
    def get(self, request, pk):
        booking = (
            Booking.objects
            .filter(id=pk)
            .select_related(
                "hall",
                "customer",
                "hall__owner",
                "hall__owner__owner_profile",
            )
            .first()
        )

        if not booking:
            return api_response(
                message="Booking not found.",
                status_code=status.HTTP_404_NOT_FOUND,
                success=False,
            )

        # IDOR Authorization Guard
        is_customer = booking.customer == request.user
        is_owner = booking.hall.owner == request.user
        is_admin = request.user.is_admin

        if not (is_customer or is_owner or is_admin):
            return api_response(
                message="You do not have authorization to view this booking.",
                status_code=status.HTTP_403_FORBIDDEN,
                success=False,
                code="FORBIDDEN",
            )

        serializer = BookingDetailSerializer(booking)

        return api_response(data=serializer.data)


class OwnerBookingListView(APIView):
    """
    Lists incoming booking requests for the authenticated venue owner.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="status",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter bookings by booking status.",
            ),
        ],
        responses={
            200: BookingListSerializer(many=True),
        },
        tags=["Bookings"],
        summary="List owner bookings",
        description=(
            "Returns incoming booking requests for halls owned by "
            "the authenticated owner."
        ),
    )
    def get(self, request):
        status_filter = request.query_params.get("status")

        bookings = (
            Booking.objects
            .filter(hall__owner=request.user)
            .select_related("hall", "customer")
            .order_by("-created_at")
        )

        if status_filter:
            bookings = bookings.filter(status=status_filter)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(bookings, request)

        serializer = BookingListSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)


class OwnerAcceptBookingView(APIView):
    """
    Owner confirms a pending booking request.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="pk",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                required=True,
                description="Booking ID",
            ),
        ],
        request=BookingOwnerDecisionSerializer,
        responses={
            200: BookingDetailSerializer,
        },
        tags=["Bookings"],
        summary="Accept booking",
        description="Allows the hall owner to accept a pending booking request.",
    )
    def post(self, request, pk):
        booking = (
            Booking.objects
            .filter(id=pk)
            .select_related("hall", "hall__owner")
            .first()
        )

        if not booking:
            return api_response(
                message="Booking not found.",
                status_code=status.HTTP_404_NOT_FOUND,
                success=False,
            )

        serializer = BookingOwnerDecisionSerializer(data=request.data)

        if not serializer.is_valid():
            return api_response(
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
            )

        notes = serializer.validated_data.get("notes", "")

        try:
            confirmed_booking = BookingService.owner_accept_booking(
                booking,
                request.user,
                notes=notes,
            )

            return api_response(
                data=BookingDetailSerializer(confirmed_booking).data,
                message=(
                    f"Booking #{confirmed_booking.booking_number} "
                    "accepted and confirmed!"
                ),
            )

        except BookingValidationError as exc:
            return api_response(
                message=str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
            )


class OwnerRejectBookingView(APIView):
    """
    Owner rejects a pending booking request.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="pk",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                required=True,
                description="Booking ID",
            ),
        ],
        request=BookingOwnerDecisionSerializer,
        responses={
            200: BookingDetailSerializer,
        },
        tags=["Bookings"],
        summary="Reject booking",
        description="Allows the hall owner to reject a pending booking request.",
    )
    def post(self, request, pk):
        booking = (
            Booking.objects
            .filter(id=pk)
            .select_related("hall", "hall__owner")
            .first()
        )

        if not booking:
            return api_response(
                message="Booking not found.",
                status_code=status.HTTP_404_NOT_FOUND,
                success=False,
            )

        serializer = BookingOwnerDecisionSerializer(data=request.data)

        if not serializer.is_valid():
            return api_response(
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
            )

        reason = serializer.validated_data.get("notes", "Unavailable")

        try:
            rejected_booking = BookingService.owner_reject_booking(
                booking,
                request.user,
                reason=reason,
            )

            return api_response(
                data=BookingDetailSerializer(rejected_booking).data,
                message=(
                    f"Booking #{rejected_booking.booking_number} "
                    "declined."
                ),
            )

        except BookingValidationError as exc:
            return api_response(
                message=str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
            )


class ProcessBookingRefundView(APIView):
    """Allows the hall owner or admin to process the refundable amount for a cancelled booking."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        booking = (
            Booking.objects
            .filter(id=pk)
            .select_related("hall", "hall__owner", "customer")
            .first()
        )

        if not booking:
            return api_response(
                message="Booking not found.",
                status_code=status.HTTP_404_NOT_FOUND,
                success=False,
            )

        if booking.hall.owner != request.user and not getattr(request.user, 'is_admin', False):
            return api_response(
                message="Only the hall owner or admin can process this refund.",
                status_code=status.HTTP_403_FORBIDDEN,
                success=False,
            )

        serializer = BookingRefundSerializer(data=request.data)
        if not serializer.is_valid():
            return api_response(
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
            )

        try:
            refund_booking = BookingService.process_booking_refund(
                booking,
                request.user,
                reason=serializer.validated_data.get("reason", "Booking cancellation refund"),
                amount=serializer.validated_data.get("amount"),
            )
            return api_response(
                data=BookingDetailSerializer(refund_booking).data,
                message=(
                    f"Refund of ₹{refund_booking.refund_amount} has been processed for booking #{refund_booking.booking_number}."
                ),
            )
        except BookingValidationError as exc:
            return api_response(
                message=str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
            )


class CancelBookingView(APIView):
    """
    Customer or Owner cancels an active booking.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="pk",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                required=True,
                description="Booking ID",
            ),
        ],
        request=BookingCancellationSerializer,
        responses={
            200: BookingDetailSerializer,
        },
        tags=["Bookings"],
        summary="Cancel booking",
        description=(
            "Allows an authorized customer or hall owner to cancel "
            "an active booking."
        ),
    )
    def post(self, request, pk):
        booking = (
            Booking.objects
            .filter(id=pk)
            .select_related(
                "hall",
                "customer",
                "hall__owner",
            )
            .first()
        )

        if not booking:
            return api_response(
                message="Booking not found.",
                status_code=status.HTTP_404_NOT_FOUND,
                success=False,
            )

        serializer = BookingCancellationSerializer(data=request.data)

        if not serializer.is_valid():
            return api_response(
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
            )

        reason = serializer.validated_data["reason"]

        try:
            cancelled_booking = BookingService.cancel_booking(
                booking,
                request.user,
                reason=reason,
            )

            return api_response(
                data=BookingDetailSerializer(cancelled_booking).data,
                message=(
                    f"Booking cancelled. Refund eligible: "
                    f"₹{cancelled_booking.refund_amount}."
                ),
            )

        except BookingValidationError as exc:
            return api_response(
                message=str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
            )