from django.core import signing
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from backend.accounts.permissions import IsStoreManager, IsSupportStaff, has_role
from .models import ApprovalRequest, SupportConversation, SupportMessage
from .services import can_answer, can_view, publish_update, snapshot


def allowed_conversation(request, conversation_id):
    conversation = get_object_or_404(SupportConversation, pk=conversation_id)
    if not can_view(request.user, conversation):
        raise PermissionDenied("This conversation is not accessible.")
    return conversation


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


@api_view(["GET"])
def conversation_detail(request, conversation_id):
    return Response(snapshot(allowed_conversation(request, conversation_id)))


@api_view(["GET"])
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
    if conversation.status == SupportConversation.Status.ACTIVE:
        return Response(snapshot(conversation))
    conversation.status = SupportConversation.Status.WAITING
    conversation.save(update_fields=["status", "updated_at"])
    publish_update(conversation.id)
    return Response(snapshot(conversation))


@api_view(["POST"])
@permission_classes([IsSupportStaff])
def claim_conversation(request, conversation_id):
    with transaction.atomic():
        conversation = get_object_or_404(SupportConversation.objects.select_for_update(), pk=conversation_id)
        if conversation.status != SupportConversation.Status.WAITING or conversation.agent_id:
            raise ValidationError("This conversation has already been claimed.")
        conversation.agent = request.user
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


@api_view(["GET"])
@permission_classes([IsStoreManager])
def approvals(request):
    qs = ApprovalRequest.objects.order_by("-created_at")
    return Response([{"id": a.id, "action": a.action, "reason": a.reason, "status": a.status, "conversation_id": a.conversation_id} for a in qs[:100]])


@api_view(["POST"])
@permission_classes([IsStoreManager])
def decide_approval(request, approval_id):
    decision = request.data.get("approved")
    if not isinstance(decision, bool):
        raise ValidationError("approved must be true or false.")
    with transaction.atomic():
        approval = get_object_or_404(ApprovalRequest.objects.select_for_update(), pk=approval_id)
        if approval.status != ApprovalRequest.Status.PENDING:
            raise ValidationError("This request has already been reviewed.")
        approval.status = ApprovalRequest.Status.APPROVED if decision else ApprovalRequest.Status.REJECTED
        approval.reviewed_by = request.user
        approval.reviewed_at = timezone.now()
        approval.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    # Approval records a decision; it does not automatically issue a refund.
    return Response({"id": approval.id, "status": approval.status})


@api_view(["POST"])
def websocket_ticket(request, conversation_id):
    conversation = allowed_conversation(request, conversation_id)
    # Short-lived, signed authorization for Channels connections made by JWT clients.
    ticket = signing.dumps(
        {"user_id": request.user.id, "conversation_id": conversation.id},
        salt="northline-support-ws",
    )
    return Response({"ticket": ticket})
