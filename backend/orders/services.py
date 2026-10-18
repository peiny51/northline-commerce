from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from backend.catalog.models import ProductVariant
from .models import CartItem, Order, OrderItem
from .serializers import CartItemSerializer, OrderSerializer


def cart_snapshot(user):
    # Join the two ForeignKey levels needed by the nested cart serializer.
    items = (
        CartItem.objects
        .filter(user=user)
        .select_related("variant__product")
    )
    return CartItemSerializer(items, many=True).data

def order_snapshot(order):
    return OrderSerializer(order).data

@transaction.atomic
def reserve_checkout(user, address, key):
    # lock and serialize checkouts for the same customer to prevent duplicate reservations.
    get_user_model().objects.select_for_update().get(pk=user.pk)

    # Repeated requests with the same key must reuse the existing order.
    previous = Order.objects.filter(
        user=user,
        idempotency_key=key,
    ).first()

    if previous:
        return previous, False

    cart_items = list(
        CartItem.objects
        .select_for_update()
        .filter(user=user)
        .order_by("variant_id")
    )

    if not cart_items:
        raise ValidationError("Cart is empty.")

    variant_ids = sorted({
        item.variant_id for item in cart_items
    })

    # Lock inventory in a consistent order to reduce deadlock risks.
    # in case of concurrent checkouts, the first transaction to lock a variant will reserve it, and the second will fail if stock is insufficient.
    variants = {
        variant.id: variant
        for variant in (
            ProductVariant.objects
            .select_for_update()
            .select_related("product")
            .filter(id__in=variant_ids)
            .order_by("id")
        )
    }

    total = 0
    # check stock and calculate total price before creating the order to avoid partial reservations.
    for item in cart_items:
        variant = variants[item.variant_id]

        if (
            not variant.product.is_active
            or variant.stock < item.quantity
        ):
            raise ValidationError(
                f"Insufficient stock for {variant.product.name}."
            )

        total += variant.product.price_cents * item.quantity

    # Create the order and reserve stock in a single transaction to ensure consistency.
    order = Order.objects.create(
        user=user,
        total_cents=total,
        shipping_address=address,
        idempotency_key=key,
        reservation_expires_at=timezone.now() + timedelta(minutes=40),
    )

    for item in cart_items:
        variant = variants[item.variant_id]

        # Reserve stock when checkout starts, not after payment.
        variant.stock -= item.quantity
        variant.save(update_fields=["stock"])

        OrderItem.objects.create(
            order=order,
            variant=variant,
            quantity=item.quantity,
            unit_price_cents=variant.product.price_cents,
            product_name=variant.product.name,
        )

    # The reserved items now belong to the pending order.
    CartItem.objects.filter(
        pk__in=[item.pk for item in cart_items]
    ).delete()

    return order, True


@transaction.atomic
def finalize_payment(order_id):
    # Lock the order to prevent concurrent modifications during payment finalization.
    order = (
        Order.objects
        .select_for_update()
        .get(pk=order_id)
    )

    # Repeated Stripe events must not finalize the same order twice.
    if order.status == Order.Status.PAID:
        return order

    # Only pending orders can be finalized; expired or cancelled orders cannot be paid.
    if order.status != Order.Status.PENDING:
        raise ValidationError("Order is no longer payable.")

    order.status = Order.Status.PAID
    order.save(update_fields=["status"])

    return order

# Release reserved stock and optionally restore items to the cart if payment fails or expires.
@transaction.atomic
def release_reservation(
    order_id,
    expired=False,
    restore_cart=False,
):
    order = (
        Order.objects
        .select_for_update()
        .get(pk=order_id)
    )

    # Only pending orders can release reserved inventory.
    if order.status != Order.Status.PENDING:
        return order

    items = list(
        order.items.order_by("variant_id")
    )

    variant_ids = [item.variant_id for item in items]

    variants = {
        variant.id: variant
        for variant in (
            ProductVariant.objects
            .select_for_update()
            .filter(id__in=variant_ids)
            .order_by("id")
        )
    }

    for item in items:
        variant = variants[item.variant_id]

        # Return reserved inventory to available stock.
        variant.stock += item.quantity
        variant.save(update_fields=["stock"])

        if restore_cart:
            # Restore items if Stripe Checkout could not be created.
            cart_item = (
                CartItem.objects
                .select_for_update()
                .filter(
                    user=order.user,
                    variant=variant,
                )
                .first()
            )

            if cart_item is None:
                # Quantity must be positive to satisfy the database constraint.
                CartItem.objects.create(
                    user=order.user,
                    variant=variant,
                    quantity=item.quantity,
                )
            else:
                # Preserve any items added after the checkout attempt.
                cart_item.quantity += item.quantity
                cart_item.save(update_fields=["quantity"])

    order.status = (
        Order.Status.EXPIRED
        if expired
        else Order.Status.CANCELLED
    )

    order.save(update_fields=["status"])

    return order