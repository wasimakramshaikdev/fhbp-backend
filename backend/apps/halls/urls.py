from django.urls import path
from apps.halls.views import (
    PublicHallListView,
    PublicFeaturedHallsView,
    PublicAmenityListView,
    PublicHallDetailView,
    OwnerHallListCreateView,
    OwnerHallDetailView,
    OwnerHallSubmitView,
    OwnerHallToggleStatusView,
    OwnerHallImageUploadView,
    OwnerHallImageDeleteView,
    AdminHallListView,
    AdminHallActionView,
)

urlpatterns = [
    # Public Endpoints
    path('halls/', PublicHallListView.as_view(), name='public-hall-list'),
    path('halls/featured/', PublicFeaturedHallsView.as_view(), name='public-featured-halls'),
    path('halls/amenities/', PublicAmenityListView.as_view(), name='public-amenity-list'),
    path('halls/<str:id_or_slug>/', PublicHallDetailView.as_view(), name='public-hall-detail'),

    # Owner Management Endpoints
    path('owner/listings/', OwnerHallListCreateView.as_view(), name='owner-hall-list-create'),
    path('owner/listings/<uuid:pk>/', OwnerHallDetailView.as_view(), name='owner-hall-detail'),
    path('owner/listings/<uuid:pk>/submit/', OwnerHallSubmitView.as_view(), name='owner-hall-submit'),
    path('owner/listings/<uuid:pk>/toggle-status/', OwnerHallToggleStatusView.as_view(), name='owner-hall-toggle-status'),
    path('owner/listings/<uuid:pk>/images/', OwnerHallImageUploadView.as_view(), name='owner-hall-image-upload'),
    path('owner/listings/<uuid:pk>/images/<uuid:img_id>/', OwnerHallImageDeleteView.as_view(), name='owner-hall-image-delete'),

    # Super Admin Endpoints
    path('admin/halls/', AdminHallListView.as_view(), name='admin-hall-list'),
    path('admin/halls/<uuid:pk>/action/', AdminHallActionView.as_view(), name='admin-hall-action'),
]
