"""Run with: python manage.py test tests --verbosity 2 (requires PostgreSQL)."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from backend.catalog.models import Category, Product, ProductVariant
from backend.orders.models import CartItem, Order
from backend.orders.services import reserve_checkout


class CatalogAPITests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Jackets")
        for index, price in enumerate([9000, 12000, 19000]):
            Product.objects.create(
                category=category, name=f"Jacket {index}",
                brand="North Ridge", price_cents=price,
            )

    def test_filter_sort_and_pagination(self):
        response = APIClient().get("/api/products", {
            "category": "Jackets", "max_price_cad": "150",
            "sort": "price_desc", "limit": 1, "page": 1,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 2)
        self.assertTrue(response.data["has_more"])
        self.assertEqual(response.data["items"][0]["price_cents"], 12000)


class AuthorizationTests(TestCase):
    def setUp(self):
        self.customer = get_user_model().objects.create_user(username="cust", password="pass")
        self.agent = get_user_model().objects.create_user(username="agent", password="pass")
        self.group = Group.objects.create(name="Support Agent")
        self.agent.groups.add(self.group)

    def test_customer_cannot_view_staff_queue(self):
        client = APIClient()
        client.force_authenticate(user=self.customer)
        self.assertEqual(client.get("/api/support/queue").status_code, 403)

    def test_customer_cannot_view_other_customer_conversation(self):
        from backend.support.models import SupportConversation

        second = get_user_model().objects.create_user(username="other")
        conversation = SupportConversation.objects.create(user=second)
        client = APIClient()
        client.force_authenticate(user=self.customer)
        self.assertEqual(
            client.get(f"/api/support/conversations/{conversation.pk}").status_code,
            403,
        )

    def test_obsolete_approval_routes_are_removed(self):
        client = APIClient()
        client.force_authenticate(user=self.agent)
        self.assertEqual(client.get("/api/support/approvals").status_code, 404)
        self.assertEqual(
            client.post("/api/support/approvals/1/decision", {"approved": True}).status_code,
            404,
        )

    def test_support_agent_can_view_queue(self):
        client = APIClient()
        client.force_authenticate(user=self.agent)
        self.assertEqual(client.get("/api/support/queue").status_code, 200)


class CheckoutIdempotencyTests(TestCase):
    def test_duplicate_key_does_not_reserve_twice(self):
        category = Category.objects.create(name="Accessories")
        product = Product.objects.create(
            category=category, name="Beanie", brand="North", price_cents=3000,
        )
        variant = ProductVariant.objects.create(product=product, size="One Size", color="Black", stock=4)
        customer = get_user_model().objects.create_user(username="idempotent_buyer")
        CartItem.objects.create(user=customer, variant=variant, quantity=1)

        first, first_created = reserve_checkout(customer, "123 Main Street, Edmonton", "same-key")
        second, second_created = reserve_checkout(customer, "123 Main Street, Edmonton", "same-key")

        variant.refresh_from_db()
        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.id, second.id)
        self.assertEqual(variant.stock, 3)
        self.assertEqual(Order.objects.count(), 1)


class InventoryConcurrencyTests(TransactionTestCase):
    """PostgreSQL row locks must permit exactly one purchase of the final unit."""

    def test_only_one_customer_can_reserve_last_item(self):
        category = Category.objects.create(name="Limited")
        product = Product.objects.create(category=category, name="Last Jacket", brand="North", price_cents=12500)
        variant = ProductVariant.objects.create(product=product, size="M", color="Black", stock=1)
        customers = [get_user_model().objects.create_user(username=f"buyer{i}") for i in range(2)]
        for customer in customers:
            CartItem.objects.create(user=customer, variant=variant, quantity=1)

        barrier = Barrier(2)

        def attempt(user):
            close_old_connections()
            barrier.wait(timeout=10)
            try:
                reserve_checkout(user, "123 Main St, Edmonton, AB", f"test-{user.pk}")
                return True
            except Exception:
                return False
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, customers))

        variant.refresh_from_db()
        self.assertEqual(results.count(True), 1)
        self.assertEqual(variant.stock, 0)
        self.assertEqual(Order.objects.count(), 1)


class JiraEscalationTests(TestCase):
    def test_escalation_creates_ticket_without_approval(self):
        from backend.ai.workflow import escalation_node
        from backend.support.models import SupportConversation

        user = get_user_model().objects.create_user(username="ticket_customer")
        conversation = SupportConversation.objects.create(user=user)

        with patch("backend.ai.workflow.get_my_orders", return_value=[]), \
             patch("backend.ai.workflow.policy_context", return_value=""), \
             patch("backend.ai.workflow.llm") as mocked_llm, \
             patch("backend.ai.workflow.create_jira_escalation", return_value="NC-123") as create_ticket:
            mocked_llm.return_value.invoke.return_value.content = "Staff should review this request."
            result = escalation_node({
                "question": "Please review my refund request.",
                "user_id": user.id,
                "conversation_id": conversation.id,
            })

        self.assertEqual(result["data"]["jira_issue_key"], "NC-123")
        create_ticket.assert_called_once()
        self.assertIn("No refund", result["answer"])
