# from datetime import datetime, timezone
# from rest_framework.views import APIView
# from rest_framework.permissions import AllowAny, IsAuthenticated
# from rest_framework import status
# from apps.core.responses import api_response
# from apps.core.services.audit import AuditService
# from apps.accounts.permissions import IsOwnerRole
# from apps.halls.models import Hall, HallApprovalStatus
# from apps.availability.models import TimeSlot, SlotStatus
# from apps.availability.services.availability import AvailabilityService, AvailabilityConflictError
# from apps.availability.serializers import (
#     AvailabilityCheckRequestSerializer,
#     SlotBlockRequestSerializer,
#     SlotUnblockRequestSerializer,
# )

# class HallMonthAvailabilityView(APIView):
#     """
#     Returns day-by-day availability status matrix for a given month and year.
#     """
#     permission_classes = [AllowAny]
#     authentication_classes = []

#     def get(self, request, pk):
#         hall = Hall.objects.filter(id=pk).first()
#         if not hall:
#             return api_response(message="Function hall not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

#         now = datetime.now(timezone.utc)
#         year = int(request.query_params.get('year', now.year))
#         month = int(request.query_params.get('month', now.month))

#         if month < 1 or month > 12:
#             return api_response(message="Invalid month.", status_code=status.HTTP_400_BAD_REQUEST, success=False)

#         matrix = AvailabilityService.get_month_matrix(hall, year, month)
#         return api_response(data={
#             "year": year,
#             "month": month,
#             "calendar": matrix
#         })


# class HallCheckAvailabilityView(APIView):
#     """
#     Real-time slot availability check and server-calculated price quotation.
#     """
#     permission_classes = [AllowAny]
#     authentication_classes = []

#     def post(self, request, pk):
#         hall = Hall.objects.filter(id=pk).first()
#         if not hall:
#             return api_response(message="Function hall not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

#         serializer = AvailabilityCheckRequestSerializer(data=request.data)
#         if not serializer.is_valid():
#             return api_response(
#                 message="Availability check parameters invalid.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False
#             )

#         data = serializer.validated_data
#         event_date = data['date']
#         slot = data['slot']
#         guest_count = data.get('guest_count') or hall.min_capacity
#         has_catering = data.get('has_catering', False)
#         catering_type = data.get('catering_type', 'VEG')
#         has_decor = data.get('has_decor', False)
#         has_dj = data.get('has_dj', False)

#         # Capacity check
#         if guest_count > hall.max_capacity:
#             return api_response(
#                 data={"is_available": False, "status": "CAPACITY_EXCEEDED"},
#                 message=f"Guest count ({guest_count}) exceeds maximum venue capacity ({hall.max_capacity}).",
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False
#             )

#         avail_result = AvailabilityService.check_availability(hall, event_date, slot)

#         # Calculate authoritative server price breakdown
#         if slot == TimeSlot.MORNING:
#             hall_rent = float(hall.base_price_morning)
#         elif slot == TimeSlot.EVENING:
#             hall_rent = float(hall.base_price_evening)
#         else:
#             hall_rent = float(hall.base_price_full_day)

#         per_plate = float(hall.veg_plate_price) if catering_type == 'VEG' else float(hall.non_veg_plate_price)
#         catering_amount = (guest_count * per_plate) if has_catering else 0.0
#         decor_amount = float(hall.decor_price) if has_decor else 0.0
#         dj_amount = float(hall.dj_price) if has_dj else 0.0

#         subtotal = hall_rent + catering_amount + decor_amount + dj_amount
#         tax_rate = 18.0
#         tax_amount = round(subtotal * (tax_rate / 100.0), 2)
#         total_amount = round(subtotal + tax_amount, 2)
#         advance_pct = float(hall.advance_percentage)
#         advance_amount = round(total_amount * (advance_pct / 100.0), 2)
#         balance_amount = round(total_amount - advance_amount, 2)

#         quotation = {
#             "hall_rent": hall_rent,
#             "has_catering": has_catering,
#             "catering_plate_type": catering_type,
#             "per_plate_price": per_plate,
#             "catering_amount": catering_amount,
#             "has_decor": has_decor,
#             "decor_amount": decor_amount,
#             "has_dj": has_dj,
#             "dj_amount": dj_amount,
#             "subtotal": subtotal,
#             "tax_rate": tax_rate,
#             "tax_amount": tax_amount,
#             "total_amount": total_amount,
#             "advance_percentage": advance_pct,
#             "advance_amount": advance_amount,
#             "balance_amount": balance_amount,
#         }

#         return api_response(data={
#             "is_available": avail_result["is_available"],
#             "slot_status": avail_result["status"],
#             "message": avail_result["reason"],
#             "quotation": quotation
#         })


# class HallBlockSlotView(APIView):
#     """
#     Owner manually blocks a date/slot for private usage or maintenance.
#     """
#     permission_classes = [IsAuthenticated, IsOwnerRole]

#     def post(self, request, pk):
#         hall = Hall.objects.filter(id=pk, owner=request.user).first()
#         if not hall:
#             return api_response(message="Venue not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

#         serializer = SlotBlockRequestSerializer(data=request.data)
#         if not serializer.is_valid():
#             return api_response(errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST, success=False)

#         try:
#             slot_rec = AvailabilityService.block_slot_manually(
#                 hall=hall,
#                 event_date=serializer.validated_data['date'],
#                 slot=serializer.validated_data['slot'],
#                 reason=serializer.validated_data.get('reason', '')
#             )
#             AuditService.log_action(
#                 actor=request.user,
#                 action="OWNER_BLOCKED_SLOT",
#                 obj=hall,
#                 changes={"date": str(slot_rec.date), "slot": slot_rec.slot, "reason": slot_rec.blocked_reason}
#             )
#             return api_response(message=f"Slot '{slot_rec.slot}' on {slot_rec.date} has been blocked.")
#         except AvailabilityConflictError as e:
#             return api_response(message=str(e), status_code=status.HTTP_409_CONFLICT, success=False)


# class HallUnblockSlotView(APIView):
#     """
#     Owner unblocks a previously blocked date/slot.
#     """
#     permission_classes = [IsAuthenticated, IsOwnerRole]

#     def post(self, request, pk):
#         hall = Hall.objects.filter(id=pk, owner=request.user).first()
#         if not hall:
#             return api_response(message="Venue not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

#         serializer = SlotUnblockRequestSerializer(data=request.data)
#         if not serializer.is_valid():
#             return api_response(errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST, success=False)

#         try:
#             slot_rec = AvailabilityService.unblock_slot_manually(
#                 hall=hall,
#                 event_date=serializer.validated_data['date'],
#                 slot=serializer.validated_data['slot']
#             )
#             if not slot_rec:
#                 return api_response(message="Slot was not blocked.", status_code=status.HTTP_400_BAD_REQUEST, success=False)

#             AuditService.log_action(
#                 actor=request.user,
#                 action="OWNER_UNBLOCKED_SLOT",
#                 obj=hall,
#                 changes={"date": str(slot_rec.date), "slot": slot_rec.slot}
#             )
#             return api_response(message=f"Slot '{slot_rec.slot}' on {slot_rec.date} is now OPEN.")
#         except AvailabilityConflictError as e:
#             return api_response(message=str(e), status_code=status.HTTP_409_CONFLICT, success=False)


from datetime import datetime, timezone

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status, serializers

from drf_spectacular.utils import (
    extend_schema,
    inline_serializer,
    OpenApiParameter,
    OpenApiResponse,
)

from apps.core.responses import api_response
from apps.core.services.audit import AuditService
from apps.accounts.permissions import IsOwnerRole
from apps.halls.models import Hall
from apps.availability.models import TimeSlot
from apps.availability.services.availability import (
    AvailabilityService,
    AvailabilityConflictError,
)
from apps.availability.serializers import (
    AvailabilityCheckRequestSerializer,
    SlotBlockRequestSerializer,
    SlotUnblockRequestSerializer,
)


class HallMonthAvailabilityView(APIView):
    """
    Returns day-by-day availability status matrix for a given month and year.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Get hall monthly availability",
        description=(
            "Returns the day-by-day availability matrix for a function hall. "
            "Year and month default to the current year and month when omitted."
        ),
        parameters=[
            OpenApiParameter(
                name="pk",
                type=int,
                location=OpenApiParameter.PATH,
                description="Function hall ID.",
            ),
            OpenApiParameter(
                name="year",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Calendar year. Defaults to the current year.",
            ),
            OpenApiParameter(
                name="month",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Calendar month from 1 to 12. Defaults to the current month.",
            ),
        ],
        responses={
            200: inline_serializer(
                name="HallMonthAvailabilityResponse",
                fields={
                    "success": serializers.BooleanField(),
                    "message": serializers.CharField(),
                    "data": inline_serializer(
                        name="HallMonthAvailabilityData",
                        fields={
                            "year": serializers.IntegerField(),
                            "month": serializers.IntegerField(),
                            "calendar": serializers.JSONField(),
                        },
                    ),
                },
            ),
            400: OpenApiResponse(
                description="Invalid month."
            ),
            404: OpenApiResponse(
                description="Function hall not found."
            ),
        },
        tags=["Availability"],
    )
    def get(self, request, pk):
        hall = Hall.objects.filter(id=pk).first()

        if not hall:
            return api_response(
                message="Function hall not found.",
                status_code=status.HTTP_404_NOT_FOUND,
                success=False,
            )

        now = datetime.now(timezone.utc)

        year = int(
            request.query_params.get(
                "year",
                now.year,
            )
        )

        month = int(
            request.query_params.get(
                "month",
                now.month,
            )
        )

        if month < 1 or month > 12:
            return api_response(
                message="Invalid month.",
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
            )

        matrix = AvailabilityService.get_month_matrix(
            hall,
            year,
            month,
        )

        return api_response(
            data={
                "year": year,
                "month": month,
                "calendar": matrix,
            }
        )


class HallCheckAvailabilityView(APIView):
    """
    Real-time slot availability check and server-calculated price quotation.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Check hall availability and quotation",
        description=(
            "Checks real-time hall availability for the requested date and "
            "time slot and returns a server-calculated price quotation."
        ),
        parameters=[
            OpenApiParameter(
                name="pk",
                type=int,
                location=OpenApiParameter.PATH,
                description="Function hall ID.",
            ),
        ],
        request=AvailabilityCheckRequestSerializer,
        responses={
            200: inline_serializer(
                name="HallCheckAvailabilityResponse",
                fields={
                    "success": serializers.BooleanField(),
                    "message": serializers.CharField(),
                    "data": inline_serializer(
                        name="HallCheckAvailabilityData",
                        fields={
                            "is_available": serializers.BooleanField(),
                            "slot_status": serializers.CharField(),
                            "message": serializers.CharField(),
                            "quotation": inline_serializer(
                                name="AvailabilityQuotation",
                                fields={
                                    "hall_rent": serializers.FloatField(),
                                    "has_catering": serializers.BooleanField(),
                                    "catering_plate_type": serializers.CharField(),
                                    "per_plate_price": serializers.FloatField(),
                                    "catering_amount": serializers.FloatField(),
                                    "has_decor": serializers.BooleanField(),
                                    "decor_amount": serializers.FloatField(),
                                    "has_dj": serializers.BooleanField(),
                                    "dj_amount": serializers.FloatField(),
                                    "subtotal": serializers.FloatField(),
                                    "tax_rate": serializers.FloatField(),
                                    "tax_amount": serializers.FloatField(),
                                    "total_amount": serializers.FloatField(),
                                    "advance_percentage": serializers.FloatField(),
                                    "advance_amount": serializers.FloatField(),
                                    "balance_amount": serializers.FloatField(),
                                },
                            ),
                        },
                    ),
                },
            ),
            400: OpenApiResponse(
                description=(
                    "Invalid availability parameters or guest count "
                    "exceeds the hall's maximum capacity."
                )
            ),
            404: OpenApiResponse(
                description="Function hall not found."
            ),
        },
        tags=["Availability"],
    )
    def post(self, request, pk):
        hall = Hall.objects.filter(id=pk).first()

        if not hall:
            return api_response(
                message="Function hall not found.",
                status_code=status.HTTP_404_NOT_FOUND,
                success=False,
            )

        serializer = AvailabilityCheckRequestSerializer(
            data=request.data
        )

        if not serializer.is_valid():
            return api_response(
                message="Availability check parameters invalid.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
            )

        data = serializer.validated_data

        event_date = data["date"]
        slot = data["slot"]

        guest_count = (
            data.get("guest_count")
            or hall.min_capacity
        )

        has_catering = data.get(
            "has_catering",
            False,
        )

        catering_type = data.get(
            "catering_type",
            "VEG",
        )

        has_decor = data.get(
            "has_decor",
            False,
        )

        has_dj = data.get(
            "has_dj",
            False,
        )

        # Capacity check
        if guest_count > hall.max_capacity:
            return api_response(
                data={
                    "is_available": False,
                    "status": "CAPACITY_EXCEEDED",
                },
                message=(
                    f"Guest count ({guest_count}) exceeds maximum "
                    f"venue capacity ({hall.max_capacity})."
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
            )

        avail_result = AvailabilityService.check_availability(
            hall,
            event_date,
            slot,
        )

        # Calculate authoritative server price breakdown
        if slot == TimeSlot.MORNING:
            hall_rent = float(
                hall.base_price_morning
            )

        elif slot == TimeSlot.EVENING:
            hall_rent = float(
                hall.base_price_evening
            )

        else:
            hall_rent = float(
                hall.base_price_full_day
            )

        per_plate = (
            float(hall.veg_plate_price)
            if catering_type == "VEG"
            else float(hall.non_veg_plate_price)
        )

        catering_amount = (
            guest_count * per_plate
            if has_catering
            else 0.0
        )

        decor_amount = (
            float(hall.decor_price)
            if has_decor
            else 0.0
        )

        dj_amount = (
            float(hall.dj_price)
            if has_dj
            else 0.0
        )

        subtotal = (
            hall_rent
            + catering_amount
            + decor_amount
            + dj_amount
        )

        tax_rate = 18.0

        tax_amount = round(
            subtotal * (tax_rate / 100.0),
            2,
        )

        total_amount = round(
            subtotal + tax_amount,
            2,
        )

        advance_pct = float(
            hall.advance_percentage
        )

        advance_amount = round(
            total_amount * (advance_pct / 100.0),
            2,
        )

        balance_amount = round(
            total_amount - advance_amount,
            2,
        )

        quotation = {
            "hall_rent": hall_rent,
            "has_catering": has_catering,
            "catering_plate_type": catering_type,
            "per_plate_price": per_plate,
            "catering_amount": catering_amount,
            "has_decor": has_decor,
            "decor_amount": decor_amount,
            "has_dj": has_dj,
            "dj_amount": dj_amount,
            "subtotal": subtotal,
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "total_amount": total_amount,
            "advance_percentage": advance_pct,
            "advance_amount": advance_amount,
            "balance_amount": balance_amount,
        }

        return api_response(
            data={
                "is_available": avail_result["is_available"],
                "slot_status": avail_result["status"],
                "message": avail_result["reason"],
                "quotation": quotation,
            }
        )


class HallBlockSlotView(APIView):
    """
    Owner manually blocks a date/slot for private usage or maintenance.
    """

    permission_classes = [
        IsAuthenticated,
        IsOwnerRole,
    ]

    @extend_schema(
        summary="Block hall time slot",
        description=(
            "Allows a hall owner to manually block a date and "
            "time slot for private use or maintenance."
        ),
        parameters=[
            OpenApiParameter(
                name="pk",
                type=int,
                location=OpenApiParameter.PATH,
                description="Function hall ID.",
            ),
        ],
        request=SlotBlockRequestSerializer,
        responses={
            200: OpenApiResponse(
                description="Slot successfully blocked."
            ),
            400: OpenApiResponse(
                description="Invalid request."
            ),
            404: OpenApiResponse(
                description="Venue not found."
            ),
            409: OpenApiResponse(
                description="Availability conflict."
            ),
        },
        tags=["Availability"],
    )
    def post(self, request, pk):
        hall = Hall.objects.filter(
            id=pk,
            owner=request.user,
        ).first()

        if not hall:
            return api_response(
                message="Venue not found.",
                status_code=status.HTTP_404_NOT_FOUND,
                success=False,
            )

        serializer = SlotBlockRequestSerializer(
            data=request.data
        )

        if not serializer.is_valid():
            return api_response(
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
            )

        try:
            slot_rec = AvailabilityService.block_slot_manually(
                hall=hall,
                event_date=serializer.validated_data["date"],
                slot=serializer.validated_data["slot"],
                reason=serializer.validated_data.get(
                    "reason",
                    "",
                ),
            )

            AuditService.log_action(
                actor=request.user,
                action="OWNER_BLOCKED_SLOT",
                obj=hall,
                changes={
                    "date": str(slot_rec.date),
                    "slot": slot_rec.slot,
                    "reason": slot_rec.blocked_reason,
                },
            )

            return api_response(
                message=(
                    f"Slot '{slot_rec.slot}' on "
                    f"{slot_rec.date} has been blocked."
                )
            )

        except AvailabilityConflictError as e:
            return api_response(
                message=str(e),
                status_code=status.HTTP_409_CONFLICT,
                success=False,
            )


class HallUnblockSlotView(APIView):
    """
    Owner unblocks a previously blocked date/slot.
    """

    permission_classes = [
        IsAuthenticated,
        IsOwnerRole,
    ]

    @extend_schema(
        summary="Unblock hall time slot",
        description=(
            "Allows a hall owner to unblock a previously "
            "blocked date and time slot."
        ),
        parameters=[
            OpenApiParameter(
                name="pk",
                type=int,
                location=OpenApiParameter.PATH,
                description="Function hall ID.",
            ),
        ],
        request=SlotUnblockRequestSerializer,
        responses={
            200: OpenApiResponse(
                description="Slot successfully unblocked."
            ),
            400: OpenApiResponse(
                description="Invalid request or slot was not blocked."
            ),
            404: OpenApiResponse(
                description="Venue not found."
            ),
            409: OpenApiResponse(
                description="Availability conflict."
            ),
        },
        tags=["Availability"],
    )
    def post(self, request, pk):
        hall = Hall.objects.filter(
            id=pk,
            owner=request.user,
        ).first()

        if not hall:
            return api_response(
                message="Venue not found.",
                status_code=status.HTTP_404_NOT_FOUND,
                success=False,
            )

        serializer = SlotUnblockRequestSerializer(
            data=request.data
        )

        if not serializer.is_valid():
            return api_response(
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False,
            )

        try:
            slot_rec = AvailabilityService.unblock_slot_manually(
                hall=hall,
                event_date=serializer.validated_data["date"],
                slot=serializer.validated_data["slot"],
            )

            if not slot_rec:
                return api_response(
                    message="Slot was not blocked.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    success=False,
                )

            AuditService.log_action(
                actor=request.user,
                action="OWNER_UNBLOCKED_SLOT",
                obj=hall,
                changes={
                    "date": str(slot_rec.date),
                    "slot": slot_rec.slot,
                },
            )

            return api_response(
                message=(
                    f"Slot '{slot_rec.slot}' on "
                    f"{slot_rec.date} is now OPEN."
                )
            )

        except AvailabilityConflictError as e:
            return api_response(
                message=str(e),
                status_code=status.HTTP_409_CONFLICT,
                success=False,
            )