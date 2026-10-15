from decimal import Decimal, InvalidOperation

from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer


def price_cents(value):
    try:
        amount = Decimal(value)
        if not amount.is_finite() or amount < 0:
            raise ValueError
        return int(amount * 100)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Price must be a non-negative CAD amount.")


@api_view(["GET"])
@permission_classes([AllowAny])
def products(request):
    try:
        page = int(request.query_params.get("page", 1))
        limit = int(request.query_params.get("limit", 12))
        if page < 1 or limit < 1 or limit > 48:
            raise ValueError
    except ValueError:
        return Response({"error": "Invalid pagination."}, status=400)

    qs = Product.objects.filter(is_active=True).select_related("category").prefetch_related("variants")
    search = request.query_params.get("search", "").strip()
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(brand__icontains=search) | Q(description__icontains=search))
    if request.query_params.get("category"):
        qs = qs.filter(category__name=request.query_params["category"])
    if request.query_params.get("brand"):
        qs = qs.filter(brand=request.query_params["brand"])
    try:
        if request.query_params.get("min_price_cad"):
            qs = qs.filter(price_cents__gte=price_cents(request.query_params["min_price_cad"]))
        if request.query_params.get("max_price_cad"):
            qs = qs.filter(price_cents__lte=price_cents(request.query_params["max_price_cad"]))
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

    ordering = {
        "newest": ("-created_at", "-id"),
        "price_asc": ("price_cents", "id"),
        "price_desc": ("-price_cents", "id"),
        "name_asc": ("name", "id"),
    }
    sort = request.query_params.get("sort", "newest")
    if sort not in ordering:
        return Response({"error": "Invalid sort option."}, status=400)
    qs = qs.order_by(*ordering[sort])
    total = qs.count()
    offset = (page - 1) * limit
    items = ProductSerializer(qs[offset:offset + limit], many=True).data
    return Response({"items": items, "page": page, "limit": limit, "total": total, "has_more": offset + limit < total})


@api_view(["GET"])
@permission_classes([AllowAny])
def product_detail(request, product_id):
    try:
        product = Product.objects.select_related("category").prefetch_related("variants").get(pk=product_id, is_active=True)
    except Product.DoesNotExist:
        return Response({"error": "Product not found."}, status=404)
    return Response(ProductSerializer(product).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def categories(request):
    return Response(CategorySerializer(Category.objects.order_by("name"), many=True).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def brands(request):
    return Response(list(Product.objects.filter(is_active=True).order_by("brand").values_list("brand", flat=True).distinct()))
