from rest_framework import serializers

from backend.catalog.models import Product, ProductVariant
from .models import CartItem


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
