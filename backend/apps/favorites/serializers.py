from rest_framework import serializers
from apps.favorites.models import Favorite
from apps.halls.serializers import HallListSerializer

class FavoriteSerializer(serializers.ModelSerializer):
    hall = HallListSerializer(read_only=True)

    class Meta:
        model = Favorite
        fields = ['id', 'hall', 'created_at']
