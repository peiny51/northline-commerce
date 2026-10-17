from django.contrib import admin
from .models import Order, OrderItem, StripeEvent


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("variant", "quantity", "unit_price_cents", "product_name")

    def has_add_permission(self, request, obj=None):
        # Order items must be created by the checkout flow.
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "total_cents", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("id", "user__username", "stripe_session_id")
    readonly_fields = ("id", "user", "status", "total_cents", "shipping_address", "reservation_expires_at", "stripe_session_id", "idempotency_key", "created_at")
    inlines = (OrderItemInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StripeEvent)
class StripeEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "processed_at")
    search_fields = ("event_id",)
    readonly_fields = ("event_id", "processed_at")

    def has_add_permission(self, request):
        # Only the Stripe webhook should record payment events.
        return False

    def has_delete_permission(self, request, obj=None):
        return False
