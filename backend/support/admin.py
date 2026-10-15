from django.contrib import admin
from django.utils import timezone
from backend.accounts.permissions import has_role
from .models import ApprovalRequest, SupportConversation, SupportMessage


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


@admin.register(ApprovalRequest)
class ApprovalAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "action", "status", "reviewed_by")
    list_filter = ("status",)
    readonly_fields = ("conversation", "requested_by", "action", "reason", "reviewed_by", "created_at", "reviewed_at")
    # Approval mutations intentionally happen through the controlled DRF endpoint.
    def has_change_permission(self, request, obj=None):
        return has_role(request.user, "Store Manager", "Admin")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(SupportMessage)
