from django.urls import path
from . import views

urlpatterns = [
    path("cart", views.cart),
    path("cart/<int:item_id>", views.cart_item),
    path("checkout", views.checkout),
    path("orders", views.orders),
    path("stripe/webhook", views.stripe_webhook),
]
