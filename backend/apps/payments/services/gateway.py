import hmac
import hashlib
import uuid
import secrets
import logging
from decimal import Decimal
from abc import ABC, abstractmethod
from django.conf import settings

logger = logging.getLogger(__name__)

class PaymentGatewayError(Exception):
    pass

class PaymentGatewayConfigurationError(PaymentGatewayError):
    pass

class PaymentGatewayAdapter(ABC):
    @abstractmethod
    def create_order(self, amount: Decimal, currency: str, receipt: str, notes: dict = None) -> dict:
        """Create a transaction order with the payment provider."""
        pass

    @abstractmethod
    def verify_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        """Verify HMAC signature returned by provider upon checkout."""
        pass

    @abstractmethod
    def verify_webhook_signature(self, raw_body: bytes, signature: str, order_id: str = None, payment_id: str = None) -> bool:
        """Verify webhook signature from gateway callback."""
        pass

    @abstractmethod
    def process_refund(self, payment_id: str, amount: Decimal, reason: str) -> dict:
        """Trigger refund API call with payment provider."""
        pass


class RazorpayGatewayAdapter(PaymentGatewayAdapter):
    def __init__(self, key_id=None, key_secret=None, webhook_secret=None):
        self.key_id = key_id or getattr(settings, 'RAZORPAY_KEY_ID', '')
        self.key_secret = key_secret or getattr(settings, 'RAZORPAY_KEY_SECRET', '')
        self.webhook_secret = webhook_secret or getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', '') or self.key_secret

    @property
    def is_configured(self) -> bool:
        return bool(self.key_id and self.key_secret)

    def _get_client(self):
        if not self.is_configured:
            raise PaymentGatewayConfigurationError("Razorpay payment configuration is not available.")
        import razorpay
        return razorpay.Client(auth=(self.key_id, self.key_secret))

    def create_order(self, amount: Decimal, currency: str, receipt: str, notes: dict = None) -> dict:
        if not self.is_configured:
            raise PaymentGatewayConfigurationError("Razorpay payment configuration is not available.")

        # Convert amount to paise (1 INR = 100 paise)
        amount_in_subunits = int((Decimal(str(amount)) * Decimal('100')).quantize(Decimal('1')))

        try:
            client = self._get_client()
            order_payload = {
                'amount': amount_in_subunits,
                'currency': currency or 'INR',
                'receipt': receipt,
                'notes': notes or {},
                'payment_capture': 1,
            }
            resp = client.order.create(data=order_payload)
            return {
                "gateway_order_id": resp.get("id"),
                "amount": float(amount),
                "amount_subunits": amount_in_subunits,
                "currency": currency or 'INR',
                "key_id": self.key_id,
                "receipt": receipt,
                "raw_response": resp,
            }
        except PaymentGatewayConfigurationError:
            raise
        except Exception as exc:
            logger.error(f"[RAZORPAY] Order creation failed: {exc}", exc_info=True)
            raise PaymentGatewayError(f"Razorpay order creation failed: {str(exc)}")

    def verify_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        if not self.is_configured:
            raise PaymentGatewayConfigurationError("Razorpay payment configuration is not available.")

        if not order_id or not payment_id or not signature:
            return False

        try:
            client = self._get_client()
            client.utility.verify_payment_signature({
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature,
            })
            return True
        except Exception:
            # Explicit HMAC verification fallback
            message = f"{order_id}|{payment_id}"
            generated_signature = hmac.new(
                key=self.key_secret.encode('utf-8'),
                msg=message.encode('utf-8'),
                digestmod=hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(generated_signature, signature)

    def verify_webhook_signature(self, raw_body: bytes, signature: str, order_id: str = None, payment_id: str = None) -> bool:
        secret = self.webhook_secret or self.key_secret
        if not secret:
            return False

        if raw_body and signature:
            try:
                body_bytes = raw_body if isinstance(raw_body, bytes) else str(raw_body).encode('utf-8')
                generated_signature = hmac.new(
                    key=secret.encode('utf-8'),
                    msg=body_bytes,
                    digestmod=hashlib.sha256
                ).hexdigest()
                if hmac.compare_digest(generated_signature, signature):
                    return True
            except Exception as e:
                logger.warning(f"[RAZORPAY WEBHOOK] Error verifying webhook signature: {e}")

        # Fallback to payment signature verification
        if order_id and payment_id and signature:
            return self.verify_signature(order_id, payment_id, signature)
        return False

    def process_refund(self, payment_id: str, amount: Decimal, reason: str) -> dict:
        if not self.is_configured:
            raise PaymentGatewayConfigurationError("Razorpay payment configuration is not available.")

        amount_in_subunits = int((Decimal(str(amount)) * Decimal('100')).quantize(Decimal('1')))
        try:
            client = self._get_client()
            resp = client.payment.refund(payment_id, {
                'amount': amount_in_subunits,
                'notes': {'reason': reason or 'Customer cancellation / Dispute refund'}
            })
            return {
                "gateway_refund_id": resp.get("id"),
                "amount": float(amount),
                "status": resp.get("status", "processed"),
                "raw_response": resp,
            }
        except PaymentGatewayConfigurationError:
            raise
        except Exception as exc:
            logger.error(f"[RAZORPAY] Refund processing failed: {exc}", exc_info=True)
            raise PaymentGatewayError(f"Razorpay refund failed: {str(exc)}")


class SimulatedGatewayAdapter(PaymentGatewayAdapter):
    """
    Deterministic simulated gateway adapter for test suites and sandbox offline demo mode.
    """
    def __init__(self):
        self.key_id = "rzp_test_simulated_key"
        self.key_secret = "sim_test_secret_1234567890abcdef"
        self.webhook_secret = "sim_webhook_secret_1234567890abcdef"

    def create_order(self, amount: Decimal, currency: str, receipt: str, notes: dict = None) -> dict:
        order_id = f"order_sim_{secrets.token_hex(8)}"
        return {
            "gateway_order_id": order_id,
            "amount": float(amount),
            "amount_subunits": int((Decimal(str(amount)) * Decimal('100')).quantize(Decimal('1'))),
            "currency": currency or "INR",
            "key_id": self.key_id,
            "receipt": receipt,
        }

    def verify_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        if signature in ["valid_simulated_signature", "sim_signature_test", "valid_webhook_sig"]:
            return True
        message = f"{order_id}|{payment_id}"
        generated_signature = hmac.new(
            key=self.key_secret.encode('utf-8'),
            msg=message.encode('utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(generated_signature, signature)

    def verify_webhook_signature(self, raw_body: bytes, signature: str, order_id: str = None, payment_id: str = None) -> bool:
        if signature in ["valid_simulated_signature", "sim_signature_test", "valid_webhook_sig"]:
            return True
        if raw_body:
            body_bytes = raw_body if isinstance(raw_body, bytes) else str(raw_body).encode('utf-8')
            generated_signature = hmac.new(
                key=self.webhook_secret.encode('utf-8'),
                msg=body_bytes,
                digestmod=hashlib.sha256
            ).hexdigest()
            if hmac.compare_digest(generated_signature, signature):
                return True
        if order_id and payment_id:
            return self.verify_signature(order_id, payment_id, signature)
        return False

    def process_refund(self, payment_id: str, amount: Decimal, reason: str) -> dict:
        refund_id = f"rfnd_sim_{secrets.token_hex(8)}"
        return {
            "gateway_refund_id": refund_id,
            "amount": float(amount),
            "status": "processed",
        }


def get_payment_gateway(provider: str = None) -> PaymentGatewayAdapter:
    """Factory to retrieve configured gateway adapter."""
    selected = provider or getattr(settings, 'PAYMENT_GATEWAY_PROVIDER', 'RAZORPAY')
    if selected.upper() == 'SIMULATED':
        return SimulatedGatewayAdapter()
    return RazorpayGatewayAdapter()
