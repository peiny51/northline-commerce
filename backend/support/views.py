from django.core import signing
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from backend.accounts.permissions import IsSupportStaff, has_role
from .models import SupportConversation, SupportMessage
from .services import can_answer, can_view, publish_update, snapshot

# check if the user is authorized to view this conversation
def allowed_conversation(request, conversation_id):
    conversation = get_object_or_404(SupportConversation, pk=conversation_id)
    if not can_view(request.user, conversation):
        raise PermissionDenied("This conversation is not accessible.")
    return conversation


# create conversation and get list of conversations for the user, agent, or store manager/admin
@api_view(["GET", "POST"])
def conversations(request):
    if request.method == "POST":
        conversation = SupportConversation.objects.create(user=request.user)
        return Response(snapshot(conversation), status=201)

    if has_role(request.user, "Store Manager", "Admin"):
        qs = SupportConversation.objects.all()
    elif has_role(request.user, "Support Agent"):
        qs = SupportConversation.objects.filter(agent=request.user)
    else:
        qs = SupportConversation.objects.filter(user=request.user)
    return Response([snapshot(item) for item in qs.order_by("-created_at")[:50]])


# check specific conversation details, including messages, for the user, agent, or store manager/admin
@api_view(["GET"])
def conversation_detail(request, conversation_id):
    return Response(snapshot(allowed_conversation(request, conversation_id)))


# check the position of a conversation in the support queue
def queue_position(request, conversation_id):
    conversation = allowed_conversation(request, conversation_id)
    ahead = SupportConversation.objects.filter(
        status=SupportConversation.Status.WAITING,
        created_at__lt=conversation.created_at,
    ).count()
    return Response({"ahead": ahead})


@api_view(["POST"])
def send_message(request, conversation_id):
    conversation = allowed_conversation(request, conversation_id)
    content = str(request.data.get("content", "")).strip()
    if not content or len(content) > 4000:
        raise ValidationError("Message length must be between 1 and 4000.")

    if conversation.status == SupportConversation.Status.CLOSED:
        raise ValidationError("This conversation is closed.")
    if request.user.id == conversation.user_id:
        sender = "customer"
    elif can_answer(request.user, conversation):
        sender = "agent"
    else:
        raise PermissionDenied("Only the assigned agent can reply.")

    SupportMessage.objects.create(conversation=conversation, sender=sender, content=content)

    if sender == "customer" and conversation.status == SupportConversation.Status.AI:
        from backend.ai.workflow import answer_customer
        result = answer_customer(content, request.user, conversation)
        SupportMessage.objects.create(
            conversation=conversation,
            sender="ai", content=result["message"], data=result.get("data", {}),
        )

    publish_update(conversation.id)
    return Response(snapshot(conversation))


@api_view(["POST"])
def request_human(request, conversation_id):
    conversation = allowed_conversation(request, conversation_id)
    if conversation.user_id != request.user.id:
        raise PermissionDenied("Only the customer can request an agent.")
    if conversation.status == SupportConversation.Status.CLOSED:
        raise ValidationError("Cannot reopen a closed conversation.")
    # human already assigned, no need to change status
    if conversation.status == SupportConversation.Status.ACTIVE:
        return Response(snapshot(conversation))
    conversation.status = SupportConversation.Status.WAITING
    conversation.save(update_fields=["status", "updated_at"])
    publish_update(conversation.id)
    return Response(snapshot(conversation))


# human agent can claim a conversation from the queue, which assigns them to the conversation and changes its status to active
@api_view(["POST"])
@permission_classes([IsSupportStaff])
def claim_conversation(request, conversation_id):
    with transaction.atomic():
        conversation = get_object_or_404(SupportConversation.objects.select_for_update(), pk=conversation_id)
        if conversation.status != SupportConversation.Status.WAITING or conversation.agent_id:
            raise ValidationError("This conversation has already been claimed.")
        conversation.agent = request.user # assign the agent to the conversation
        conversation.status = SupportConversation.Status.ACTIVE
        conversation.save(update_fields=["agent", "status", "updated_at"])
    publish_update(conversation.id)
    return Response(snapshot(conversation))


@api_view(["POST"])
def close_conversation(request, conversation_id):
    conversation = allowed_conversation(request, conversation_id)
    if conversation.status == SupportConversation.Status.CLOSED:
        return Response(snapshot(conversation))
    conversation.status = SupportConversation.Status.CLOSED
    conversation.save(update_fields=["status", "updated_at"])
    publish_update(conversation.id)
    return Response(snapshot(conversation))


@api_view(["GET"])
@permission_classes([IsSupportStaff])
def support_queue(request):
    qs = SupportConversation.objects.filter(status=SupportConversation.Status.WAITING).order_by("created_at")
    return Response([snapshot(item) for item in qs[:50]])


@api_view(["POST"])
def websocket_ticket(request, conversation_id):
    conversation = allowed_conversation(request, conversation_id)
    # Short-lived, signed authorization for Channels connections made by JWT clients.
    ticket = signing.dumps(
        {"user_id": request.user.id, "conversation_id": conversation.id},
        salt="northline-support-ws",
    )
    return Response({"ticket": ticket})
