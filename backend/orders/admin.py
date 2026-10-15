from django.contrib import admin
from .models import CartItem, Order, OrderItem, StripeEvent


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("variant", "quantity", "unit_price_cents", "product_name")


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


admin.site.register(StripeEvent)
