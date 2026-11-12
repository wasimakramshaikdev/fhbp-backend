from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from apps.core.responses import api_response
from apps.core.pagination import StandardPagination
from apps.halls.models import Hall
from apps.favorites.models import Favorite
from apps.favorites.serializers import FavoriteSerializer

class FavoriteListView(APIView):
    """
    Lists all saved function halls for the authenticated customer.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        favorites = Favorite.objects.filter(customer=request.user).select_related('hall', 'hall__owner').order_by('-created_at')
        paginator = StandardPagination()
        page = paginator.paginate_queryset(favorites, request)
        serializer = FavoriteSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ToggleFavoriteView(APIView):
    """
    Adds or removes a venue from customer favorites.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, hall_id):
        hall = Hall.objects.filter(id=hall_id).first()
        if not hall:
            return api_response(message="Function hall not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

        fav = Favorite.objects.filter(customer=request.user, hall=hall).first()
        if fav:
            fav.delete()
            return api_response(
                data={"is_favorited": False},
                message=f"Removed '{hall.name}' from your saved venues."
            )
        else:
            Favorite.objects.create(customer=request.user, hall=hall)
            return api_response(
                data={"is_favorited": True},
                message=f"Added '{hall.name}' to your saved venues."
            )
