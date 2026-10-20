from django.urls import path
from . import views

urlpatterns = [
    path("support/conversations", views.conversations),
    path("support/conversations/<int:conversation_id>", views.conversation_detail),
    path("support/conversations/<int:conversation_id>/position", views.queue_position),
    path("support/conversations/<int:conversation_id>/ticket", views.websocket_ticket),
    path("support/conversations/<int:conversation_id>/messages", views.send_message),
    path("support/conversations/<int:conversation_id>/request-human", views.request_human),
    path("support/conversations/<int:conversation_id>/claim", views.claim_conversation),
    path("support/conversations/<int:conversation_id>/close", views.close_conversation),
    path("support/queue", views.support_queue),
]
