from django.contrib import admin
from backend.accounts.permissions import has_role
from .models import SupportConversation, SupportMessage


@admin.register(SupportConversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "agent", "status", "created_at")
    list_filter = ("status",)
    readonly_fields = ("user", "agent", "status", "created_at")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if has_role(request.user, "Store Manager", "Admin"):
            return qs
        return qs.filter(agent=request.user)


admin.site.register(SupportMessage)
