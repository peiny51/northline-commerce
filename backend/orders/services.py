import os
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from backend.catalog.models import ProductVariant
from .models import CartItem, Order, OrderItem


def cart_snapshot(user):
    items = CartItem.objects.filter(user=user).select_related("variant__product", "variant__product__category")
    return [{
        "id": item.id,
        "quantity": item.quantity,
        "variant": {
            "id": item.variant_id, "size": item.variant.size,
            "color": item.variant.color, "stock": item.variant.stock,
        },
        "product": {
            "id": item.variant.product_id, "name": item.variant.product.name,
            "price_cents": item.variant.product.price_cents,
        },
    } for item in items]


def order_snapshot(order):
    return {
        "id": str(order.id), "status": order.status, "total_cents": order.total_cents,
        "created_at": order.created_at.isoformat(), "shipping_address": order.shipping_address,
        "items": [{
            "id": item.id, "name": item.product_name, "quantity": item.quantity,
            "price_cents": item.unit_price_cents,
        } for item in order.items.all()],
    }


@transaction.atomic
def reserve_checkout(user, address, key):
    # A repeated checkout attempt with the same key must never reserve stock again.
    from django.contrib.auth import get_user_model

    # Serialize checkouts belonging to the same customer (including retries).
    get_user_model().objects.select_for_update().get(pk=user.pk)
    previous = Order.objects.filter(user=user, idempotency_key=key).first()
    if previous:
        return previous, False

    cart_items = list(CartItem.objects.select_for_update().filter(user=user).order_by("variant_id"))
    if not cart_items:
        raise ValidationError("Cart is empty.")

    variant_ids = sorted({item.variant_id for item in cart_items})
    # Lock inventory in a stable order to reduce deadlocks under contention.
    variants = {
        variant.id: variant
        for variant in ProductVariant.objects.select_for_update().select_related("product").filter(id__in=variant_ids).order_by("id")
    }

    total = 0
    for item in cart_items:
        variant = variants[item.variant_id]
        if not variant.product.is_active or variant.stock < item.quantity:
            raise ValidationError(f"Insufficient stock for {variant.product.name}.")
        total += variant.product.price_cents * item.quantity

    order = Order.objects.create(
        user=user, total_cents=total, shipping_address=address,
        idempotency_key=key,
        reservation_expires_at=timezone.now() + timedelta(minutes=40),
    )
    for item in cart_items:
        variant = variants[item.variant_id]
        variant.stock -= item.quantity
        variant.save(update_fields=["stock"])
        OrderItem.objects.create(
            order=order, variant=variant, quantity=item.quantity,
            unit_price_cents=variant.product.price_cents,
            product_name=variant.product.name,
        )

    CartItem.objects.filter(pk__in=[item.pk for item in cart_items]).delete()
    return order, True


@transaction.atomic
def finalize_payment(order_id):
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.status == Order.Status.PAID:
        return order
    if order.status != Order.Status.PENDING:
        raise ValidationError("Order is no longer payable.")
    order.status = Order.Status.PAID
    order.save(update_fields=["status"])
    return order


@transaction.atomic
def release_reservation(order_id, expired=False, restore_cart=False):
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.status != Order.Status.PENDING:
        return order
    items = list(order.items.order_by("variant_id"))
    variants = {
        variant.id: variant
        for variant in ProductVariant.objects.select_for_update().filter(id__in=[item.variant_id for item in items]).order_by("id")
    }
    for item in items:
        variant = variants[item.variant_id]
        variant.stock += item.quantity
        variant.save(update_fields=["stock"])
        if restore_cart:
            # Preserve the customer's bag if Stripe session creation failed.
            cart_item, _ = CartItem.objects.get_or_create(
                user=order.user, variant=variant, defaults={"quantity": 0},
            )
            cart_item.quantity += item.quantity
            cart_item.save(update_fields=["quantity"])
    order.status = Order.Status.EXPIRED if expired else Order.Status.CANCELLED
    order.save(update_fields=["status"])
    return order
