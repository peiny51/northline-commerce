from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create store staff groups and assign scoped model permissions."

    def handle(self, *args, **options):
        definitions = {
            "Support Agent": ["view_supportconversation", "view_supportmessage", "add_supportmessage"],
            "Store Manager": [
                "add_product", "change_product", "view_product",
                "add_productvariant", "change_productvariant", "view_productvariant",
                "view_order", "view_supportconversation", "view_supportmessage",
            ],
            "Admin": ["view_order", "view_product", "view_supportconversation"],
        }
        for name, codes in definitions.items():
            group, _ = Group.objects.get_or_create(name=name)
            group.permissions.set(Permission.objects.filter(codename__in=codes))
            self.stdout.write(f"Configured group: {name}")
        from django.conf import settings
        from django.contrib.auth import get_user_model

        if settings.DEMO_MODE:
            for username, role in (("demo_agent", "Support Agent"), ("demo_manager", "Store Manager")):
                user, _ = get_user_model().objects.get_or_create(username=username)
                user.groups.add(Group.objects.get(name=role))
                user.is_staff = True
                user.save(update_fields=["is_staff"])
        self.stdout.write(self.style.SUCCESS("Staff roles configured."))
