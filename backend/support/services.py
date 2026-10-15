from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from rest_framework.exceptions import PermissionDenied

from backend.accounts.permissions import has_role
from .models import SupportConversation


def can_view(user, conversation):
    return (
        conversation.user_id == user.id
        or conversation.agent_id == user.id
        or has_role(user, "Store Manager", "Admin")
    )


def can_answer(user, conversation):
    return conversation.agent_id == user.id or has_role(user, "Store Manager", "Admin")


def publish_update(conversation_id):
    layer = get_channel_layer()
    async_to_sync(layer.group_send)(
        f"support_{conversation_id}",
        {"type": "conversation.updated", "conversation_id": conversation_id},
    )


def snapshot(conversation):
    messages = conversation.messages.order_by("created_at", "id")
    return {
        "id": conversation.id,
        "status": conversation.status,
        "user_id": conversation.user_id,
        "agent_id": conversation.agent_id,
        "messages": [
            {"id": m.id, "sender": m.sender, "content": m.content, "data": m.data}
            for m in messages
        ],
    }
