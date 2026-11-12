from rest_framework import serializers
from apps.notifications.models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id',
            'title',
            'message',
            'type',
            'is_read',
            'read_at',
            'related_entity_type',
            'related_entity_id',
            'created_at'
        ]
        read_only_fields = ['id', 'title', 'message', 'type', 'created_at']
