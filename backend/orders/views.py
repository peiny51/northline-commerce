
import os
import uuid

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from backend.catalog.models import ProductVariant
from .models import CartItem, Order, StripeEvent
from .services import (
    cart_snapshot,
    finalize_payment,
    order_snapshot,
    release_reservation,
    reserve_checkout,
)


@api_view(["GET", "POST"])
def cart(request):
    if request.method == "GET":
        return Response(cart_snapshot(request.user))

    try:
        variant_id = int(request.data["variant_id"])
        quantity = int(request.data.get("quantity", 1))
    except (KeyError, ValueError, TypeError):
        raise ValidationError(
            "Valid variant_id and quantity are required."
        )

    if quantity < 1 or quantity > 99:
        raise ValidationError(
            "Quantity must be between 1 and 99."
        )

    with transaction.atomic():
        # Lock the variant to serialize concurrent cart updates.
        variant = get_object_or_404(
            ProductVariant.objects.select_for_update(),
            pk=variant_id,
            product__is_active=True,
        )

        cart_item = (
            CartItem.objects
            .select_for_update()
            .filter(
                user=request.user,
                variant=variant,
            )
            .first()
        )

        current_quantity = (
            cart_item.quantity if cart_item else 0
        )

        new_quantity = current_quantity + quantity

        if new_quantity > 99:
            raise ValidationError(
                "Cart quantity cannot exceed 99."
            )

        if new_quantity > variant.stock:
            raise ValidationError(
                "Requested quantity exceeds available stock."
            )

        if cart_item is None:
            # CartItem.quantity has a database constraint requiring > 0.
            CartItem.objects.create(
                user=request.user,
                variant=variant,
                quantity=new_quantity,
            )
        else:
            cart_item.quantity = new_quantity
            cart_item.save(
                update_fields=["quantity"]
            )

    return Response(
        cart_snapshot(request.user),
        status=201,
    )


@api_view(["DELETE", "PATCH"])
def cart_item(request, item_id):
    if request.method == "PATCH":
        try:
            quantity = int(request.data["quantity"])
        except (KeyError, ValueError, TypeError):
            raise ValidationError(
                "Valid quantity is required."
            )

        if quantity < 1 or quantity > 99:
            raise ValidationError(
                "Quantity must be between 1 and 99."
            )

    with transaction.atomic():
        existing_item = get_object_or_404(
            CartItem,
            pk=item_id,
            user=request.user,
        )

        # Use the same lock order as the add-to-cart operation.
        variant = get_object_or_404(
            ProductVariant.objects.select_for_update(),
            pk=existing_item.variant_id,
        )

        locked_item = get_object_or_404(
            CartItem.objects.select_for_update(),
            pk=item_id,
            user=request.user,
        )

        if request.method == "DELETE":
            locked_item.delete()
        else:
            if quantity > variant.stock:
                raise ValidationError(
                    "Requested quantity exceeds available stock."
                )

            locked_item.quantity = quantity
            locked_item.save(
                update_fields=["quantity"]
            )

    return Response(cart_snapshot(request.user))


def stripe_checkout(order, request):
    import stripe

    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]

    items = list(order.items.all())

    line_items = []

    for item in items:
        line_items.append(
            {
                "price_data": {
                    "currency": "cad",
                    "unit_amount": item.unit_price_cents,
                    "product_data": {
                        "name": item.product_name,
                    },
                },
                "quantity": item.quantity,
            }
        )

    frontend_url = os.getenv(
        "FRONTEND_URL",
        "http://127.0.0.1:5173",
    ).rstrip("/")

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=line_items,
        success_url=(
            f"{frontend_url}/orders?checkout=success"
        ),
        cancel_url=(
            f"{frontend_url}/cart?checkout=cancelled"
        ),
        client_reference_id=str(order.id),
        expires_at=int(
            order.reservation_expires_at.timestamp()
        ),
        idempotency_key=f"northline-checkout-{order.id}",
    )

    order.stripe_session_id = session.id
    order.save(
        update_fields=["stripe_session_id"]
    )

    return session.url


@api_view(["POST"])
def checkout(request):
    address = str(
        request.data.get("shipping_address", "")
    ).strip()

    if len(address) < 10:
        raise ValidationError(
            "A valid shipping address is required."
        )

    idempotency_key = request.headers.get(
        "Idempotency-Key",
        "",
    ).strip()

    if not idempotency_key or len(idempotency_key) > 128:
        raise ValidationError(
            "Idempotency-Key header is required "
            "(max 128 characters)."
        )

    # Only Stripe test payments are allowed for this project.
    stripe_secret = os.getenv(
        "STRIPE_SECRET_KEY",
        "",
    )

    if not stripe_secret.startswith("sk_test_"):
        raise ValidationError(
            "Configure a Stripe test secret key "
            "before checkout."
        )

    order, created = reserve_checkout(
        request.user,
        address,
        idempotency_key,
    )

    if not created and order.status != Order.Status.PENDING:
        return Response(
            {"order": order_snapshot(order)}
        )

    try:
        checkout_url = stripe_checkout(
            order,
            request,
        )
    except Exception:
        # Release stock only when this request created the order.
        if created:
            release_reservation(
                order.id,
                restore_cart=True,
            )

        raise ValidationError(
            "Unable to start Stripe Checkout."
        )

    return Response(
        {
            "order": order_snapshot(order),
            "checkout_url": checkout_url,
        },
        status=201,
    )


@api_view(["GET"])
def orders(request):
    queryset = (
        Order.objects
        .filter(user=request.user)
        .prefetch_related("items")
        .order_by("-created_at")
    )

    return Response(
        [
            order_snapshot(order)
            for order in queryset[:100]
        ]
    )


@csrf_exempt
def stripe_webhook(request):
    import stripe

    if request.method != "POST":
        return JsonResponse(
            {"error": "Method not allowed"},
            status=405,
        )

    webhook_secret = os.getenv(
        "STRIPE_WEBHOOK_SECRET",
        "",
    )

    if not webhook_secret:
        return JsonResponse(
            {"error": "Webhook is not configured"},
            status=503,
        )

    try:
        # Never trust an unsigned Stripe webhook payload.
        event = stripe.Webhook.construct_event(
            request.body,
            request.headers.get("Stripe-Signature", ""),
            webhook_secret,
        )
    except (
        ValueError,
        stripe.error.SignatureVerificationError,
    ):
        return JsonResponse(
            {"error": "Invalid Stripe signature"},
            status=400,
        )

    relevant_events = {
        "checkout.session.completed",
        "checkout.session.expired",
        "checkout.session.async_payment_succeeded",
        "checkout.session.async_payment_failed",
    }

    if event["type"] not in relevant_events:
        return JsonResponse({"received": True})

    session = event["data"]["object"]
    order_id = session.get("client_reference_id")

    try:
        with transaction.atomic():
            # Prevent processing the same Stripe event twice.
            _, is_new_event = StripeEvent.objects.get_or_create(
                event_id=event["id"]
            )

            if not is_new_event:
                return JsonResponse({"received": True})

            order = (
                Order.objects
                .select_for_update()
                .get(pk=uuid.UUID(order_id))
            )

            if order.stripe_session_id != session.get("id"):
                raise ValueError(
                    "Stripe session does not match order."
                )

            if event["type"] in {
                "checkout.session.completed",
                "checkout.session.async_payment_succeeded",
            }:
                if session.get("payment_status") == "paid":
                    finalize_payment(order.id)
            else:
                release_reservation(
                    order.id,
                    expired=True,
                )

    except (ValueError, TypeError, Order.DoesNotExist):
        return JsonResponse(
            {"error": "Unknown order"},
            status=400,
        )

    return JsonResponse({"received": True})
