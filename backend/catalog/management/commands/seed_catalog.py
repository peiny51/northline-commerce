from django.core.management.base import BaseCommand
from backend.catalog.models import Category, Product, ProductVariant


SAMPLES = [
    ("Alpine Shell Jacket", "North Ridge", 15999, "Jackets", "Waterproof shell for wet weather."),
    ("Insulated Parka", "Summit Trail", 22999, "Jackets", "Warm insulated winter parka."),
    ("Trail Hiking Boots", "Rockline", 11999, "Footwear", "Durable boots for day hikes."),
    ("Everyday Daypack", "Trailworks", 6999, "Backpacks", "Lightweight 22L backpack."),
    ("Thermal Beanie", "Summit Trail", 2499, "Accessories", "Warm knit hat."),
    ("Lightweight Rain Jacket", "North Ridge", 8999, "Jackets", "Packable rain protection."),
]


class Command(BaseCommand):
    help = "Seed repeatable sample products without changing existing orders or stock."

    def handle(self, *args, **options):
        for name, brand, price, category_name, description in SAMPLES:
            category, _ = Category.objects.get_or_create(name=category_name)
            product, created = Product.objects.get_or_create(
                name=name,
                defaults={
                    "brand": brand, "price_cents": price,
                    "category": category, "description": description,
                },
            )
            if not created:
                continue
            sizes = ("S", "M", "L") if category_name == "Jackets" else ("One Size",)
            for size in sizes:
                ProductVariant.objects.create(product=product, size=size, color="Black", stock=12)
        self.stdout.write(self.style.SUCCESS("Sample catalog ready."))
