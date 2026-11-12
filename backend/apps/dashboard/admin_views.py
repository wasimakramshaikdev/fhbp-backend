from datetime import datetime, timezone
from decimal import Decimal
from django.core.cache import cache
from django.db.models import Sum, Count, Q
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from apps.core.responses import api_response
from apps.core.pagination import StandardPagination
from apps.core.models import PlatformSetting, AuditLog
from apps.core.services.audit import AuditService
from apps.accounts.models import User, UserRole, OwnerProfile, OwnerVerificationStatus
from apps.accounts.permissions import IsAdminRole
from apps.halls.models import Hall, HallApprovalStatus, HallStatus
from apps.bookings.models import Booking, BookingStatus
from apps.payouts.models import Payout
from apps.disputes.models import Dispute, DisputeStatus

class AdminDashboardOverviewView(APIView):
    """
    High-level platform metrics for Super Admin (Wireframe Admin Screen 1):
    Total halls, Active owners, Bookings MTD, Commission revenue MTD, and Pending Approvals queue.
    """
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        now = datetime.now(timezone.utc)
        current_year = now.year
        current_month = now.month

        total_halls = Hall.objects.count()
        active_owners = User.objects.filter(role=UserRole.OWNER, is_active=True).count()

        bookings_mtd = Booking.objects.filter(
            created_at__year=current_year,
            created_at__month=current_month
        )
        bookings_mtd_count = bookings_mtd.count()

        # Platform commission MTD
        commission_mtd = Payout.objects.filter(
            created_at__year=current_year,
            created_at__month=current_month
        ).aggregate(Sum('commission_amount'))['commission_amount__sum'] or Decimal('0.00')

        # Refunded bookings and total refund amount this month
        refunded_bookings_qs = Booking.objects.filter(status=BookingStatus.REFUNDED).select_related('hall', 'customer').order_by('-updated_at')
        refunds_this_month = refunded_bookings_qs.filter(
            updated_at__year=current_year,
            updated_at__month=current_month,
        )
        refund_amount_mtd = refunds_this_month.aggregate(Sum('refund_amount'))['refund_amount__sum'] or Decimal('0.00')
        total_refunded_bookings = refunded_bookings_qs.count()

        refund_due_qs = Booking.objects.filter(
            status=BookingStatus.CANCELLED_BY_CUSTOMER,
            refund_amount__gt=0,
        ).select_related('hall', 'customer').order_by('-updated_at')
        refunds_due_count = refund_due_qs.count()
        refunds_due_amount = refund_due_qs.aggregate(Sum('refund_amount'))['refund_amount__sum'] or Decimal('0.00')

        refunded_bookings = [{
            "id": str(b.id),
            "booking_number": b.booking_number,
            "hall_name": b.hall.name,
            "customer_name": b.contact_name or b.customer.full_name,
            "customer_email": b.customer.email,
            "refund_amount": float(b.refund_amount),
            "amount_paid": float(b.amount_paid),
            "event_date": b.event_date.isoformat(),
            "status": b.status,
            "refunded_at": b.updated_at.isoformat(),
        } for b in refunded_bookings_qs[:20]]

        # Pending Approvals List (Wireframe Admin Screen 1)
        pending_halls = Hall.objects.filter(
            approval_status=HallApprovalStatus.UNDER_REVIEW
        ).select_related('owner', 'owner__owner_profile').order_by('-created_at')[:8]

        pending_data = []
        for h in pending_halls:
            pending_data.append({
                "id": str(h.id),
                "hall_name": h.name,
                "locality": h.locality,
                "city": h.city,
                "owner_name": h.owner.full_name,
                "owner_business": getattr(h.owner.owner_profile, 'business_name', ''),
                "submitted_date": h.updated_at.isoformat(),
                "min_capacity": h.min_capacity,
                "max_capacity": h.max_capacity,
                "base_price_evening": float(h.base_price_evening),
            })

        # Dispute summary
        open_disputes_count = Dispute.objects.filter(status__in=[DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW]).count()

        return api_response(data={
            "metrics": {
                "total_halls": total_halls,
                "active_owners": active_owners,
                "bookings_this_month": bookings_mtd_count,
                "commission_revenue_mtd": float(commission_mtd),
                "refunds_this_month": refunds_this_month.count(),
                "refund_amount_mtd": float(refund_amount_mtd),
                "total_refunded_bookings": total_refunded_bookings,
                "refunds_due_count": refunds_due_count,
                "refunds_due_amount": float(refunds_due_amount),
                "pending_approvals_count": pending_halls.count(),
                "open_disputes_count": open_disputes_count,
            },
            "pending_approvals": pending_data,
            "refunded_bookings": refunded_bookings,
        })


class AdminOwnerListView(APIView):
    """
    Super Admin Owner Directory (Wireframe Admin Screen 2):
    Search by owner/hall name, filter by status, view venue count, joined date.
    """
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        q = request.query_params.get('q')
        status_filter = request.query_params.get('status')

        queryset = User.objects.filter(role=UserRole.OWNER).select_related('owner_profile').annotate(venue_count=Count('halls')).order_by('-created_at')

        if q:
            queryset = queryset.filter(
                Q(full_name__icontains=q) |
                Q(email__icontains=q) |
                Q(owner_profile__business_name__icontains=q)
            )

        if status_filter:
            if status_filter == 'ACTIVE':
                queryset = queryset.filter(is_active=True, owner_profile__verification_status=OwnerVerificationStatus.VERIFIED)
            elif status_filter == 'UNDER_REVIEW':
                queryset = queryset.filter(owner_profile__verification_status=OwnerVerificationStatus.PENDING)
            elif status_filter == 'SUSPENDED':
                queryset = queryset.filter(Q(is_active=False) | Q(owner_profile__verification_status=OwnerVerificationStatus.SUSPENDED))

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)

        data = []
        for user in page:
            profile = getattr(user, 'owner_profile', None)
            id_proof_url = request.build_absolute_uri(profile.id_proof.url) if profile and profile.id_proof else None
            business_proof_url = request.build_absolute_uri(profile.business_proof.url) if profile and profile.business_proof else None
            data.append({
                "id": str(user.id),
                "full_name": user.full_name,
                "email": user.email,
                "phone": user.phone or "",
                "business_name": profile.business_name if profile else "",
                "locality": profile.locality if profile else "",
                "city": profile.city if profile else "Hyderabad",
                "venue_count": user.venue_count,
                "is_active": user.is_active,
                "verification_status": profile.verification_status if profile else "PENDING",
                "joined_at": user.created_at.isoformat(),
                "id_proof_url": id_proof_url,
                "business_proof_url": business_proof_url,
            })

        return paginator.get_paginated_response(data)


class AdminOwnerActionView(APIView):
    """
    Super Admin actions on venue owners: APPROVE, REJECT, SUSPEND, REACTIVATE.
    """
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        user = User.objects.filter(id=pk, role=UserRole.OWNER).select_related('owner_profile').first()
        if not user:
            return api_response(message="Owner account not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

        action = request.data.get('action')
        profile = getattr(user, 'owner_profile', None)

        if action == 'APPROVE':
            if profile:
                profile.verification_status = OwnerVerificationStatus.VERIFIED
                profile.payout_enabled = True
                profile.save()
            user.is_active = True
            user.save()
            AuditService.log_action(actor=request.user, action="ADMIN_VERIFIED_OWNER", obj=user)
            return api_response(message=f"Owner '{user.full_name}' has been verified.")

        elif action == 'REJECT':
            if profile:
                profile.verification_status = OwnerVerificationStatus.REJECTED
                profile.payout_enabled = False
                profile.notes = request.data.get('notes') or 'Owner verification rejected by admin.'
                profile.save()
            user.is_active = True
            user.save()
            AuditService.log_action(actor=request.user, action="ADMIN_REJECTED_OWNER", obj=user)
            return api_response(message=f"Owner '{user.full_name}' verification rejected.")

        elif action == 'SUSPEND':
            if profile:
                profile.verification_status = OwnerVerificationStatus.SUSPENDED
                profile.payout_enabled = False
                profile.notes = request.data.get('notes') or 'Owner account suspended by admin.'
                profile.save()
            user.is_active = False
            user.save()
            Hall.objects.filter(owner=user).update(status=HallStatus.INACTIVE)
            AuditService.log_action(actor=request.user, action="ADMIN_SUSPENDED_OWNER", obj=user)
            return api_response(message=f"Owner '{user.full_name}' and all associated listings suspended.")

        elif action == 'REACTIVATE':
            if profile:
                profile.verification_status = OwnerVerificationStatus.VERIFIED
                profile.payout_enabled = True
                profile.notes = request.data.get('notes') or 'Owner reactivated by admin.'
                profile.save()
            user.is_active = True
            user.save()
            AuditService.log_action(actor=request.user, action="ADMIN_REACTIVATED_OWNER", obj=user)
            return api_response(message=f"Owner '{user.full_name}' reactivated.")

        return api_response(message="Invalid action.", status_code=status.HTTP_400_BAD_REQUEST, success=False)


class AdminBookingListView(APIView):
    """
    Super Admin real-time monitor across all marketplace bookings.
    """
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        status_filter = request.query_params.get('status')
        queryset = Booking.objects.all().select_related('hall', 'customer', 'hall__owner').order_by('-created_at')

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)

        data = []
        for b in page:
            data.append({
                "id": str(b.id),
                "booking_number": b.booking_number,
                "hall_name": b.hall.name,
                "customer_name": b.contact_name or b.customer.full_name,
                "customer_email": b.customer.email,
                "owner_name": b.hall.owner.full_name,
                "event_date": b.event_date.isoformat(),
                "time_slot": b.time_slot,
                "guest_count": b.guest_count,
                "total_amount": float(b.total_amount),
                "amount_paid": float(b.amount_paid),
                "status": b.status,
                "created_at": b.created_at.isoformat(),
            })

        return paginator.get_paginated_response(data)


class AdminSettingsView(APIView):
    """
    Super Admin configurable platform settings (Commission %, GST Tax %, Advance %, Hold TTL).
    """
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        cache_key = "platform_settings_cache"
        cached_data = cache.get(cache_key)
        if cached_data:
            return api_response(data=cached_data)

        settings_objs = PlatformSetting.objects.all()
        data = {s.key: s.value for s in settings_objs}
        # Defaults if not yet written to DB
        if "PLATFORM_COMMISSION_PCT" not in data:
            data["PLATFORM_COMMISSION_PCT"] = {"percentage": 10.0}
        if "DEFAULT_GST_TAX_RATE" not in data:
            data["DEFAULT_GST_TAX_RATE"] = {"rate": 18.0}
        if "DEFAULT_ADVANCE_PCT" not in data:
            data["DEFAULT_ADVANCE_PCT"] = {"percentage": 20.0}
        if "BOOKING_HOLD_TTL_MINUTES" not in data:
            data["BOOKING_HOLD_TTL_MINUTES"] = {"minutes": 15}

        cache.set(cache_key, data, timeout=3600)
        return api_response(data=data)

    def patch(self, request):
        updates = request.data
        for key, value in updates.items():
            setting, created = PlatformSetting.objects.get_or_create(
                key=key,
                defaults={"value": value, "updated_by": request.user}
            )
            old_val = setting.value
            setting.value = value
            setting.updated_by = request.user
            setting.save()

            AuditService.log_action(
                actor=request.user,
                action="ADMIN_UPDATED_PLATFORM_SETTING",
                obj=setting,
                changes={"key": key, "old": old_val, "new": value}
            )

        # Invalidate platform settings cache
        cache.delete("platform_settings_cache")

        return api_response(message="Platform settings updated successfully.")


class AdminAuditLogListView(APIView):
    """
    Super Admin filterable immutable audit trail.
    """
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        action_filter = request.query_params.get('action')
        queryset = AuditLog.objects.all().select_related('actor').order_by('-created_at')

        if action_filter:
            queryset = queryset.filter(action=action_filter)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)

        data = []
        for log in page:
            data.append({
                "id": log.id,
                "actor_email": log.actor.email if log.actor else "SYSTEM",
                "actor_role": getattr(log.actor, 'role', 'SYSTEM'),
                "action": log.action,
                "object_type": log.object_type,
                "object_id": log.object_id,
                "ip_address": log.ip_address,
                "changes": log.changes,
                "created_at": log.created_at.isoformat(),
            })

        return paginator.get_paginated_response(data)
