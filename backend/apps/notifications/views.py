from datetime import datetime, timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from apps.core.responses import api_response
from apps.core.pagination import StandardPagination
from apps.notifications.models import Notification
from apps.notifications.serializers import NotificationSerializer

class NotificationListView(APIView):
    """
    Returns user notification feed with read/unread filtering and pagination.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Notification.objects.filter(user=request.user).order_by('-created_at')
        unread_only = request.query_params.get('unread')
        if unread_only == 'true':
            queryset = queryset.filter(is_read=False)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = NotificationSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class NotificationUnreadCountView(APIView):
    """
    Returns total unread notification count for the badge counter.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return api_response(data={"unread_count": count})


class NotificationMarkReadView(APIView):
    """
    Marks a single notification as read.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        notification = Notification.objects.filter(id=pk, user=request.user).first()
        if not notification:
            return api_response(message="Notification not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

        notification.mark_as_read()
        return api_response(data=NotificationSerializer(notification).data, message="Marked as read.")


class NotificationMarkAllReadView(APIView):
    """
    Marks all notifications for the user as read.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True,
            read_at=datetime.now(timezone.utc)
        )
        return api_response(message="All notifications marked as read.")
