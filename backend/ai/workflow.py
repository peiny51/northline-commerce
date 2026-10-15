"""Django-owned LangGraph support workflow: shopping, orders, policy, hybrid, escalation."""
import json
import os
from typing import Literal, TypedDict

from django.db import transaction
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from backend.ai.settings import Config
from backend.ai.tools import get_my_orders, policy_context, search_products
from backend.support.models import ApprovalRequest


Route = Literal["shopping", "orders", "policy", "hybrid", "escalation"]


class AgentState(TypedDict, total=False):
    question: str
    route: Route
    user_id: int
    conversation_id: int
    answer: str
    data: dict


class Decision(BaseModel):
    route: Route = Field(description="Intent route for a store customer request")


class ProductSearch(BaseModel):
    search: str = Field(default="", description="Product name, material, or description keywords")
    category: str = ""
    brand: str = ""
    max_price_cad: float | None = None


def llm():
    return ChatGoogleGenerativeAI(model=Config.GEMINI_MODEL, temperature=0)


def route_node(state: AgentState):
    decision = llm().with_structured_output(Decision).invoke([
        SystemMessage(content=(
            "Route into shopping (products, comparisons, inventory), orders (customer order details), "
            "policy (shipping/return policy), hybrid (specific order + policy), or escalation "
            "(refund, cancellation, sensitive actions requiring staff approval). "
            "Do not treat asking about eligibility as a request to perform an action."
        )),
        HumanMessage(content=state["question"]),
    ])
    return {"route": decision.route}


def shopping_node(state: AgentState):
    criteria = llm().with_structured_output(ProductSearch).invoke([
        SystemMessage(content="Extract product search filters. Do not invent catalog items or stock."),
        HumanMessage(content=state["question"]),
    ])
    products = search_products(**criteria.model_dump())
    answer = llm().invoke([
        SystemMessage(content="Recommend only from the provided catalog JSON. Explain if no product matches. Quote CAD prices. Do not invent features."),
        HumanMessage(content=f"Request: {state['question']}\nCatalog: {json.dumps(products)}"),
    ])
    return {"answer": str(answer.content), "data": {"products": products}}


def orders_node(state: AgentState):
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.get(pk=state["user_id"])
    orders = get_my_orders(user)
    answer = llm().invoke([
        SystemMessage(content="Answer only with provided authenticated user's orders. Never invent order tracking or prices."),
        HumanMessage(content=f"Request: {state['question']}\nOrders: {json.dumps(orders)}"),
    ])
    return {"answer": str(answer.content), "data": {"orders": orders}}


def policy_node(state: AgentState):
    context = policy_context(state["question"])
    answer = llm().invoke([
        SystemMessage(content="Use ONLY the retrieved store policy context. If insufficient, say so. Never promise refunds or actions."),
        HumanMessage(content=f"Question: {state['question']}\nContext:\n{context}"),
    ])
    return {"answer": str(answer.content)}


def hybrid_node(state: AgentState):
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.get(pk=state["user_id"])
    orders = get_my_orders(user)
    context = policy_context(state["question"])
    answer = llm().invoke([
        SystemMessage(content="Use ONLY authenticated customer orders and retrieved store policies. Do not perform cancellations or refunds."),
        HumanMessage(content=f"Question: {state['question']}\nOrders: {json.dumps(orders)}\nPolicies:\n{context}"),
    ])
    return {"answer": str(answer.content)}


def escalation_node(state: AgentState):
    # Human approval is a real DB transition, never an automatic LLM-controlled refund.
    ApprovalRequest.objects.create(
        conversation_id=state["conversation_id"],
        requested_by_id=state["user_id"],
        reason=state["question"],
        action="escalate",
    )
    return {"answer": "I've submitted your request for staff review. No refund or cancellation has been performed."}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("router", route_node)
    for name, node in (
        ("shopping", shopping_node),
        ("orders", orders_node),
        ("policy", policy_node),
        ("hybrid", hybrid_node),
        ("escalation", escalation_node),
    ):
        graph.add_node(name, node)
        graph.add_edge(name, END)
    graph.add_edge(START, "router")
    graph.add_conditional_edges("router", lambda state: state["route"])
    return graph.compile()


def answer_customer(question, user, conversation):
    if not os.getenv("GOOGLE_API_KEY"):
        return {"message": "AI is not configured yet. Please request human support."}
    try:
        result = build_graph().invoke({
            "question": question,
            "user_id": user.id,
            "conversation_id": conversation.id,
        })
        return {"message": result["answer"], "data": result.get("data", {})}
    except Exception:
        # Never expose internal credentials or stack traces to customers.
        return {"message": "I couldn't process that request. Please ask for a human agent."}
