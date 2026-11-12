# import logging
# from datetime import datetime, timezone
# from django.db.models import Q
# from django.core.cache import cache
# from rest_framework.views import APIView
# from rest_framework.permissions import AllowAny, IsAuthenticated
# from rest_framework import status
# from apps.core.responses import api_response
# from apps.core.pagination import StandardPagination
# from apps.core.services.audit import AuditService
# from apps.accounts.permissions import IsOwnerRole, IsAdminRole, IsOwnerOrAdmin
# from apps.halls.models import Hall, HallImage, Amenity, HallApprovalStatus, HallStatus
# from apps.halls.serializers import (
#     AmenitySerializer,
#     HallImageSerializer,
#     HallListSerializer,
#     HallDetailSerializer,
#     HallCreateUpdateSerializer,
#     AdminHallApprovalSerializer,
# )

# logger = logging.getLogger(__name__)

# class PublicHallListView(APIView):
#     """
#     Public search endpoint returning only APPROVED & ACTIVE function halls.
#     """
#     permission_classes = [AllowAny]
#     authentication_classes = []

#     def get(self, request):
#         queryset = Hall.objects.filter(
#             approval_status=HallApprovalStatus.APPROVED,
#             status=HallStatus.ACTIVE
#         ).select_related('owner', 'owner__owner_profile').prefetch_related('amenities', 'images')

#         # Filters
#         q = request.query_params.get('q')
#         city = request.query_params.get('city')
#         locality = request.query_params.get('locality')
#         hall_type = request.query_params.get('hall_type')
#         guests = request.query_params.get('guests')
#         capacity_min = request.query_params.get('capacity_min')
#         capacity_max = request.query_params.get('capacity_max')
#         price_min = request.query_params.get('price_min')
#         price_max = request.query_params.get('price_max')
#         min_rating = request.query_params.get('min_rating')
#         amenities = request.query_params.getlist('amenities')
#         sort = request.query_params.get('sort', 'recommended')

#         if q:
#             queryset = queryset.filter(
#                 Q(name__icontains=q) |
#                 Q(description__icontains=q) |
#                 Q(locality__icontains=q) |
#                 Q(address_line1__icontains=q)
#             )

#         if city:
#             queryset = queryset.filter(city__iexact=city)
#         if locality:
#             queryset = queryset.filter(locality__iexact=locality)
#         if hall_type:
#             queryset = queryset.filter(hall_type=hall_type)
#         if guests:
#             try:
#                 g_val = int(guests)
#                 queryset = queryset.filter(min_capacity__lte=g_val, max_capacity__gte=g_val)
#             except ValueError:
#                 pass
#         if capacity_min:
#             try:
#                 queryset = queryset.filter(max_capacity__gte=int(capacity_min))
#             except ValueError:
#                 pass
#         if capacity_max:
#             try:
#                 queryset = queryset.filter(min_capacity__lte=int(capacity_max))
#             except ValueError:
#                 pass
#         if price_min:
#             try:
#                 queryset = queryset.filter(base_price_morning__gte=float(price_min))
#             except ValueError:
#                 pass
#         if price_max:
#             try:
#                 queryset = queryset.filter(base_price_morning__lte=float(price_max))
#             except ValueError:
#                 pass
#         if min_rating:
#             try:
#                 queryset = queryset.filter(avg_rating__gte=float(min_rating))
#             except ValueError:
#                 pass
#         if amenities:
#             for am in amenities:
#                 if am.strip():
#                     queryset = queryset.filter(amenities__slug=am.strip())

#         # Sorting
#         if sort == 'price_asc':
#             queryset = queryset.order_by('base_price_morning')
#         elif sort == 'price_desc':
#             queryset = queryset.order_by('-base_price_morning')
#         elif sort == 'rating' or sort == 'rating_desc':
#             queryset = queryset.order_by('-avg_rating', '-review_count')
#         elif sort == 'capacity_desc':
#             queryset = queryset.order_by('-max_capacity')
#         elif sort == 'capacity_asc':
#             queryset = queryset.order_by('min_capacity')
#         else:
#             # Recommended sort: highest rated + review count + newest
#             queryset = queryset.order_by('-avg_rating', '-review_count', '-created_at')

#         paginator = StandardPagination()
#         page = paginator.paginate_queryset(queryset, request)
#         serializer = HallListSerializer(page, many=True)
#         return paginator.get_paginated_response(serializer.data)


# class PublicFeaturedHallsView(APIView):
#     """
#     Returns curated top-rated featured halls for homepage display (cached in Redis).
#     """
#     permission_classes = [AllowAny]
#     authentication_classes = []

#     def get(self, request):
#         cache_key = "featured_halls_homepage"
#         cached_data = cache.get(cache_key)
#         if cached_data:
#             return api_response(data=cached_data)

#         halls = Hall.objects.filter(
#             approval_status=HallApprovalStatus.APPROVED,
#             status=HallStatus.ACTIVE
#         ).select_related('owner', 'owner__owner_profile').prefetch_related('amenities', 'images').order_by('-avg_rating', '-created_at')[:6]

#         serializer = HallListSerializer(halls, many=True)
#         cache.set(cache_key, serializer.data, timeout=300) # 5 minutes cache
#         return api_response(data=serializer.data)


# class PublicAmenityListView(APIView):
#     """Catalog of active venue amenities (cached in Redis)."""
#     permission_classes = [AllowAny]
#     authentication_classes = []

#     def get(self, request):
#         cache_key = "public_amenities_catalog"
#         cached_data = cache.get(cache_key)
#         if cached_data:
#             return api_response(data=cached_data)

#         amenities = Amenity.objects.filter(is_active=True).order_by('name')
#         serializer = AmenitySerializer(amenities, many=True)
#         cache.set(cache_key, serializer.data, timeout=3600) # 1 hour cache
#         return api_response(data=serializer.data)


# class PublicHallDetailView(APIView):
#     """
#     Public detailed view of a single function hall by slug or UUID.
#     Unapproved halls are restricted unless requested by owner or admin.
#     """
#     permission_classes = [AllowAny]

#     def get(self, request, id_or_slug):
#         import uuid
#         is_uuid = False
#         try:
#             uuid.UUID(str(id_or_slug))
#             is_uuid = True
#         except (ValueError, TypeError, AttributeError):
#             is_uuid = False

#         if is_uuid:
#             query = Q(id=id_or_slug) | Q(slug=id_or_slug)
#         else:
#             query = Q(slug=id_or_slug)

#         hall = Hall.objects.filter(query).select_related('owner', 'owner__owner_profile').prefetch_related('amenities', 'images').first()
#         if not hall:
#             return api_response(
#                 message="Function hall not found.",
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 success=False,
#                 code="NOT_FOUND"
#             )

#         # Access check for non-approved listings
#         if hall.approval_status != HallApprovalStatus.APPROVED:
#             user = request.user
#             if not user or not user.is_authenticated or (user != hall.owner and not user.is_admin):
#                 return api_response(
#                     message="This venue listing is currently under review or inactive.",
#                     status_code=status.HTTP_404_NOT_FOUND,
#                     success=False,
#                     code="NOT_PUBLIC"
#                 )

#         serializer = HallDetailSerializer(hall)
#         return api_response(data=serializer.data)


# class OwnerHallListCreateView(APIView):
#     """
#     Lists all halls belonging to the authenticated Owner, or creates a new draft listing.
#     """
#     permission_classes = [IsAuthenticated, IsOwnerRole]

#     def get(self, request):
#         halls = Hall.objects.filter(owner=request.user).prefetch_related('amenities', 'images').order_by('-created_at')
#         serializer = HallDetailSerializer(halls, many=True)
#         return api_response(data=serializer.data)

#     def post(self, request):
#         serializer = HallCreateUpdateSerializer(data=request.data, context={'request': request})
#         if not serializer.is_valid():
#             return api_response(
#                 message="Listing validation failed.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="VALIDATION_ERROR"
#             )

#         hall = serializer.save()
#         AuditService.log_action(
#             actor=request.user,
#             action="HALL_CREATED_DRAFT",
#             obj=hall,
#             ip_address=request.META.get('REMOTE_ADDR'),
#             changes={"name": hall.name, "locality": hall.locality}
#         )

#         return api_response(
#             data=HallDetailSerializer(hall).data,
#             message="Venue listing created successfully as Draft.",
#             status_code=status.HTTP_201_CREATED
#         )


# class OwnerHallDetailView(APIView):
#     """
#     Retrieves, updates, or deletes an owner's specific function hall listing.
#     """
#     permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

#     def get_object(self, request, pk):
#         hall = Hall.objects.filter(id=pk).prefetch_related('amenities', 'images').first()
#         if not hall:
#             return None
#         if hall.owner != request.user and not request.user.is_admin:
#             return "FORBIDDEN"
#         return hall

#     def get(self, request, pk):
#         hall = self.get_object(request, pk)
#         if hall is None:
#             return api_response(message="Venue not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)
#         if hall == "FORBIDDEN":
#             return api_response(message="You do not have permission to access this venue.", status_code=status.HTTP_403_FORBIDDEN, success=False)
#         return api_response(data=HallDetailSerializer(hall).data)

#     def patch(self, request, pk):
#         hall = self.get_object(request, pk)
#         if hall is None:
#             return api_response(message="Venue not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)
#         if hall == "FORBIDDEN":
#             return api_response(message="You do not have permission to modify this venue.", status_code=status.HTTP_403_FORBIDDEN, success=False)

#         serializer = HallCreateUpdateSerializer(hall, data=request.data, partial=True, context={'request': request})
#         if not serializer.is_valid():
#             return api_response(
#                 message="Update validation failed.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="VALIDATION_ERROR"
#             )

#         updated_hall = serializer.save()
#         # Invalidate featured cache
#         cache.delete("featured_halls_homepage")

#         AuditService.log_action(
#             actor=request.user,
#             action="HALL_UPDATED",
#             obj=updated_hall,
#             ip_address=request.META.get('REMOTE_ADDR')
#         )

#         return api_response(
#             data=HallDetailSerializer(updated_hall).data,
#             message="Venue listing updated successfully."
#         )


# class OwnerHallSubmitView(APIView):
#     """
#     Submits a draft or rejected hall listing to the Super Admin queue for verification & approval.
#     """
#     permission_classes = [IsAuthenticated, IsOwnerRole]

#     def post(self, request, pk):
#         hall = Hall.objects.filter(id=pk, owner=request.user).first()
#         if not hall:
#             return api_response(message="Venue not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

#         if hall.approval_status not in [HallApprovalStatus.DRAFT, HallApprovalStatus.REJECTED]:
#             return api_response(
#                 message=f"Cannot submit venue in '{hall.approval_status}' state.",
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False,
#                 code="INVALID_STATE"
#             )

#         hall.approval_status = HallApprovalStatus.UNDER_REVIEW
#         hall.rejection_reason = ""
#         hall.save()

#         AuditService.log_action(
#             actor=request.user,
#             action="HALL_SUBMITTED_FOR_REVIEW",
#             obj=hall,
#             ip_address=request.META.get('REMOTE_ADDR')
#         )

#         return api_response(
#             data=HallDetailSerializer(hall).data,
#             message="Venue submitted for platform review. An administrator will verify and approve your listing."
#         )


# class OwnerHallToggleStatusView(APIView):
#     """
#     Enables/disables public availability for approved listings.
#     """
#     permission_classes = [IsAuthenticated, IsOwnerRole]

#     def post(self, request, pk):
#         hall = Hall.objects.filter(id=pk, owner=request.user).first()
#         if not hall:
#             return api_response(message="Venue not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

#         if hall.approval_status != HallApprovalStatus.APPROVED:
#             return api_response(
#                 message="Only approved venues can toggle operational status.",
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False
#             )

#         hall.status = HallStatus.INACTIVE if hall.status == HallStatus.ACTIVE else HallStatus.ACTIVE
#         hall.save()
#         cache.delete("featured_halls_homepage")

#         AuditService.log_action(
#             actor=request.user,
#             action="HALL_STATUS_TOGGLED",
#             obj=hall,
#             changes={"status": hall.status}
#         )

#         return api_response(
#             data={"status": hall.status},
#             message=f"Venue status updated to {hall.status}."
#         )


# class OwnerHallImageUploadView(APIView):
#     """
#     Adds images to hall gallery.
#     """
#     permission_classes = [IsAuthenticated, IsOwnerRole]

#     def post(self, request, pk):
#         hall = Hall.objects.filter(id=pk, owner=request.user).first()
#         if not hall:
#             return api_response(message="Venue not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

#         image_urls = request.data.get('images', [])
#         if isinstance(image_urls, str):
#             image_urls = [image_urls]

#         if not image_urls:
#             return api_response(
#                 message="No image URLs provided.",
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False
#             )

#         from apps.halls.serializers import validate_safe_image_url
#         validated_urls = []
#         for url in image_urls:
#             try:
#                 validated_urls.append(validate_safe_image_url(url))
#             except Exception as e:
#                 return api_response(message=str(e), status_code=status.HTTP_400_BAD_REQUEST, success=False)

#         created_images = []
#         existing_count = hall.images.count()
#         for idx, url in enumerate(validated_urls):
#             img = HallImage.objects.create(
#                 hall=hall,
#                 image_url=url,
#                 sort_order=existing_count + idx,
#                 is_primary=(existing_count == 0 and idx == 0)
#             )
#             created_images.append(img)

#         return api_response(
#             data=HallImageSerializer(created_images, many=True).data,
#             message="Images uploaded successfully."
#         )


# class OwnerHallImageDeleteView(APIView):
#     """
#     Deletes an image from a hall's gallery.
#     """
#     permission_classes = [IsAuthenticated, IsOwnerRole]

#     def delete(self, request, pk, img_id):
#         img = HallImage.objects.filter(id=img_id, hall_id=pk, hall__owner=request.user).first()
#         if not img:
#             return api_response(message="Image not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

#         was_primary = img.is_primary
#         hall = img.hall
#         img.delete()

#         if was_primary:
#             next_img = hall.images.first()
#             if next_img:
#                 next_img.is_primary = True
#                 next_img.save()

#         return api_response(message="Image deleted successfully.")


# class AdminHallListView(APIView):
#     """
#     Super Admin listing of all halls with approval status filtering.
#     """
#     permission_classes = [IsAuthenticated, IsAdminRole]

#     def get(self, request):
#         status_filter = request.query_params.get('status')
#         queryset = Hall.objects.all().select_related('owner', 'owner__owner_profile').prefetch_related('amenities', 'images').order_by('-created_at')

#         if status_filter:
#             queryset = queryset.filter(approval_status=status_filter)

#         serializer = HallDetailSerializer(queryset, many=True)
#         return api_response(data=serializer.data)


# class AdminHallActionView(APIView):
#     """
#     Super Admin decision: APPROVE, REJECT, or SUSPEND listing.
#     """
#     permission_classes = [IsAuthenticated, IsAdminRole]

#     def post(self, request, pk):
#         hall = Hall.objects.filter(id=pk).first()
#         if not hall:
#             return api_response(message="Venue not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

#         serializer = AdminHallApprovalSerializer(data=request.data)
#         if not serializer.is_valid():
#             return api_response(
#                 message="Decision payload invalid.",
#                 errors=serializer.errors,
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 success=False
#             )

#         action = serializer.validated_data['action']
#         reason = serializer.validated_data.get('reason', '')

#         if action == 'APPROVE':
#             hall.approval_status = HallApprovalStatus.APPROVED
#             hall.status = HallStatus.ACTIVE
#             hall.rejection_reason = ""
#             hall.approved_by = request.user
#             hall.approved_at = datetime.now(timezone.utc)
#             hall.save()
#             cache.delete("featured_halls_homepage")

#             AuditService.log_action(
#                 actor=request.user,
#                 action="ADMIN_APPROVED_HALL",
#                 obj=hall,
#                 changes={"status": "APPROVED"}
#             )
#             return api_response(
#                 data=HallDetailSerializer(hall).data,
#                 message=f"Venue '{hall.name}' has been approved and is now live on the marketplace."
#             )

#         elif action == 'REJECT':
#             hall.approval_status = HallApprovalStatus.REJECTED
#             hall.rejection_reason = reason
#             hall.save()
#             cache.delete("featured_halls_homepage")

#             AuditService.log_action(
#                 actor=request.user,
#                 action="ADMIN_REJECTED_HALL",
#                 obj=hall,
#                 changes={"status": "REJECTED", "reason": reason}
#             )
#             return api_response(
#                 data=HallDetailSerializer(hall).data,
#                 message=f"Venue '{hall.name}' has been rejected."
#             )

#         elif action == 'SUSPEND':
#             hall.approval_status = HallApprovalStatus.SUSPENDED
#             hall.status = HallStatus.INACTIVE
#             hall.save()
#             cache.delete("featured_halls_homepage")

#             AuditService.log_action(
#                 actor=request.user,
#                 action="ADMIN_SUSPENDED_HALL",
#                 obj=hall,
#                 changes={"status": "SUSPENDED"}
#             )
#             return api_response(
#                 data=HallDetailSerializer(hall).data,
#                 message=f"Venue '{hall.name}' has been suspended from the marketplace."
#             )




# import logging
# import uuid
# from datetime import datetime, timezone

# from django.core.cache import cache
# from django.db.models import Q
# from drf_spectacular.types import OpenApiTypes
# from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
# from rest_framework import status
# from rest_framework.permissions import AllowAny, IsAuthenticated
# from rest_framework.views import APIView

# from apps.accounts.permissions import IsAdminRole, IsOwnerOrAdmin, IsOwnerRole
# from apps.core.pagination import StandardPagination
# from apps.core.responses import api_response
# from apps.core.services.audit import AuditService
# from apps.halls.models import Amenity, Hall, HallApprovalStatus, HallImage, HallStatus
# from apps.halls.serializers import (
#     AdminHallApprovalSerializer,
#     AmenitySerializer,
#     HallCreateUpdateSerializer,
#     HallDetailSerializer,
#     HallImageSerializer,
#     HallListSerializer,
# )

# logger = logging.getLogger(__name__)


# # ---------------------------------------------------------------------------
# # Public Endpoints
# # ---------------------------------------------------------------------------

# @extend_schema(
#     summary="Search & List Function Halls",
#     description="Public search endpoint returning only APPROVED & ACTIVE function halls with filtering and sorting.",
#     parameters=[
#         OpenApiParameter(name="q", type=OpenApiTypes.STR, description="Search term for name, description, or locality"),
#         OpenApiParameter(name="city", type=OpenApiTypes.STR, description="Filter by city name"),
#         OpenApiParameter(name="locality", type=OpenApiTypes.STR, description="Filter by locality/area"),
#         OpenApiParameter(name="hall_type", type=OpenApiTypes.STR, description="Filter by HallType enum"),
#         OpenApiParameter(name="guests", type=OpenApiTypes.INT, description="Required guest count capacity"),
#         OpenApiParameter(name="capacity_min", type=OpenApiTypes.INT, description="Minimum venue capacity"),
#         OpenApiParameter(name="capacity_max", type=OpenApiTypes.INT, description="Maximum venue capacity"),
#         OpenApiParameter(name="price_min", type=OpenApiTypes.FLOAT, description="Minimum morning slot base price"),
#         OpenApiParameter(name="price_max", type=OpenApiTypes.FLOAT, description="Maximum morning slot base price"),
#         OpenApiParameter(name="min_rating", type=OpenApiTypes.FLOAT, description="Minimum average rating"),
#         OpenApiParameter(name="amenities", type=OpenApiTypes.STR, many=True, description="Filter by amenity slug(s)"),
#         OpenApiParameter(name="sort", type=OpenApiTypes.STR, description="Sorting option: price_asc, price_desc, rating, capacity_asc, capacity_desc, recommended"),
#     ],
#     responses={200: HallListSerializer(many=True)},
# )
# class PublicHallListView(APIView):
#     permission_classes = [AllowAny]
#     authentication_classes = []
#     serializer_class = HallListSerializer

#     def get(self, request):
#         queryset = Hall.objects.filter(
#             approval_status=HallApprovalStatus.APPROVED,
#             status=HallStatus.ACTIVE
#         ).select_related('owner', 'owner__owner_profile').prefetch_related('amenities', 'images')

#         # Filters
#         q = request.query_params.get('q')
#         city = request.query_params.get('city')
#         locality = request.query_params.get('locality')
#         hall_type = request.query_params.get('hall_type')
#         guests = request.query_params.get('guests')
#         capacity_min = request.query_params.get('capacity_min')
#         capacity_max = request.query_params.get('capacity_max')
#         price_min = request.query_params.get('price_min')
#         price_max = request.query_params.get('price_max')
#         min_rating = request.query_params.get('min_rating')
#         amenities = request.query_params.getlist('amenities')
#         sort = request.query_params.get('sort', 'recommended')

#         if q:
#             queryset = queryset.filter(
#                 Q(name__icontains=q) |
#                 Q(description__icontains=q) |
#                 Q(locality__icontains=q) |
#                 Q(address_line1__icontains=q)
#             )

#         if city:
#             queryset = queryset.filter(city__iexact=city)
#         if locality:
#             queryset = queryset.filter(locality__iexact=locality)
#         if hall_type:
#             queryset = queryset.filter(hall_type=hall_type)
#         if guests:
#             try:
#                 g_val = int(guests)
#                 queryset = queryset.filter(min_capacity__lte=g_val, max_capacity__gte=g_val)
#             except ValueError:
#                 pass
#         if capacity_min:
#             try:
#                 queryset = queryset.filter(max_capacity__gte=int(capacity_min))
#             except ValueError:
#                 pass
#         if capacity_max:
#             try:
#                 queryset = queryset.filter(min_capacity__lte=int(capacity_max))
#             except ValueError:
#                 pass
#         if price_min:
#             try:
#                 queryset = queryset.filter(base_price_morning__gte=float(price_min))
#             except ValueError:
#                 pass
#         if price_max:
#             try:
#                 queryset = queryset.filter(base_price_morning__lte=float(price_max))
#             except ValueError:
#                 pass
#         if min_rating:
#             try:
#                 queryset = queryset.filter(avg_rating__gte=float(min_rating))
#             except ValueError:
#                 pass
#         if amenities:
#             for am in amenities:
#                 if am.strip():
#                     queryset = queryset.filter(amenities__slug=am.strip())

#         # Sorting
#         if sort == 'price_asc':
#             queryset = queryset.order_by('base_price_morning')
#         elif sort == 'price_desc':
#             queryset = queryset.order_by('-base_price_morning')
#         elif sort == 'rating' or sort == 'rating_desc':
#             queryset = queryset.order_by('-avg_rating', '-review_count')
#         elif sort == 'capacity_desc':
#             queryset = queryset.order_by('-max_capacity')
#         elif sort == 'capacity_asc':
#             queryset = queryset.order_by('min_capacity')
#         else:
#             queryset = queryset.order_by('-avg_rating', '-review_count', '-created_at')

#         paginator = StandardPagination()
#         page = paginator.paginate_queryset(queryset, request)
#         serializer = self.serializer_class(page, many=True)
#         return paginator.get_paginated_response(serializer.data)


# @extend_schema(
#     summary="Get Featured Halls",
#     description="Returns top-rated featured halls for the homepage display (Cached in Redis for 5 minutes).",
#     responses={200: HallListSerializer(many=True)}
# )
# class PublicFeaturedHallsView(APIView):
#     permission_classes = [AllowAny]
#     authentication_classes = []
#     serializer_class = HallListSerializer

#     def get(self, request):
#         cache_key = "featured_halls_homepage"
#         cached_data = cache.get(cache_key)
#         if cached_data:
#             return api_response(data=cached_data)

#         halls = Hall.objects.filter(
#             approval_status=HallApprovalStatus.APPROVED,
#             status=HallStatus.ACTIVE
#         ).select_related('owner', 'owner__owner_profile').prefetch_related('amenities', 'images').order_by('-avg_rating', '-created_at')[:6]

#         serializer = self.serializer_class(halls, many=True)
#         cache.set(cache_key, serializer.data, timeout=300)
#         return api_response(data=serializer.data)


# @extend_schema(
#     summary="Get Amenities Catalog",
#     description="Catalog of active venue amenities (Cached in Redis for 1 hour).",
#     responses={200: AmenitySerializer(many=True)}
# )
# class PublicAmenityListView(APIView):
#     permission_classes = [AllowAny]
#     authentication_classes = []
#     serializer_class = AmenitySerializer

#     def get(self, request):
#         cache_key = "public_amenities_catalog"
#         cached_data = cache.get(cache_key)
#         if cached_data:
#             return api_response(data=cached_data)

#         amenities = Amenity.objects.filter(is_active=True).order_by('name')
#         serializer = self.serializer_class(amenities, many=True)
#         cache.set(cache_key, serializer.data, timeout=3600)
#         return api_response(data=serializer.data)


# @extend_schema(
#     summary="Get Public Hall Details",
#     description="Public detailed view of a single function hall by slug or UUID. Unapproved halls are restricted unless requested by owner or admin.",
#     responses={
#         200: HallDetailSerializer,
#         404: OpenApiTypes.OBJECT
#     }
# )
# class PublicHallDetailView(APIView):
#     permission_classes = [AllowAny]
#     serializer_class = HallDetailSerializer

#     def get(self, request, id_or_slug):
#         is_uuid = False
#         try:
#             uuid.UUID(str(id_or_slug))
#             is_uuid = True
#         except (ValueError, TypeError, AttributeError):
#             is_uuid = False

#         if is_uuid:
#             query = Q(id=id_or_slug) | Q(slug=id_or_slug)
#         else:
#             query = Q(slug=id_or_slug)

#         hall = Hall.objects.filter(query).select_related('owner', 'owner__owner_profile').prefetch_related('amenities', 'images').first()
#         if not hall:
#             return api_response(
#                 message="Function hall not found.",
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 success=False,
#                 code="NOT_FOUND"
#             )

#         if hall.approval_status != HallApprovalStatus.APPROVED:
#             user = request.user
#             if not user or not user.is_authenticated or (user != hall.owner and not getattr(user, 'is_admin', False)):
#                 return api_response(
#                     message="This venue listing is currently under review or inactive.",
#                     status_code=status.HTTP_404_NOT_FOUND,
#                     success=False,
#                     code="NOT_PUBLIC"
#                 )

#         serializer = self.serializer_class(hall)
#         return api_response(data=serializer.data)


# # ---------------------------------------------------------------------------
# # Hall Owner Endpoints
# # ---------------------------------------------------------------------------

# @extend_schema_view(
#     get=extend_schema(
#         summary="List Owner Halls",
#         description="List all halls owned by the authenticated owner.",
#         responses={200: HallListSerializer(many=True)}
#     ),
#     post=extend_schema(
#         summary="Create Hall Listing",
#         description="Creates a new function hall listing in DRAFT state.",
#         request=HallCreateUpdateSerializer,
#         responses={201: HallDetailSerializer}
#     )
# )
# class OwnerHallListCreateView(APIView):
#     permission_classes = [IsAuthenticated, IsOwnerRole]

#     def get_serializer_class(self):
#         if self.request.method == 'POST':
#             return HallCreateUpdateSerializer
#         return HallListSerializer

#     def get(self, request):
#         halls = Hall.objects.filter(owner=request.user).prefetch_related('amenities', 'images')
#         serializer = HallListSerializer(halls, many=True)
#         return api_response(data=serializer.data)

#     def post(self, request):
#         serializer = HallCreateUpdateSerializer(data=request.data, context={'request': request})
#         if serializer.is_valid():
#             hall = serializer.save()
            
#             # Invalidate featured homepage cache
#             cache.delete("featured_halls_homepage")
            
#             AuditService.log_action(
#                 user=request.user,
#                 action="HALL_CREATED",
#                 target_type="Hall",
#                 target_id=str(hall.id),
#                 details={"name": hall.name}
#             )
            
#             detail_serializer = HallDetailSerializer(hall)
#             return api_response(
#                 data=detail_serializer.data,
#                 message="Hall created successfully and submitted for review.",
#                 status_code=status.HTTP_201_CREATED
#             )
#         return api_response(
#             message="Validation error.",
#             errors=serializer.errors,
#             status_code=status.HTTP_400_BAD_REQUEST,
#             success=False
#         )


# @extend_schema_view(
#     get=extend_schema(
#         summary="Get Owner Hall Detail",
#         description="Retrieve details of a specific hall owned by the authenticated user.",
#         responses={200: HallDetailSerializer}
#     ),
#     patch=extend_schema(
#         summary="Update Owner Hall",
#         description="Update details of a specific hall owned by the authenticated user.",
#         request=HallCreateUpdateSerializer,
#         responses={200: HallDetailSerializer}
#     )
# )
# class OwnerHallDetailView(APIView):
#     permission_classes = [IsAuthenticated, IsOwnerRole]

#     def get_serializer_class(self):
#         if self.request.method in ['PUT', 'PATCH']:
#             return HallCreateUpdateSerializer
#         return HallDetailSerializer

#     def get_object(self, hall_id, user):
#         return Hall.objects.filter(id=hall_id, owner=user).prefetch_related('amenities', 'images').first()

#     def get(self, request, hall_id):
#         hall = self.get_object(hall_id, request.user)
#         if not hall:
#             return api_response(message="Hall not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)
#         serializer = HallDetailSerializer(hall)
#         return api_response(data=serializer.data)

#     def patch(self, request, hall_id):
#         hall = self.get_object(hall_id, request.user)
#         if not hall:
#             return api_response(message="Hall not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

#         serializer = HallCreateUpdateSerializer(hall, data=request.data, partial=True, context={'request': request})
#         if serializer.is_valid():
#             updated_hall = serializer.save()
            
#             # Reset to UNDER_REVIEW if edited after rejection
#             if updated_hall.approval_status == HallApprovalStatus.REJECTED:
#                 updated_hall.approval_status = HallApprovalStatus.UNDER_REVIEW
#                 updated_hall.save(update_fields=['approval_status'])

#             cache.delete("featured_halls_homepage")

#             AuditService.log_action(
#                 user=request.user,
#                 action="HALL_UPDATED",
#                 target_type="Hall",
#                 target_id=str(updated_hall.id)
#             )

#             detail_serializer = HallDetailSerializer(updated_hall)
#             return api_response(data=detail_serializer.data, message="Hall updated successfully.")
#         return api_response(message="Validation error.", errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST, success=False)


# # ---------------------------------------------------------------------------
# # Admin Endpoints
# # ---------------------------------------------------------------------------

# @extend_schema(
#     summary="Admin List All Halls",
#     description="Admin view to inspect, filter, and review function halls across all owners.",
#     parameters=[
#         OpenApiParameter(name="status", type=OpenApiTypes.STR, description="Filter by HallStatus"),
#         OpenApiParameter(name="approval_status", type=OpenApiTypes.STR, description="Filter by HallApprovalStatus"),
#         OpenApiParameter(name="q", type=OpenApiTypes.STR, description="Search query for name, locality, city"),
#     ],
#     responses={200: HallListSerializer(many=True)}
# )
# class AdminHallListView(APIView):
#     permission_classes = [IsAuthenticated, IsAdminRole]
#     serializer_class = HallListSerializer

#     def get(self, request):
#         queryset = Hall.objects.select_related('owner', 'owner__owner_profile').prefetch_related('amenities', 'images').all()

#         status_param = request.query_params.get('status')
#         approval_param = request.query_params.get('approval_status')
#         q = request.query_params.get('q')

#         if status_param:
#             queryset = queryset.filter(status=status_param)
#         if approval_param:
#             queryset = queryset.filter(approval_status=approval_param)
#         if q:
#             queryset = queryset.filter(
#                 Q(name__icontains=q) |
#                 Q(locality__icontains=q) |
#                 Q(city__icontains=q) |
#                 Q(owner__email__icontains=q)
#             )

#         paginator = StandardPagination()
#         page = paginator.paginate_queryset(queryset, request)
#         serializer = self.serializer_class(page, many=True)
#         return paginator.get_paginated_response(serializer.data)


# @extend_schema(
#     summary="Admin Hall Approval Action",
#     description="Approve, Reject, or Suspend a function hall listing.",
#     request=AdminHallApprovalSerializer,
#     responses={200: HallDetailSerializer}
# )
# class AdminHallActionView(APIView):
#     permission_classes = [IsAuthenticated, IsAdminRole]
#     serializer_class = AdminHallApprovalSerializer

#     def post(self, request, hall_id):
#         hall = Hall.objects.filter(id=hall_id).first()
#         if not hall:
#             return api_response(message="Hall not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

#         serializer = self.serializer_class(data=request.data)
#         if serializer.is_valid():
#             action = serializer.validated_data['action']
#             reason = serializer.validated_data.get('reason', '')

#             if action == 'APPROVE':
#                 hall.approval_status = HallApprovalStatus.APPROVED
#                 hall.approved_by = request.user
#                 hall.approved_at = datetime.now(timezone.utc)
#                 hall.rejection_reason = ""
#             elif action == 'REJECT':
#                 hall.approval_status = HallApprovalStatus.REJECTED
#                 hall.rejection_reason = reason
#             elif action == 'SUSPEND':
#                 hall.approval_status = HallApprovalStatus.SUSPENDED
#                 hall.rejection_reason = reason

#             hall.save()
#             cache.delete("featured_halls_homepage")

#             AuditService.log_action(
#                 user=request.user,
#                 action=f"HALL_{action}",
#                 target_type="Hall",
#                 target_id=str(hall.id),
#                 details={"reason": reason}
#             )

#             detail_serializer = HallDetailSerializer(hall)
#             return api_response(data=detail_serializer.data, message=f"Hall status updated to {hall.approval_status}.")
#         return api_response(message="Validation error.", errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST, success=False)




import logging
import uuid
from datetime import datetime, timezone

from django.core.cache import cache
from django.db.models import Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import OwnerVerificationStatus
from apps.accounts.permissions import IsAdminRole, IsOwnerRole
from apps.core.pagination import StandardPagination
from apps.core.responses import api_response
from apps.core.services.audit import AuditService
from apps.halls.models import Amenity, Hall, HallApprovalStatus, HallImage, HallStatus
from apps.halls.serializers import (
    AdminHallApprovalSerializer,
    AmenitySerializer,
    HallCreateUpdateSerializer,
    HallDetailSerializer,
    HallImageSerializer,
    HallListSerializer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public Endpoints
# ---------------------------------------------------------------------------

@extend_schema(
    summary="Search & List Function Halls",
    description="Public search endpoint returning only APPROVED & ACTIVE function halls with filtering and sorting.",
    parameters=[
        OpenApiParameter(name="q", type=OpenApiTypes.STR, description="Search term for name, description, or locality"),
        OpenApiParameter(name="city", type=OpenApiTypes.STR, description="Filter by city name"),
        OpenApiParameter(name="locality", type=OpenApiTypes.STR, description="Filter by locality/area"),
        OpenApiParameter(name="hall_type", type=OpenApiTypes.STR, description="Filter by HallType enum"),
        OpenApiParameter(name="guests", type=OpenApiTypes.INT, description="Required guest count capacity"),
        OpenApiParameter(name="capacity_min", type=OpenApiTypes.INT, description="Minimum venue capacity"),
        OpenApiParameter(name="capacity_max", type=OpenApiTypes.INT, description="Maximum venue capacity"),
        OpenApiParameter(name="price_min", type=OpenApiTypes.FLOAT, description="Minimum morning slot base price"),
        OpenApiParameter(name="price_max", type=OpenApiTypes.FLOAT, description="Maximum morning slot base price"),
        OpenApiParameter(name="min_rating", type=OpenApiTypes.FLOAT, description="Minimum average rating"),
        OpenApiParameter(name="amenities", type=OpenApiTypes.STR, many=True, description="Filter by amenity slug(s)"),
        OpenApiParameter(name="sort", type=OpenApiTypes.STR, description="Sorting option: price_asc, price_desc, rating, capacity_asc, capacity_desc, recommended"),
    ],
    responses={200: HallListSerializer(many=True)},
)
class PublicHallListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = HallListSerializer

    def get(self, request):
        queryset = Hall.objects.filter(
            approval_status=HallApprovalStatus.APPROVED,
            status=HallStatus.ACTIVE
        ).select_related('owner', 'owner__owner_profile').prefetch_related('amenities', 'images')

        # Filters
        q = request.query_params.get('q')
        city = request.query_params.get('city')
        locality = request.query_params.get('locality')
        hall_type = request.query_params.get('hall_type')
        guests = request.query_params.get('guests')
        capacity_min = request.query_params.get('capacity_min')
        capacity_max = request.query_params.get('capacity_max')
        price_min = request.query_params.get('price_min')
        price_max = request.query_params.get('price_max')
        min_rating = request.query_params.get('min_rating')
        amenities = request.query_params.getlist('amenities')
        sort = request.query_params.get('sort', 'recommended')

        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) |
                Q(description__icontains=q) |
                Q(locality__icontains=q) |
                Q(address_line1__icontains=q)
            )

        if city:
            queryset = queryset.filter(city__iexact=city)
        if locality:
            queryset = queryset.filter(locality__iexact=locality)
        if hall_type:
            queryset = queryset.filter(hall_type=hall_type)
        if guests:
            try:
                g_val = int(guests)
                queryset = queryset.filter(min_capacity__lte=g_val, max_capacity__gte=g_val)
            except ValueError:
                pass
        if capacity_min:
            try:
                queryset = queryset.filter(max_capacity__gte=int(capacity_min))
            except ValueError:
                pass
        if capacity_max:
            try:
                queryset = queryset.filter(min_capacity__lte=int(capacity_max))
            except ValueError:
                pass
        if price_min:
            try:
                queryset = queryset.filter(base_price_morning__gte=float(price_min))
            except ValueError:
                pass
        if price_max:
            try:
                queryset = queryset.filter(base_price_morning__lte=float(price_max))
            except ValueError:
                pass
        if min_rating:
            try:
                queryset = queryset.filter(avg_rating__gte=float(min_rating))
            except ValueError:
                pass
        if amenities:
            for am in amenities:
                if am.strip():
                    queryset = queryset.filter(amenities__slug=am.strip())

        # Sorting
        if sort == 'price_asc':
            queryset = queryset.order_by('base_price_morning')
        elif sort == 'price_desc':
            queryset = queryset.order_by('-base_price_morning')
        elif sort in ['rating', 'rating_desc']:
            queryset = queryset.order_by('-avg_rating', '-review_count')
        elif sort == 'capacity_desc':
            queryset = queryset.order_by('-max_capacity')
        elif sort == 'capacity_asc':
            queryset = queryset.order_by('min_capacity')
        else:
            queryset = queryset.order_by('-avg_rating', '-review_count', '-created_at')

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = self.serializer_class(page, many=True)
        return paginator.get_paginated_response(serializer.data)


@extend_schema(
    summary="Get Featured Halls",
    description="Returns top-rated featured halls for the homepage display (Cached in Redis for 5 minutes).",
    responses={200: HallListSerializer(many=True)}
)
class PublicFeaturedHallsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = HallListSerializer

    def get(self, request):
        cache_key = "featured_halls_homepage"
        cached_data = cache.get(cache_key)
        if cached_data:
            return api_response(data=cached_data)

        halls = Hall.objects.filter(
            approval_status=HallApprovalStatus.APPROVED,
            status=HallStatus.ACTIVE
        ).select_related('owner', 'owner__owner_profile').prefetch_related('amenities', 'images').order_by('-avg_rating', '-created_at')[:6]

        serializer = self.serializer_class(halls, many=True)
        cache.set(cache_key, serializer.data, timeout=300)
        return api_response(data=serializer.data)


@extend_schema(
    summary="Get Amenities Catalog",
    description="Catalog of active venue amenities (Cached in Redis for 1 hour).",
    responses={200: AmenitySerializer(many=True)}
)
class PublicAmenityListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = AmenitySerializer

    def get(self, request):
        cache_key = "public_amenities_catalog"
        cached_data = cache.get(cache_key)
        if cached_data:
            return api_response(data=cached_data)

        amenities = Amenity.objects.filter(is_active=True).order_by('name')
        serializer = self.serializer_class(amenities, many=True)
        cache.set(cache_key, serializer.data, timeout=3600)
        return api_response(data=serializer.data)


@extend_schema(
    summary="Get Public Hall Details",
    description="Public detailed view of a single function hall by slug or UUID. Unapproved halls are restricted unless requested by owner or admin.",
    responses={
        200: HallDetailSerializer,
        404: OpenApiTypes.OBJECT
    }
)
class PublicHallDetailView(APIView):
    permission_classes = [AllowAny]
    serializer_class = HallDetailSerializer

    def get(self, request, id_or_slug):
        try:
            uuid.UUID(str(id_or_slug))
            is_uuid = True
        except (ValueError, TypeError, AttributeError):
            is_uuid = False

        if is_uuid:
            query = Q(id=id_or_slug) | Q(slug=id_or_slug)
        else:
            query = Q(slug=id_or_slug)

        hall = Hall.objects.filter(query).select_related('owner', 'owner__owner_profile').prefetch_related('amenities', 'images').first()
        if not hall:
            return api_response(
                message="Function hall not found.",
                status_code=status.HTTP_404_NOT_FOUND,
                success=False,
                code="NOT_FOUND"
            )

        if hall.approval_status != HallApprovalStatus.APPROVED:
            user = request.user
            if not user or not user.is_authenticated or (user != hall.owner and not getattr(user, 'is_admin', False)):
                return api_response(
                    message="This venue listing is currently under review or inactive.",
                    status_code=status.HTTP_404_NOT_FOUND,
                    success=False,
                    code="NOT_PUBLIC"
                )

        serializer = self.serializer_class(hall)
        return api_response(data=serializer.data)


# ---------------------------------------------------------------------------
# Hall Owner Endpoints
# ---------------------------------------------------------------------------

@extend_schema_view(
    get=extend_schema(
        summary="List Owner Halls",
        description="List all halls owned by the authenticated owner.",
        responses={200: HallListSerializer(many=True)}
    ),
    post=extend_schema(
        summary="Create Hall Listing",
        description="Creates a new function hall listing in DRAFT state.",
        request=HallCreateUpdateSerializer,
        responses={201: HallDetailSerializer}
    )
)
class OwnerHallListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOwnerRole]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return HallCreateUpdateSerializer
        return HallListSerializer

    def get(self, request):
        halls = Hall.objects.filter(owner=request.user).prefetch_related('amenities', 'images')
        serializer = HallListSerializer(halls, many=True)
        return api_response(data=serializer.data)

    def post(self, request):
        profile = getattr(request.user, 'owner_profile', None)
        if not profile or profile.verification_status != OwnerVerificationStatus.VERIFIED:
            return api_response(
                message="Your owner profile must be verified before creating a venue listing.",
                status_code=status.HTTP_403_FORBIDDEN,
                success=False,
                code="OWNER_NOT_VERIFIED",
            )

        serializer = HallCreateUpdateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            hall = serializer.save()
            cache.delete("featured_halls_homepage")
            
            AuditService.log_action(
                actor=request.user,
                action="HALL_CREATED",
                obj=hall,
                changes={"name": hall.name}
            )
            
            detail_serializer = HallDetailSerializer(hall)
            return api_response(
                data=detail_serializer.data,
                message="Hall created successfully in draft mode.",
                status_code=status.HTTP_201_CREATED
            )
        return api_response(
            message="Validation error.",
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST,
            success=False
        )


@extend_schema_view(
    get=extend_schema(
        summary="Get Owner Hall Detail",
        description="Retrieve details of a specific hall owned by the authenticated user.",
        responses={200: HallDetailSerializer}
    ),
    patch=extend_schema(
        summary="Update Owner Hall",
        description="Update details of a specific hall owned by the authenticated user.",
        request=HallCreateUpdateSerializer,
        responses={200: HallDetailSerializer}
    )
)
class OwnerHallDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOwnerRole]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return HallCreateUpdateSerializer
        return HallDetailSerializer

    def get_object(self, pk, user):
        return Hall.objects.filter(id=pk, owner=user).prefetch_related('amenities', 'images').first()

    def get(self, request, pk):
        hall = self.get_object(pk, request.user)
        if not hall:
            return api_response(message="Hall not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)
        serializer = HallDetailSerializer(hall)
        return api_response(data=serializer.data)

    def patch(self, request, pk):
        hall = self.get_object(pk, request.user)
        if not hall:
            return api_response(message="Hall not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

        serializer = HallCreateUpdateSerializer(hall, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            updated_hall = serializer.save()
            
            if updated_hall.approval_status == HallApprovalStatus.REJECTED:
                updated_hall.approval_status = HallApprovalStatus.UNDER_REVIEW
                updated_hall.save(update_fields=['approval_status'])

            cache.delete("featured_halls_homepage")

            AuditService.log_action(
                actor=request.user,
                action="HALL_UPDATED",
                obj=updated_hall
            )

            detail_serializer = HallDetailSerializer(updated_hall)
            return api_response(data=detail_serializer.data, message="Hall updated successfully.")
        return api_response(message="Validation error.", errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST, success=False)


@extend_schema(
    summary="Submit Hall for Approval",
    description="Moves hall listing from DRAFT to UNDER_REVIEW status for admin evaluation.",
    responses={200: HallDetailSerializer}
)
class OwnerHallSubmitView(APIView):
    permission_classes = [IsAuthenticated, IsOwnerRole]
    serializer_class = HallDetailSerializer

    def post(self, request, pk):
        profile = getattr(request.user, 'owner_profile', None)
        if not profile or profile.verification_status != OwnerVerificationStatus.VERIFIED:
            return api_response(
                message="Your owner profile must be verified before submitting a venue for review.",
                status_code=status.HTTP_403_FORBIDDEN,
                success=False,
                code="OWNER_NOT_VERIFIED",
            )

        hall = Hall.objects.filter(id=pk, owner=request.user).first()
        if not hall:
            return api_response(message="Hall not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

        if hall.approval_status not in [HallApprovalStatus.DRAFT, HallApprovalStatus.REJECTED]:
            return api_response(
                message=f"Cannot submit hall currently in '{hall.approval_status}' state.",
                status_code=status.HTTP_400_BAD_REQUEST,
                success=False
            )

        hall.approval_status = HallApprovalStatus.UNDER_REVIEW
        hall.save(update_fields=['approval_status'])

        AuditService.log_action(
            actor=request.user,
            action="HALL_SUBMITTED_FOR_REVIEW",
            obj=hall
        )

        serializer = self.serializer_class(hall)
        return api_response(data=serializer.data, message="Hall successfully submitted for admin approval.")


@extend_schema(
    summary="Toggle Hall Active Status",
    description="Toggle active operational status (ACTIVE <-> INACTIVE) for an approved venue listing.",
    responses={200: HallDetailSerializer}
)
class OwnerHallToggleStatusView(APIView):
    permission_classes = [IsAuthenticated, IsOwnerRole]
    serializer_class = HallDetailSerializer

    def post(self, request, pk):
        hall = Hall.objects.filter(id=pk, owner=request.user).first()
        if not hall:
            return api_response(message="Hall not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

        hall.status = HallStatus.INACTIVE if hall.status == HallStatus.ACTIVE else HallStatus.ACTIVE
        hall.save(update_fields=['status'])
        cache.delete("featured_halls_homepage")

        AuditService.log_action(
            actor=request.user,
            action=f"HALL_STATUS_{hall.status}",
            obj=hall
        )

        serializer = self.serializer_class(hall)
        return api_response(data=serializer.data, message=f"Hall status updated to {hall.status}.")


@extend_schema(
    summary="Upload Hall Image",
    description="Upload gallery images for a specific function hall listing.",
    request=HallImageSerializer,
    responses={201: HallImageSerializer}
)
class OwnerHallImageUploadView(APIView):
    permission_classes = [IsAuthenticated, IsOwnerRole]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = HallImageSerializer

    def post(self, request, pk):
        hall = Hall.objects.filter(id=pk, owner=request.user).first()
        if not hall:
            return api_response(message="Hall not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save(hall=hall)
            cache.delete("featured_halls_homepage")
            return api_response(data=serializer.data, message="Image uploaded successfully.", status_code=status.HTTP_201_CREATED)
        return api_response(message="Validation error.", errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST, success=False)


@extend_schema(
    summary="Delete Hall Image",
    description="Remove an image attachment from a hall gallery.",
    responses={200: OpenApiTypes.OBJECT}
)
class OwnerHallImageDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsOwnerRole]

    def delete(self, request, pk, img_id):
        image = HallImage.objects.filter(id=img_id, hall_id=pk, hall__owner=request.user).first()
        if not image:
            return api_response(message="Image not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

        image.delete()
        cache.delete("featured_halls_homepage")
        return api_response(message="Image deleted successfully.")


# ---------------------------------------------------------------------------
# Admin Endpoints
# ---------------------------------------------------------------------------

@extend_schema(
    summary="Admin List All Halls",
    description="Admin view to inspect, filter, and review function halls across all owners.",
    parameters=[
        OpenApiParameter(name="status", type=OpenApiTypes.STR, description="Filter by HallStatus"),
        OpenApiParameter(name="approval_status", type=OpenApiTypes.STR, description="Filter by HallApprovalStatus"),
        OpenApiParameter(name="q", type=OpenApiTypes.STR, description="Search query for name, locality, city"),
    ],
    responses={200: HallListSerializer(many=True)}
)
class AdminHallListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = HallListSerializer

    def get(self, request):
        queryset = Hall.objects.select_related('owner', 'owner__owner_profile').prefetch_related('amenities', 'images').all()

        status_param = request.query_params.get('status')
        approval_param = request.query_params.get('approval_status')
        q = request.query_params.get('q')

        if status_param:
            queryset = queryset.filter(status=status_param)
        if approval_param:
            queryset = queryset.filter(approval_status=approval_param)
        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) |
                Q(locality__icontains=q) |
                Q(city__icontains=q) |
                Q(owner__email__icontains=q)
            )

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = self.serializer_class(page, many=True)
        return paginator.get_paginated_response(serializer.data)


@extend_schema(
    summary="Admin Hall Approval Action",
    description="Approve, Reject, or Suspend a function hall listing.",
    request=AdminHallApprovalSerializer,
    responses={200: HallDetailSerializer}
)
class AdminHallActionView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = AdminHallApprovalSerializer

    def post(self, request, pk):
        hall = Hall.objects.filter(id=pk).first()
        if not hall:
            return api_response(message="Hall not found.", status_code=status.HTTP_404_NOT_FOUND, success=False)

        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            action = serializer.validated_data['action']
            reason = serializer.validated_data.get('reason', '')

            if action == 'APPROVE':
                hall.approval_status = HallApprovalStatus.APPROVED
                hall.approved_by = request.user
                hall.approved_at = datetime.now(timezone.utc)
                hall.rejection_reason = ""
            elif action == 'REJECT':
                hall.approval_status = HallApprovalStatus.REJECTED
                hall.rejection_reason = reason
            elif action == 'SUSPEND':
                hall.approval_status = HallApprovalStatus.SUSPENDED
                hall.rejection_reason = reason

            hall.save()
            cache.delete("featured_halls_homepage")

            AuditService.log_action(
                actor=request.user,
                action=f"HALL_{action}",
                obj=hall,
                changes={"reason": reason}
            )

            detail_serializer = HallDetailSerializer(hall)
            return api_response(data=detail_serializer.data, message=f"Hall status updated to {hall.approval_status}.")
        return api_response(message="Validation error.", errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST, success=False)