import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q


class CartItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart_items")
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "variant"], name="unique_user_cart_variant"),
            models.CheckConstraint(condition=Q(quantity__gte=1), name="cart_quantity_positive"),
        ]


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending payment"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    total_cents = models.PositiveIntegerField()
    shipping_address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    reservation_expires_at = models.DateTimeField(null=True, blank=True)
    stripe_session_id = models.CharField(max_length=255, null=True, blank=True, unique=True)
    idempotency_key = models.CharField(max_length=128, null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "idempotency_key"], name="unique_user_checkout_key")]
        indexes = [models.Index(fields=["status", "reservation_expires_at"])]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price_cents = models.PositiveIntegerField()
    product_name = models.CharField(max_length=200)


class StripeEvent(models.Model):
    event_id = models.CharField(max_length=255, primary_key=True)
    processed_at = models.DateTimeField(auto_now_add=True)
