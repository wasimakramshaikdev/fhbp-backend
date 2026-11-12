from rest_framework import serializers
from apps.reviews.models import Review

class ReviewSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_avatar = serializers.CharField(source='customer.avatar_url', read_only=True)
    hall_name = serializers.CharField(source='hall.name', read_only=True)
    hall_slug = serializers.CharField(source='hall.slug', read_only=True)

    class Meta:
        model = Review
        fields = [
            'id',
            'booking_id',
            'customer_id',
            'customer_name',
            'customer_avatar',
            'hall_id',
            'hall_name',
            'hall_slug',
            'rating',
            'comment',
            'owner_response',
            'owner_responded_at',
            'created_at'
        ]
        read_only_fields = ['id', 'booking_id', 'customer_id', 'hall_id', 'created_at']


class ReviewCreateSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5, required=True)
    comment = serializers.CharField(min_length=5, required=True)


class ReviewResponseSerializer(serializers.Serializer):
    owner_response = serializers.CharField(min_length=2, required=True)
