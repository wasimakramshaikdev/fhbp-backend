from django.test import TestCase
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User, UserRole, OwnerProfile
from apps.accounts.authentication import JWTTokenService
from apps.halls.models import Hall, HallApprovalStatus, HallStatus
from apps.favorites.models import Favorite

class FavoriteDomainTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        self.owner = User.objects.create_user(
            email="owner_fav@example.com",
            password="Password123!",
            full_name="Owner Fav",
            role=UserRole.OWNER
        )
        self.customer = User.objects.create_user(
            email="cust_fav@example.com",
            password="Password123!",
            full_name="Fav User",
            role=UserRole.CUSTOMER
        )
        self.customer_token = JWTTokenService.generate_tokens_for_user(self.customer)['access_token']

        self.hall = Hall.objects.create(
            owner=self.owner,
            name="Orchid Garden Palace",
            address_line1="Kondapur",
            city="Hyderabad",
            locality="Kondapur",
            approval_status=HallApprovalStatus.APPROVED,
            status=HallStatus.ACTIVE
        )

    def test_toggle_favorite_add_and_remove(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.customer_token}")

        # 1. Add to favorites
        res_add = self.client.post(f'/api/v1/favorites/{self.hall.id}/toggle/')
        self.assertEqual(res_add.status_code, status.HTTP_200_OK)
        self.assertTrue(res_add.data['data']['is_favorited'])
        self.assertTrue(Favorite.objects.filter(customer=self.customer, hall=self.hall).exists())

        # 2. List favorites
        res_list = self.client.get('/api/v1/favorites/')
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_list.data['data']), 1)

        # 3. Remove from favorites (toggle again)
        res_remove = self.client.post(f'/api/v1/favorites/{self.hall.id}/toggle/')
        self.assertEqual(res_remove.status_code, status.HTTP_200_OK)
        self.assertFalse(res_remove.data['data']['is_favorited'])
        self.assertFalse(Favorite.objects.filter(customer=self.customer, hall=self.hall).exists())
