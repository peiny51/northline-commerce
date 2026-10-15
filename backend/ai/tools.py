from django.db.models import Q
from backend.catalog.models import Product, ProductVariant
from backend.catalog.serializers import ProductSerializer
from backend.orders.models import Order
from backend.orders.services import order_snapshot


def search_products(search="", category="", brand="", max_price_cad=None, limit=6):
    """Search store catalog using live prices and stock, not generated recommendations."""
    qs = Product.objects.filter(is_active=True).select_related("category").prefetch_related("variants")
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search) | Q(brand__icontains=search))
    if category:
        qs = qs.filter(category__name__iexact=category)
    if brand:
        qs = qs.filter(brand__iexact=brand)
    if max_price_cad is not None:
        qs = qs.filter(price_cents__lte=int(float(max_price_cad) * 100))
    return ProductSerializer(qs.order_by("price_cents")[:min(max(int(limit), 1), 12)], many=True).data


def get_product_details(product_id):
    product = Product.objects.select_related("category").prefetch_related("variants").filter(id=product_id, is_active=True).first()
    return ProductSerializer(product).data if product else {"error": "Product not found"}


def check_inventory(variant_id):
    variant = ProductVariant.objects.filter(id=variant_id, product__is_active=True).select_related("product").first()
    if not variant:
        return {"error": "Variant not found"}
    return {"product": variant.product.name, "variant_id": variant.id, "size": variant.size, "color": variant.color, "stock": variant.stock}


def get_my_orders(user):
    orders = Order.objects.filter(user=user).prefetch_related("items").order_by("-created_at")[:10]
    return [order_snapshot(order) for order in orders]


def policy_context(query):
    from backend.ai.rag.reranker import rerank_results
    from backend.ai.rag.vector_store import search_hybrid

    candidates = search_hybrid(query, limit=10)
    ranked = rerank_results(query, candidates, limit=5)
    return "\n\n".join(
        f"Source: {point.payload.get('title', 'Policy')}\n{point.payload['text']}"
        for point, _ in ranked
    )
