from django.contrib import admin
from .models import Category, Product, ProductVariant


class VariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "category", "price_cents", "is_active")
    list_filter = ("category", "brand", "is_active")
    search_fields = ("name", "brand", "description")
    inlines = (VariantInline,)


admin.site.register(Category)
