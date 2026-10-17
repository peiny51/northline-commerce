import logging
import os
import uuid

from django.utils import timezone
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from backend.catalog.models import ProductVariant
from .models import CartItem, Order, StripeEvent
from .serializers import OrderSerializer
from .services import (
    cart_snapshot,
    finalize_payment,
    order_snapshot,
    release_reservation,
    reserve_checkout,
)


logger = logging.getLogger(__name__)


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
            # Create with a positive quantity to satisfy the DB constraint.
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

        # Keep the same lock order as the add-to-cart operation.
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
        # Only newly created orders can release this reservation.
        if created:
            release_reservation(
                order.id,
                restore_cart=True,
            )

        logger.exception(
            "Unable to create Stripe Checkout for order %s.",
            order.id,
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

    return Response(OrderSerializer(queryset[:100], many=True).data)


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
        # Reject unsigned or tampered webhook payloads.
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

    event_type = event["type"]

    relevant_events = {
        "checkout.session.completed",
        "checkout.session.expired",
        "checkout.session.async_payment_succeeded",
        "checkout.session.async_payment_failed",
    }

    if event_type not in relevant_events:
        return JsonResponse({"received": True})

    session = event["data"]["object"]
    session_id = session.get("id")
    order_id = session.get("client_reference_id")

    try:
        order_uuid = uuid.UUID(str(order_id))
    except (ValueError, TypeError):
        logger.error(
            "Invalid order ID in Stripe event %s.",
            event["id"],
        )

        return JsonResponse(
            {"error": "Invalid order reference"},
            status=400,
        )

    try:
        with transaction.atomic():
            # Serialize all payment events for the same order.
            order = (
                Order.objects
                .select_for_update()
                .get(pk=order_uuid)
            )

            if order.stripe_session_id != session_id:
                raise ValueError(
                    "Stripe Session does not match the order."
                )

            # A successfully processed event must never run twice.
            # The event record rolls back if processing raises an exception.
            _, created = StripeEvent.objects.get_or_create(
                event_id=event["id"],
            )

            if not created:
                return JsonResponse({"received": True})

            if event_type in {
                "checkout.session.completed",
                "checkout.session.async_payment_succeeded",
            }:
                # Checkout completion alone does not guarantee payment.
                if session.get("payment_status") == "paid":
                    amount = session.get("amount_total")
                    currency = session.get("currency")

                    if (
                        currency != "cad"
                        or amount != order.total_cents
                    ):
                        raise ValueError(
                            "Stripe payment amount or currency mismatch."
                        )

                    # Never reactivate an order whose stock was released.
                    # Such payments require reconciliation.
                    if order.status not in {
                        Order.Status.PENDING,
                        Order.Status.PAID,
                    }:
                        raise ValidationError(
                            "Paid Stripe Session belongs to "
                            "an order whose reservation was released."
                        )

                    finalize_payment(order.id)

                    logger.info(
                        "Order %s confirmed as paid.",
                        order.id,
                    )

            elif event_type == "checkout.session.expired":
                if session.get("status") != "expired":
                    raise ValueError(
                        "Unexpected Checkout Session expiration status."
                    )

                # Paid orders must never release their reserved inventory.
                if order.status == Order.Status.PENDING:
                    release_reservation(
                        order.id,
                        expired=True,
                    )

                    logger.info(
                        "Order %s expired and inventory restored.",
                        order.id,
                    )

            elif event_type == "checkout.session.async_payment_failed":
                if session.get("payment_status") == "paid":
                    raise ValueError(
                        "Cannot release a paid Stripe Session."
                    )

                if order.status == Order.Status.PENDING:
                    release_reservation(
                        order.id,
                        expired=False,
                    )

                    logger.info(
                        "Order %s cancelled after payment failure.",
                        order.id,
                    )

    except Order.DoesNotExist:
        logger.error(
            "Stripe event %s refers to an unknown order.",
            event["id"],
        )

        return JsonResponse(
            {"error": "Unknown order"},
            status=400,
        )

    except ValueError as exc:
        logger.error(
            "Rejected Stripe event %s: %s",
            event["id"],
            exc,
        )

        return JsonResponse(
            {"error": "Invalid Stripe event data"},
            status=400,
        )

    except Exception:
        # Roll back payment changes and the event record on failure.
        # Stripe can retry the webhook after the underlying issue is fixed.
        logger.exception(
            "Stripe webhook processing failed for event %s.",
            event["id"],
        )

        return JsonResponse(
            {"error": "Webhook processing failed"},
            status=500,
        )

    return JsonResponse({"received": True})

@api_view(["POST"])
def pay_order(request, order_id):
    import stripe

    stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

    if not stripe.api_key.startswith("sk_test_"):
        raise ValidationError("Stripe test mode is not configured.")

    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update(),
            pk=order_id,
            user=request.user,
        )

        if order.status != Order.Status.PENDING:
            raise ValidationError(
                "Only pending orders can be paid."
            )

        if not order.stripe_session_id:
            raise ValidationError(
                "This order has no Stripe Checkout session."
            )

        try:
            # Reuse the existing session without reserving stock again.
            session = stripe.checkout.Session.retrieve(
                order.stripe_session_id
            )
        except stripe.StripeError:
            raise ValidationError(
                "Unable to check Stripe payment status. Please retry."
            )

        if session.client_reference_id != str(order.id):
            raise ValidationError(
                "Stripe Checkout does not match this order."
            )

        if session.payment_status == "paid":
            if (
                session.currency != "cad"
                or session.amount_total != order.total_cents
            ):
                raise ValidationError(
                    "Stripe payment amount does not match this order."
                )

            finalize_payment(order.id)

            return Response({
                "order": order_snapshot(order),
                "message": "Payment has already been completed.",
            })

        if (
            session.status != "open"
            or session.payment_status != "unpaid"
        ):
            raise ValidationError(
                "Payment is processing or this Checkout is no longer available."
            )

        if (
            order.reservation_expires_at
            and order.reservation_expires_at <= timezone.now()
        ):
            raise ValidationError(
                "The inventory reservation has expired."
            )

        if not session.url:
            raise ValidationError(
                "Stripe Checkout URL is unavailable."
            )

        return Response({
            "checkout_url": session.url,
        })


@api_view(["POST"])
def cancel_order(request, order_id):
    import stripe

    stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

    if not stripe.api_key.startswith("sk_test_"):
        raise ValidationError("Stripe test mode is not configured.")

    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update(),
            pk=order_id,
            user=request.user,
        )

        if order.status != Order.Status.PENDING:
            raise ValidationError(
                "Only pending orders can be cancelled."
            )

        if order.stripe_session_id:
            try:
                session = stripe.checkout.Session.retrieve(
                    order.stripe_session_id
                )

                if session.client_reference_id != str(order.id):
                    raise ValidationError(
                        "Stripe Checkout does not match this order."
                    )

                if session.payment_status == "paid":
                    if (
                        session.currency != "cad"
                        or session.amount_total != order.total_cents
                    ):
                        raise ValidationError(
                            "Stripe payment amount does not match this order."
                        )

                    finalize_payment(order.id)

                    return Response({
                        "order": order_snapshot(order),
                        "message": (
                            "Payment was already completed. "
                            "The order cannot be cancelled."
                        ),
                    })

                # Never cancel a completed session with a payment
                # that may still be processing asynchronously.
                if session.status == "complete":
                    raise ValidationError(
                        "Payment is processing. Cancellation is unavailable."
                    )

                if session.status == "open":
                    if session.payment_status != "unpaid":
                        raise ValidationError(
                            "Payment status must be checked before cancellation."
                        )

                    # Stripe must close Checkout before stock is released.
                    stripe.checkout.Session.expire(
                        session.id
                    )

                elif session.status != "expired":
                    raise ValidationError(
                        "Checkout is not in a cancellable state."
                    )

            except stripe.StripeError:
                raise ValidationError(
                    "Unable to confirm cancellation with Stripe. "
                    "Please retry."
                )

        # Restore inventory only after Stripe can no longer accept payment.
        release_reservation(order.id)

        return Response({
            "order": order_snapshot(order),
            "message": "Order cancelled.",
        })