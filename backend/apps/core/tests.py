from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from apps.core.models import PlatformSetting, AuditLog
from apps.core.services.audit import AuditService
from apps.accounts.models import User, UserRole

class HealthCheckTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_liveness_health_check_returns_200(self):
        response = self.client.get('/api/v1/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['status'], 'UP')
        self.assertEqual(response.data['data']['service'], 'hallbook-api')

    def test_readiness_health_check_returns_200_when_db_and_redis_healthy(self):
        response = self.client.get('/api/v1/ready/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['status'], 'READY')
        self.assertEqual(response.data['data']['dependencies']['database']['status'], 'HEALTHY')
        self.assertEqual(response.data['data']['dependencies']['redis']['status'], 'HEALTHY')


class AuditLogServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="admin@hallbook.in",
            password="SecurePassword123!",
            full_name="Platform Admin",
            role=UserRole.ADMIN
        )

    def test_audit_service_logs_actions_correctly(self):
        setting = PlatformSetting.objects.create(
            key="PLATFORM_COMMISSION_PCT",
            value={"percentage": 10.0},
            description="Default platform commission percentage"
        )

        log = AuditService.log_action(
            actor=self.user,
            action="UPDATE_PLATFORM_COMMISSION",
            obj=setting,
            ip_address="127.0.0.1",
            changes={"old": 10.0, "new": 12.5}
        )

        self.assertIsNotNone(log)
        self.assertEqual(log.actor, self.user)
        self.assertEqual(log.action, "UPDATE_PLATFORM_COMMISSION")
        self.assertEqual(log.object_type, "PlatformSetting")
        self.assertEqual(log.object_id, str(setting.id))
        self.assertEqual(log.changes["new"], 12.5)

    def test_pagination_max_page_size_clamping(self):
        """Requesting page_size=5000 is clamped to max_page_size=100."""
        from apps.core.pagination import StandardPagination
        from rest_framework.test import APIRequestFactory
        factory = APIRequestFactory()
        request = factory.get('/api/v1/halls/?page_size=5000')
        paginator = StandardPagination()
        clamped_size = paginator.get_page_size(request)
        self.assertEqual(clamped_size, 100)
