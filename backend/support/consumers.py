from urllib.parse import parse_qs

from django.core import signing
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from .models import SupportConversation
from .services import can_view


class SupportConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        user = self.scope.get("user")

        # JWT and demo-mode clients exchange authenticated REST credentials for
        # a short-lived signed ticket. The WebSocket never trusts a user ID
        # supplied by the browser without verifying its signature.
        if not user or not user.is_authenticated:
            params = parse_qs(self.scope.get("query_string", b"").decode())
            ticket = params.get("ticket", [""])[0]
            user = await self.user_from_ticket(ticket)

        if not user or not user.is_authenticated or not await self.authorized(user):
            await self.close(code=4403)
            return
        self.room = f"support_{self.conversation_id}"
        await self.channel_layer.group_add(self.room, self.channel_name)
        await self.accept()

    # authenricate user
    @database_sync_to_async
    def user_from_ticket(self, ticket):
        try:
            payload = signing.loads(ticket, salt="northline-support-ws", max_age=60)
            if payload["conversation_id"] != self.conversation_id:
                return None
            return get_user_model().objects.get(pk=payload["user_id"])
        except (signing.BadSignature, KeyError, get_user_model().DoesNotExist):
            return None

    @database_sync_to_async
    def authorized(self, user):
        try:
            conversation = SupportConversation.objects.get(pk=self.conversation_id)
            return can_view(user, conversation)
        except SupportConversation.DoesNotExist:
            return False

    async def disconnect(self, close_code):
        if hasattr(self, "room"):
            await self.channel_layer.group_discard(self.room, self.channel_name)

    async def conversation_updated(self, event):
        await self.send_json({"type": "conversation_updated", "conversation_id": event["conversation_id"]})
