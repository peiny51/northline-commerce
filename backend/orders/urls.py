from django.urls import path
from . import views


urlpatterns = [
    path("cart", views.cart),
    path("cart/<int:item_id>", views.cart_item),

    path("checkout", views.checkout),

    path("orders", views.orders),
    path("orders/<uuid:order_id>/pay", views.pay_order),
    path("orders/<uuid:order_id>/cancel", views.cancel_order),

    path("stripe/webhook", views.stripe_webhook),
]