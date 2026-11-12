from django.urls import path
from apps.payments.views import (
    PaymentInitiateView,
    PaymentVerifyView,
    PaymentWebhookView,
    BookingInvoiceView,
    CustomerInvoiceListView,
)

urlpatterns = [
    path('payments/initiate/', PaymentInitiateView.as_view(), name='payment-initiate'),
    path('payments/razorpay/order/', PaymentInitiateView.as_view(), name='payment-razorpay-order'),
    path('payments/verify/', PaymentVerifyView.as_view(), name='payment-verify'),
    path('payments/razorpay/verify/', PaymentVerifyView.as_view(), name='payment-razorpay-verify'),
    path('payments/webhook/', PaymentWebhookView.as_view(), name='payment-webhook'),
    path('payments/booking/<uuid:booking_id>/invoice/', BookingInvoiceView.as_view(), name='booking-invoice'),
    path('payments/invoices/', CustomerInvoiceListView.as_view(), name='customer-invoices'),
]
