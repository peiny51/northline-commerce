import os
import stripe
from django.core.management.base import BaseCommand
from django.utils import timezone
from backend.orders.models import Order
from backend.orders.services import finalize_payment, release_reservation


class Command(BaseCommand):
    help = "Reconcile expired unpaid Stripe reservations safely. Run periodically."

    def handle(self, *args, **options):
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
        if not stripe.api_key:
            self.stderr.write("STRIPE_SECRET_KEY missing; no reservations were changed.")
            return

        expired = Order.objects.filter(
            status=Order.Status.PENDING,
            reservation_expires_at__lte=timezone.now(),
        )[:200]
        for order in expired:
            if not order.stripe_session_id:
                release_reservation(order.id, expired=True)
                continue
            try:
                session = stripe.checkout.Session.retrieve(order.stripe_session_id)
                if session.payment_status == "paid":
                    finalize_payment(order.id)
                elif session.status == "expired":
                    release_reservation(order.id, expired=True)
                elif session.status == "open":
                    # Stripe must confirm expiry before stock is returned.
                    stripe.checkout.Session.expire(session.id)
                    release_reservation(order.id, expired=True)
            except stripe.StripeError as exc:
                self.stderr.write(f"Order {order.id}: reconciliation postponed ({exc})")
        self.stdout.write("Reservation reconciliation complete.")
