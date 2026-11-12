# Payment Processing, Webhooks & Idempotency

## 1. Multi-Stage Payment Architecture

HallBook separates venue bookings into two distinct payment stages:
1. **Advance Deposit** (e.g. 20% of total amount): Required at checkout to lock the date and notify the hall owner.
2. **Balance Settlement** (remaining 80%): Due before the event date via customer dashboard.

```
       Customer Checkout                              Payment Gateway (Razorpay / Stripe)
              │                                                     │
              ├────── POST /api/v1/payments/initiate ──────────────>│ (Creates Gateway Order)
              │       { booking_id, payment_type: 'ADVANCE' }       │
              │                                                     │
              │<───── { order_id, key, amount, currency } ──────────┤
              │                                                     │
              ├────── Modal Checkout UI (UPI / Card / NetBank) ────>│
              │                                                     │
              │<───── Customer completes payment ───────────────────┤
              │       (Returns payment_id & signature)              │
              │                                                     │
              ├────── POST /api/v1/payments/verify ────────────────>│
              │       { order_id, payment_id, signature }           │
              │                                                     │
              │       ┌──────────────────────────────────────┐      │
              │       │ Verify HMAC SHA-256 Signature        │      │
              │       │ Check Payment Amount & Currency      │      │
              │       │ Atomic Update: Payment -> SUCCESS    │      │
              │       │ Atomic Update: Booking -> CONFIRMING │      │
              │       │ Enqueue Celery Invoice & Email Tasks │      │
              │       └──────────────────────────────────────┘      │
              │                                                     │
              │<───── HTTP 200 { status: 'SUCCESS' } ───────────────┤
              │                                                     │
              │                                                     │
              │       Payment Webhook Callback (Asynchronous)       │
              │       POST /api/v1/payments/webhook/ <──────────────┤
              │       ┌──────────────────────────────────────┐      │
              │       │ Check Idempotency Key                │      │
              │       │ Verify Webhook Secret                │      │
              │       │ If already processed -> Return 200 OK│      │
              │       │ Else -> Reconcile State              │      │
              │       └──────────────────────────────────────┘      │
```

---

## 2. Idempotency & Concurrency Defenses

Duplicate payment notifications (caused by network retries, double webhook events, or simultaneous user submissions) can corrupt financial records if not guarded.

### Idempotency Safeguards:
1. **Unique Idempotency Key**: Every payment attempt generates an `idempotency_key` (format: `pay_{booking_id}_{payment_type}_{hash}`).
2. **Database Constraint**: `UNIQUE(gateway_order_id, gateway_payment_id)` and `UNIQUE(idempotency_key)`.
3. **Pessimistic Payment Lock**:
   ```python
   with transaction.atomic():
       payment = Payment.objects.select_for_update().get(gateway_order_id=order_id)
       if payment.status == PaymentStatus.SUCCESS:
           return Response({'message': 'Already processed'}, status=200)
       
       # Verify signature
       is_valid = gateway.verify_signature(order_id, payment_id, signature)
       if not is_valid:
           payment.status = PaymentStatus.FAILED
           payment.save()
           raise PaymentVerificationError("Invalid gateway signature")
           
       payment.status = PaymentStatus.SUCCESS
       payment.gateway_payment_id = payment_id
       payment.paid_at = timezone.now()
       payment.save()
       
       booking = Booking.objects.select_for_update().get(id=payment.booking_id)
       booking.amount_paid += payment.amount
       booking.status = BookingStatus.PENDING_OWNER_CONFIRMATION
       booking.save()
   ```

---

## 3. Webhook Signature Verification

Webhooks are protected against tampering using HMAC SHA-256 signatures validated against a stored shared secret:

```python
def verify_webhook_signature(payload_body: bytes, received_signature: str, secret: str) -> bool:
    generated_signature = hmac.new(
        key=secret.encode('utf-8'),
        msg=payload_body,
        digestmod=hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(generated_signature, received_signature)
```

---

## 4. Refund Lifecycle & Invoicing

1. **Refund Execution**:
   - Refunds are never executed by simply editing amounts in place.
   - A distinct `Refund` row is created with reference to the original `Payment`.
   - Refund requests trigger the gateway API to reverse transactions to the original payment method.

2. **Automated Invoicing**:
   - Upon payment verification, Celery task `generate_invoice` compiles a GST-compliant tax invoice.
   - Includes Invoice Number (`INV-YYYY-XXXXX`), GST numbers, SAC/HSN codes, breakdown of base rent, catering, add-ons, and tax (CGST + SGST).
