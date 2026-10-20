from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from rest_framework.exceptions import PermissionDenied

from backend.accounts.permissions import has_role
from .models import SupportConversation


# check if the user is authorized to view the conversation, either as the customer, the assigned agent, or a store manager/admin
def can_view(user, conversation):
    return (
        conversation.user_id == user.id
        or conversation.agent_id == user.id
        or has_role(user, "Store Manager", "Admin")
    )

# user cannot answer a conversation unless they are the assigned agent or a store manager/admin
def can_answer(user, conversation):
    return conversation.agent_id == user.id or has_role(user, "Store Manager", "Admin")

# use websocket to notify frontend clients that a conversation has been updated, so they can refresh their view
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
