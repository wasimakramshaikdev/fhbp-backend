from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.core.cache import cache
from apps.core.models import PlatformSetting, AuditLog
from apps.core.services.audit import AuditService
from apps.accounts.models import User, UserRole, OwnerProfile, OwnerVerificationStatus
from apps.halls.models import Hall, HallImage, Amenity, HallApprovalStatus, HallStatus, HallType, CateringPolicy, CancellationPolicy
from apps.availability.models import HallSlotAvailability, TimeSlot, SlotStatus
from apps.availability.services.availability import AvailabilityService
from apps.bookings.models import Booking, BookingStatus, EventType
from apps.bookings.services.pricing import PricingService
from apps.payments.models import Payment, PaymentStatus, PaymentType, PaymentMethod
from apps.reviews.models import Review
from apps.favorites.models import Favorite
from apps.notifications.models import Notification, NotificationType
from apps.disputes.models import Dispute, DisputeStatus, DisputeResolutionType
from apps.payouts.models import Payout, PayoutStatus
from apps.payouts.services.payout import PayoutService

class Command(BaseCommand):
    help = "Seeds comprehensive, realistic Hyderabad Indian marketplace data for HallBook."

    def handle(self, *args, **options):
        self.stdout.write("Seeding HallBook marketplace data...")
        cache.clear()

        # 1. Platform Settings
        PlatformSetting.objects.update_or_create(
            key="PLATFORM_COMMISSION_PCT",
            defaults={"value": {"percentage": 10.0}, "description": "Default marketplace commission percentage"}
        )
        PlatformSetting.objects.update_or_create(
            key="DEFAULT_GST_TAX_RATE",
            defaults={"value": {"rate": 18.0}, "description": "Goods & Services Tax (GST) percentage"}
        )
        PlatformSetting.objects.update_or_create(
            key="DEFAULT_ADVANCE_PCT",
            defaults={"value": {"percentage": 20.0}, "description": "Checkout advance deposit percentage"}
        )
        PlatformSetting.objects.update_or_create(
            key="BOOKING_HOLD_TTL_MINUTES",
            defaults={"value": {"minutes": 15}, "description": "Checkout temporary slot hold timeout"}
        )

        # 2. Super Admin User
        admin_user, _ = User.objects.update_or_create(
            email="admin@hallbook.in",
            defaults={
                "full_name": "Platform Super Admin",
                "role": UserRole.ADMIN,
                "is_staff": True,
                "is_superuser": True,
                "is_verified": True,
                "is_active": True,
            }
        )
        admin_user.set_password("Admin@12345")
        admin_user.save()

        # 3. Amenities Catalog
        amenity_defs = [
            ("Centralized AC", "ac", "Wind"),
            ("Valet & Guest Parking", "valet-parking", "Car"),
            ("100% Generator Backup", "generator-backup", "Zap"),
            ("Bridal Dressing Suite", "bridal-room", "Sparkles"),
            ("Stage & Acoustic Lighting", "stage-lighting", "Sun"),
            ("In-house Catering Setup", "catering-kitchen", "UtensilsCrossed"),
            ("DJ & Audio System", "dj-sound", "Music"),
            ("Lawn & Open Garden", "lawn-garden", "Trees"),
            ("CCTV & Security", "cctv-security", "ShieldCheck"),
            ("Rooms for Guests", "guest-rooms", "BedDouble"),
        ]

        amenity_objs = {}
        for name, slug, icon in amenity_defs:
            am, _ = Amenity.objects.update_or_create(name=name, defaults={"slug": slug, "icon_name": icon, "is_active": True})
            amenity_objs[slug] = am

        # 4. Venue Owners & Profiles
        owners_data = [
            {
                "email": "k.naidu@grandorchid.com",
                "full_name": "K. Venkatesh Naidu",
                "phone": "+919876501001",
                "business_name": "Grand Orchid Conventions Pvt Ltd",
                "reg": "REG-HYD-2024-0812",
                "pan": "36AABCG1234F1Z5",
                "locality": "Madhapur",
                "bank_holder": "Grand Orchid Conventions Pvt Ltd",
                "bank_acc": "98765432109876",
                "ifsc": "HDFC0001234",
            },
            {
                "email": "s.rao@royalpalms.in",
                "full_name": "Srinivas Rao",
                "phone": "+919876501002",
                "business_name": "Royal Palms Hospitality LLP",
                "reg": "REG-HYD-2023-4521",
                "pan": "36AABCR5678F1Z2",
                "locality": "Gachibowli",
                "bank_holder": "Royal Palms Hospitality LLP",
                "bank_acc": "12345678901234",
                "ifsc": "ICIC0000456",
            },
            {
                "email": "m.reddy@sapphiregardens.in",
                "full_name": "M. Madhusudhan Reddy",
                "phone": "+919876501003",
                "business_name": "Sapphire Gardens & Banquets",
                "reg": "REG-HYD-2025-9981",
                "pan": "36AABCS9012F1Z9",
                "locality": "Kondapur",
                "bank_holder": "Sapphire Gardens & Banquets",
                "bank_acc": "5555666677778888",
                "ifsc": "SBIN0004321",
            },
        ]

        owner_instances = []
        for od in owners_data:
            u, _ = User.objects.update_or_create(
                email=od["email"],
                defaults={
                    "full_name": od["full_name"],
                    "phone": od["phone"],
                    "role": UserRole.OWNER,
                    "is_verified": True,
                    "is_active": True,
                }
            )
            u.set_password("Owner@12345")
            u.save()

            OwnerProfile.objects.update_or_create(
                user=u,
                defaults={
                    "business_name": od["business_name"],
                    "registration_number": od["reg"],
                    "pan_gst_number": od["pan"],
                    "locality": od["locality"],
                    "city": "Hyderabad",
                    "bank_account_holder": od["bank_holder"],
                    "bank_account_number": od["bank_acc"],
                    "bank_ifsc_code": od["ifsc"],
                    "verification_status": OwnerVerificationStatus.VERIFIED,
                    "payout_enabled": True,
                }
            )
            owner_instances.append(u)

        # 5. Function Halls
        halls_data = [
            {
                "owner": owner_instances[0],
                "name": "Grand Orchid Banquets & Convention",
                "slug": "grand-orchid-banquets-madhapur",
                "desc": "Premier luxury air-conditioned banquet hall in Madhapur with crystal chandeliers, acoustic stage, separate veg/non-veg dining areas, and expansive parking.",
                "locality": "Madhapur",
                "address": "Plot 42, Road No 36, Madhapur",
                "min_cap": 150,
                "max_cap": 600,
                "type": HallType.AC,
                "morn_price": Decimal("35000.00"),
                "eve_price": Decimal("50000.00"),
                "full_price": Decimal("80000.00"),
                "veg_price": Decimal("550.00"),
                "non_veg": Decimal("800.00"),
                "decor": Decimal("18000.00"),
                "dj": Decimal("12000.00"),
                "rating": Decimal("4.80"),
                "reviews": 142,
                "images": [
                    "https://images.unsplash.com/photo-1519167758481-83f550bb49b3?auto=format&fit=crop&w=1200&q=80",
                    "https://images.unsplash.com/photo-1545232979-8bf68ee9b1af?auto=format&fit=crop&w=1200&q=80",
                    "https://images.unsplash.com/photo-1464366400600-7168b8af9bc3?auto=format&fit=crop&w=1200&q=80"
                ],
                "amenities": ["ac", "valet-parking", "generator-backup", "bridal-room", "stage-lighting", "catering-kitchen", "cctv-security"]
            },
            {
                "owner": owner_instances[1],
                "name": "Royal Palms Convention Center",
                "slug": "royal-palms-convention-gachibowli",
                "desc": "Magnificent convention center in Gachibowli with 35-ft ceiling height, automated stage rigging, pre-function lobby, and 300+ car parking facility.",
                "locality": "Gachibowli",
                "address": "Financial District Rd, Gachibowli",
                "min_cap": 300,
                "max_cap": 1200,
                "type": HallType.CONVENTION,
                "morn_price": Decimal("55000.00"),
                "eve_price": Decimal("85000.00"),
                "full_price": Decimal("130000.00"),
                "veg_price": Decimal("650.00"),
                "non_veg": Decimal("950.00"),
                "decor": Decimal("25000.00"),
                "dj": Decimal("15000.00"),
                "rating": Decimal("4.70"),
                "reviews": 98,
                "images": [
                    "https://images.unsplash.com/photo-1545232979-8bf68ee9b1af?auto=format&fit=crop&w=1200&q=80",
                    "https://images.unsplash.com/photo-1519167758481-83f550bb49b3?auto=format&fit=crop&w=1200&q=80"
                ],
                "amenities": ["ac", "valet-parking", "generator-backup", "bridal-room", "guest-rooms", "cctv-security"]
            },
            {
                "owner": owner_instances[2],
                "name": "Sapphire Open Gardens & Lawn",
                "slug": "sapphire-gardens-lawn-kondapur",
                "desc": "Serene open lawn venue in Kondapur with lush landscaping, illuminated water fountains, covered dining pavilion, and romantic wedding stage.",
                "locality": "Kondapur",
                "address": "Botanical Garden Rd, Kondapur",
                "min_cap": 150,
                "max_cap": 500,
                "type": HallType.OPEN_LAWN,
                "morn_price": Decimal("28000.00"),
                "eve_price": Decimal("42000.00"),
                "full_price": Decimal("65000.00"),
                "veg_price": Decimal("500.00"),
                "non_veg": Decimal("750.00"),
                "decor": Decimal("15000.00"),
                "dj": Decimal("10000.00"),
                "rating": Decimal("4.60"),
                "reviews": 115,
                "images": [
                    "https://images.unsplash.com/photo-1464366400600-7168b8af9bc3?auto=format&fit=crop&w=1200&q=80",
                    "https://images.unsplash.com/photo-1519167758481-83f550bb49b3?auto=format&fit=crop&w=1200&q=80"
                ],
                "amenities": ["lawn-garden", "valet-parking", "generator-backup", "stage-lighting", "dj-sound"]
            },
        ]

        hall_instances = []
        for hd in halls_data:
            hall, _ = Hall.objects.update_or_create(
                slug=hd["slug"],
                defaults={
                    "owner": hd["owner"],
                    "name": hd["name"],
                    "description": hd["desc"],
                    "address_line1": hd["address"],
                    "city": "Hyderabad",
                    "locality": hd["locality"],
                    "postal_code": "500081",
                    "min_capacity": hd["min_cap"],
                    "max_capacity": hd["max_cap"],
                    "hall_type": hd["type"],
                    "base_price_morning": hd["morn_price"],
                    "base_price_evening": hd["eve_price"],
                    "base_price_full_day": hd["full_price"],
                    "advance_percentage": Decimal("20.00"),
                    "catering_policy": CateringPolicy.BOTH,
                    "veg_plate_price": hd["veg_price"],
                    "non_veg_plate_price": hd["non_veg"],
                    "decor_price": hd["decor"],
                    "dj_price": hd["dj"],
                    "cancellation_policy": CancellationPolicy.MODERATE,
                    "status": HallStatus.ACTIVE,
                    "approval_status": HallApprovalStatus.APPROVED,
                    "avg_rating": hd["rating"],
                    "review_count": hd["reviews"],
                }
            )

            # Images
            for idx, img_url in enumerate(hd["images"]):
                HallImage.objects.update_or_create(
                    hall=hall,
                    sort_order=idx,
                    defaults={"image_url": img_url, "is_primary": (idx == 0)}
                )

            # Amenities
            amenity_links = [amenity_objs[s] for s in hd["amenities"] if s in amenity_objs]
            hall.amenities.set(amenity_links)
            hall_instances.append(hall)

        # 6. Customers
        customers_data = [
            ("rahul.sharma@example.com", "Rahul Sharma", "+919876540010"),
            ("ananya.reddy@example.com", "Ananya Reddy", "+919876540020"),
            ("amit.patel@example.com", "Amit Patel", "+919876540030"),
        ]

        customer_instances = []
        for em, name, phone in customers_data:
            c, _ = User.objects.update_or_create(
                email=em,
                defaults={
                    "full_name": name,
                    "phone": phone,
                    "role": UserRole.CUSTOMER,
                    "is_verified": True,
                    "is_active": True,
                }
            )
            c.set_password("Customer@12345")
            c.save()
            customer_instances.append(c)

        # 7. Customer Favorites
        Favorite.objects.get_or_create(customer=customer_instances[0], hall=hall_instances[0])
        Favorite.objects.get_or_create(customer=customer_instances[0], hall=hall_instances[1])

        # 8. Bookings across realistic dates
        # Booking 1: Confirmed Wedding
        b1, _ = Booking.objects.update_or_create(
            booking_number="BK-2026-1042",
            defaults={
                "customer": customer_instances[0],
                "hall": hall_instances[0],
                "event_type": EventType.WEDDING,
                "event_date": date(2026, 8, 12),
                "time_slot": TimeSlot.EVENING,
                "guest_count": 350,
                "contact_name": "Rahul Sharma",
                "contact_phone": "+919876540010",
                "has_catering": True,
                "catering_plate_type": "VEG",
                "catering_plate_price": Decimal("550.00"),
                "has_decor": True,
                "has_dj": True,
                "hall_rent": Decimal("50000.00"),
                "catering_amount": Decimal("192500.00"),
                "decor_amount": Decimal("18000.00"),
                "dj_amount": Decimal("12000.00"),
                "subtotal": Decimal("272500.00"),
                "tax_rate": Decimal("18.00"),
                "tax_amount": Decimal("49050.00"),
                "total_amount": Decimal("321550.00"),
                "advance_percentage": Decimal("20.00"),
                "advance_amount": Decimal("64310.00"),
                "balance_amount": Decimal("257240.00"),
                "amount_paid": Decimal("64310.00"),
                "status": BookingStatus.CONFIRMED,
                "owner_response_notes": "Delighted to host your wedding reception!",
            }
        )
        AvailabilityService.confirm_slot_booked(hall_instances[0], date(2026, 8, 12), TimeSlot.EVENING, b1.id)
        Payment.objects.get_or_create(
            booking=b1,
            idempotency_key="pay_seed_1042",
            defaults={
                "payment_reference": "PAY-2026-1042",
                "amount": Decimal("64310.00"),
                "currency": "INR",
                "payment_type": PaymentType.ADVANCE,
                "payment_method": PaymentMethod.UPI,
                "status": PaymentStatus.SUCCESS,
                "gateway": "SIMULATED",
                "gateway_order_id": "order_seed_1042",
                "gateway_payment_id": "pay_seed_1042",
                "paid_at": datetime.now(timezone.utc),
            }
        )

        # Booking 2: Completed Past Booking with 5★ Review
        b2, _ = Booking.objects.update_or_create(
            booking_number="BK-2026-0810",
            defaults={
                "customer": customer_instances[1],
                "hall": hall_instances[0],
                "event_type": EventType.RECEPTION,
                "event_date": date(2026, 7, 15),
                "time_slot": TimeSlot.EVENING,
                "guest_count": 400,
                "contact_name": "Ananya Reddy",
                "contact_phone": "+919876540020",
                "hall_rent": Decimal("50000.00"),
                "subtotal": Decimal("50000.00"),
                "tax_amount": Decimal("9000.00"),
                "total_amount": Decimal("59000.00"),
                "advance_amount": Decimal("11800.00"),
                "balance_amount": Decimal("47200.00"),
                "amount_paid": Decimal("59000.00"),
                "status": BookingStatus.COMPLETED,
            }
        )
        Review.objects.update_or_create(
            booking=b2,
            defaults={
                "customer": customer_instances[1],
                "hall": hall_instances[0],
                "rating": 5,
                "comment": "Exceptional venue! The stage lighting and centralized AC kept 400 guests comfortable throughout the summer evening. Highly recommended!",
                "owner_response": "Thank you Ananya! It was our privilege to host your family celebration.",
                "owner_responded_at": datetime.now(timezone.utc),
                "is_published": True,
            }
        )

        # Booking 3: Disputed Booking (Wireframe Screen 7)
        b3, _ = Booking.objects.update_or_create(
            booking_number="BK-2026-1039",
            defaults={
                "customer": customer_instances[2],
                "hall": hall_instances[1],
                "event_type": EventType.ENGAGEMENT,
                "event_date": date(2026, 8, 2),
                "time_slot": TimeSlot.EVENING,
                "guest_count": 250,
                "contact_name": "Amit Patel",
                "contact_phone": "+919876540030",
                "hall_rent": Decimal("85000.00"),
                "subtotal": Decimal("85000.00"),
                "tax_amount": Decimal("15300.00"),
                "total_amount": Decimal("100300.00"),
                "advance_amount": Decimal("20060.00"),
                "balance_amount": Decimal("80240.00"),
                "amount_paid": Decimal("20060.00"),
                "status": BookingStatus.DISPUTED,
            }
        )
        Dispute.objects.update_or_create(
            booking=b3,
            defaults={
                "opened_by": customer_instances[2],
                "reason": "Hall denied entry on event date",
                "description": "Customer claims hall denied entry on scheduled date. Owner claims guest count exceeded agreed capacity.",
                "evidence_urls": ["https://images.unsplash.com/photo-1519167758481-83f550bb49b3"],
                "status": DisputeStatus.OPEN,
            }
        )

        # 9. Payouts for Owner
        p1 = PayoutService.schedule_payout_for_booking(b1)
        p1.status = PayoutStatus.PAID
        p1.save()

        p2 = PayoutService.schedule_payout_for_booking(b2)
        p2.status = PayoutStatus.PAID
        p2.save()

        # Audit logs
        AuditService.log_action(actor=admin_user, action="PLATFORM_DATA_SEEDED", obj=admin_user)

        self.stdout.write(self.style.SUCCESS("Successfully seeded HallBook marketplace with Super Admin, Owners, Venues, Customers, Bookings, Reviews, Payments, and Disputes!"))
