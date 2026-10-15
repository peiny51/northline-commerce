from django.conf import settings
from django.db import models


class SupportConversation(models.Model):
    class Status(models.TextChoices):
        AI = "ai", "AI assistant"
        WAITING = "waiting", "Waiting for staff"
        ACTIVE = "active", "Human support"
        CLOSED = "closed", "Closed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="customer_conversations")
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_conversations")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AI)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class SupportMessage(models.Model):
    conversation = models.ForeignKey(SupportConversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.CharField(max_length=12, choices=[("customer", "Customer"), ("agent", "Agent"), ("ai", "AI")])
    content = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ApprovalRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    conversation = models.ForeignKey(SupportConversation, on_delete=models.CASCADE, related_name="approvals")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requested_approvals")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="reviewed_approvals")
    action = models.CharField(max_length=40, default="escalate")
    reason = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
