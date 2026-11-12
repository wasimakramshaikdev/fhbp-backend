from django.test import TestCase
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User, UserRole, OwnerProfile, OwnerVerificationStatus
from apps.accounts.authentication import JWTTokenService
from apps.halls.models import Hall, HallImage, Amenity, HallApprovalStatus, HallStatus, HallType

class HallDomainTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Admin user
        self.admin_user = User.objects.create_superuser(
            email="admin@hallbook.in",
            password="AdminPassword123!",
            full_name="Platform Super Admin"
        )
        self.admin_token = JWTTokenService.generate_tokens_for_user(self.admin_user)['access_token']

        # Owner A
        self.owner_a = User.objects.create_user(
            email="owner_a@example.com",
            password="OwnerPassword123!",
            full_name="Ramesh Reddy",
            role=UserRole.OWNER
        )
        OwnerProfile.objects.create(user=self.owner_a, business_name="Orchid Banquets LLC", city="Hyderabad")
        self.owner_a_token = JWTTokenService.generate_tokens_for_user(self.owner_a)['access_token']

        # Owner B
        self.owner_b = User.objects.create_user(
            email="owner_b@example.com",
            password="OwnerPassword123!",
            full_name="Suresh Kumar",
            role=UserRole.OWNER
        )
        OwnerProfile.objects.create(user=self.owner_b, business_name="Palms Convention LLC", city="Hyderabad")
        self.owner_b_token = JWTTokenService.generate_tokens_for_user(self.owner_b)['access_token']

        # Customer
        self.customer = User.objects.create_user(
            email="customer@example.com",
            password="CustomerPassword123!",
            full_name="Pooja Verma",
            role=UserRole.CUSTOMER
        )
        self.customer_token = JWTTokenService.generate_tokens_for_user(self.customer)['access_token']

        # Amenities
        self.amenity_ac = Amenity.objects.create(name="Centralized AC", slug="ac")
        self.amenity_parking = Amenity.objects.create(name="Valet Parking", slug="valet-parking")

    def test_owner_create_draft_hall_success(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_a_token}")
        payload = {
            "name": "Grand Orchid Banquets",
            "description": "Luxurious air-conditioned banquet hall in Madhapur.",
            "address_line1": "Road No 36, Jubilee Hills / Madhapur",
            "city": "Hyderabad",
            "locality": "Madhapur",
            "postal_code": "500081",
            "min_capacity": 150,
            "max_capacity": 600,
            "hall_type": "AC",
            "base_price_morning": "35000.00",
            "base_price_evening": "50000.00",
            "base_price_full_day": "75000.00",
            "advance_percentage": "20.00",
            "catering_policy": "BOTH",
            "veg_plate_price": "600.00",
            "non_veg_plate_price": "850.00",
            "decor_price": "20000.00",
            "dj_price": "12000.00",
            "amenity_ids": [str(self.amenity_ac.id), str(self.amenity_parking.id)],
            "initial_images": [
                "https://images.unsplash.com/photo-1519167758481-83f550bb49b3",
                "https://images.unsplash.com/photo-1545232979-8bf68ee9b1af"
            ]
        }
        res = self.client.post('/api/v1/owner/listings/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['success'])
        self.assertEqual(res.data['data']['approval_status'], "DRAFT")
        self.assertEqual(len(res.data['data']['images']), 2)
        self.assertEqual(len(res.data['data']['amenities']), 2)

    def test_unverified_owner_cannot_create_or_submit_hall(self):
        profile = self.owner_a.owner_profile
        profile.verification_status = OwnerVerificationStatus.PENDING
        profile.save(update_fields=['verification_status'])

        payload = {
            "name": "Pending KYC Hall",
            "description": "Should not be allowed before verification.",
            "address_line1": "Road 24",
            "city": "Hyderabad",
            "locality": "Madhapur",
            "min_capacity": 100,
            "max_capacity": 300,
            "hall_type": "AC",
            "base_price_morning": "25000.00",
            "base_price_evening": "40000.00",
            "base_price_full_day": "60000.00",
            "advance_percentage": "20.00",
            "catering_policy": "BOTH",
            "veg_plate_price": "500.00",
            "non_veg_plate_price": "700.00",
            "decor_price": "12000.00",
            "dj_price": "8000.00",
            "amenity_ids": [],
            "initial_images": ["https://example.com/1.jpg"]
        }

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_a_token}")
        create_res = self.client.post('/api/v1/owner/listings/', payload, format='json')
        self.assertEqual(create_res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('verification', create_res.data['message'].lower())

        hall = Hall.objects.create(
            owner=self.owner_a,
            name="Attempted Submission Hall",
            address_line1="Road 25",
            city="Hyderabad",
            locality="Madhapur",
            approval_status=HallApprovalStatus.DRAFT,
            status=HallStatus.ACTIVE,
        )

        submit_res = self.client.post(f'/api/v1/owner/listings/{hall.id}/submit/')
        self.assertEqual(submit_res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('verification', submit_res.data['message'].lower())

    def test_unapproved_hall_not_visible_publicly(self):
        # Create draft hall for Owner A
        hall = Hall.objects.create(
            owner=self.owner_a,
            name="Secret Hidden Hall",
            address_line1="Hidden Street",
            city="Hyderabad",
            locality="Kondapur",
            approval_status=HallApprovalStatus.DRAFT,
            status=HallStatus.ACTIVE
        )

        # Public list should NOT include draft hall
        pub_list_res = self.client.get('/api/v1/halls/')
        self.assertEqual(pub_list_res.status_code, status.HTTP_200_OK)
        hall_names = [h['name'] for h in pub_list_res.data['data']]
        self.assertNotIn("Secret Hidden Hall", hall_names)

        # Public detail should return 404
        pub_detail_res = self.client.get(f'/api/v1/halls/{hall.slug}/')
        self.assertEqual(pub_detail_res.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_submit_and_admin_approval_lifecycle(self):
        # 1. Owner creates draft
        hall = Hall.objects.create(
            owner=self.owner_a,
            name="Pearl Convention Hall",
            address_line1="HITEC City Main Rd",
            city="Hyderabad",
            locality="Madhapur",
            min_capacity=200,
            max_capacity=800,
            approval_status=HallApprovalStatus.DRAFT
        )

        # 2. Owner submits for review
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_a_token}")
        submit_res = self.client.post(f'/api/v1/owner/listings/{hall.id}/submit/')
        self.assertEqual(submit_res.status_code, status.HTTP_200_OK)
        hall.refresh_from_db()
        self.assertEqual(hall.approval_status, HallApprovalStatus.UNDER_REVIEW)

        # 3. Super Admin approves
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        approve_res = self.client.post(f'/api/v1/admin/halls/{hall.id}/action/', {
            "action": "APPROVE"
        }, format='json')
        self.assertEqual(approve_res.status_code, status.HTTP_200_OK)
        hall.refresh_from_db()
        self.assertEqual(hall.approval_status, HallApprovalStatus.APPROVED)
        self.assertEqual(hall.status, HallStatus.ACTIVE)
        self.assertEqual(hall.approved_by, self.admin_user)

        # 4. Now publicly visible!
        self.client.credentials() # anonymous
        pub_res = self.client.get(f'/api/v1/halls/{hall.slug}/')
        self.assertEqual(pub_res.status_code, status.HTTP_200_OK)
        self.assertEqual(pub_res.data['data']['name'], "Pearl Convention Hall")

    def test_admin_rejection_requires_reason(self):
        hall = Hall.objects.create(
            owner=self.owner_a,
            name="Incomplete Hall",
            address_line1="Test",
            city="Hyderabad",
            locality="Gachibowli",
            approval_status=HallApprovalStatus.UNDER_REVIEW
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        
        # Reject without reason fails
        res_fail = self.client.post(f'/api/v1/admin/halls/{hall.id}/action/', {
            "action": "REJECT"
        }, format='json')
        self.assertEqual(res_fail.status_code, status.HTTP_400_BAD_REQUEST)

        # Reject with reason succeeds
        res_ok = self.client.post(f'/api/v1/admin/halls/{hall.id}/action/', {
            "action": "REJECT",
            "reason": "Clear photos and fire safety license are missing."
        }, format='json')
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)
        hall.refresh_from_db()
        self.assertEqual(hall.approval_status, HallApprovalStatus.REJECTED)
        self.assertEqual(hall.rejection_reason, "Clear photos and fire safety license are missing.")

    def test_idor_owner_cannot_modify_other_owner_hall(self):
        hall_a = Hall.objects.create(
            owner=self.owner_a,
            name="Owner A Venue",
            address_line1="Road 1",
            city="Hyderabad",
            locality="Madhapur"
        )

        # Owner B tries to patch Owner A's venue
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_b_token}")
        patch_res = self.client.patch(f'/api/v1/owner/listings/{hall_a.id}/', {
            "name": "Hacked Name"
        }, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_403_FORBIDDEN)
        hall_a.refresh_from_db()
        self.assertEqual(hall_a.name, "Owner A Venue")

    def test_non_admin_cannot_approve_halls(self):
        hall = Hall.objects.create(
            owner=self.owner_a,
            name="Self Approval Attempt",
            address_line1="Road 2",
            city="Hyderabad",
            locality="Madhapur",
            approval_status=HallApprovalStatus.UNDER_REVIEW
        )

        # Owner attempts to approve
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_a_token}")
        res = self.client.post(f'/api/v1/admin/halls/{hall.id}/action/', {"action": "APPROVE"}, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_search_filtering_by_locality_and_capacity(self):
        # Create approved halls in different localities
        h1 = Hall.objects.create(
            owner=self.owner_a,
            name="Madhapur Grand Banquet",
            address_line1="Road 36",
            city="Hyderabad",
            locality="Madhapur",
            min_capacity=100,
            max_capacity=500,
            base_price_morning=30000,
            approval_status=HallApprovalStatus.APPROVED,
            status=HallStatus.ACTIVE
        )
        h2 = Hall.objects.create(
            owner=self.owner_a,
            name="Gachibowli Royal Palace",
            address_line1="ORR Junction",
            city="Hyderabad",
            locality="Gachibowli",
            min_capacity=300,
            max_capacity=1000,
            base_price_morning=60000,
            approval_status=HallApprovalStatus.APPROVED,
            status=HallStatus.ACTIVE
        )

        # 1. Filter by locality Madhapur
        res_madhapur = self.client.get('/api/v1/halls/?locality=Madhapur')
        self.assertEqual(res_madhapur.status_code, status.HTTP_200_OK)
        names = [h['name'] for h in res_madhapur.data['data']]
        self.assertIn("Madhapur Grand Banquet", names)
        self.assertNotIn("Gachibowli Royal Palace", names)

        # 2. Filter by guest count (800 guests)
        res_guests = self.client.get('/api/v1/halls/?guests=800')
        names_guests = [h['name'] for h in res_guests.data['data']]
        self.assertIn("Gachibowli Royal Palace", names_guests)
        self.assertNotIn("Madhapur Grand Banquet", names_guests)

        # 3. Sorting by price asc
        res_sort = self.client.get('/api/v1/halls/?sort=price_asc')
        self.assertEqual(res_sort.status_code, status.HTTP_200_OK)
        prices = [float(h['base_price_morning']) for h in res_sort.data['data']]
        self.assertEqual(prices, sorted(prices))
