from django.urls import path
from apps.favorites.views import (
    FavoriteListView,
    ToggleFavoriteView,
)

urlpatterns = [
    path('favorites/', FavoriteListView.as_view(), name='favorite-list'),
    path('favorites/<uuid:hall_id>/toggle/', ToggleFavoriteView.as_view(), name='favorite-toggle'),
]
