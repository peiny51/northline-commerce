from rest_framework import serializers

from backend.catalog.models import Product, ProductVariant
from .models import CartItem, Order, OrderItem


class CartVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ("id", "size", "color", "stock")


class CartProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name", "price_cents")


class CartItemSerializer(serializers.ModelSerializer):
    variant = CartVariantSerializer(read_only=True)
    product = CartProductSerializer(source="variant.product", read_only=True)

    class Meta:
        model = CartItem
        fields = ("id", "quantity", "variant", "product")


class OrderItemSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="product_name", read_only=True)
    price_cents = serializers.IntegerField(source="unit_price_cents", read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "name", "quantity", "price_cents")


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ("id", "status", "total_cents", "created_at", "shipping_address", "items")
