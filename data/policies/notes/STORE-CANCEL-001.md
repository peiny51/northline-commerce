# Order Cancellation — Northline Outdoor Demo Policy

> Portfolio-only policy for simulated transactions and Stripe test payments.

## Requesting cancellation

A customer may ask to cancel an order by providing its order number. The assistant may explain the available process or create a Jira support ticket through MCP for staff review. The AI cannot directly cancel an order.

## Pending payment vs paid order

A pending Stripe Checkout reservation is not the same as a completed payment. An unpaid reservation can expire and inventory can be released by the reconciliation process after confirming Stripe session state. A test-paid order requires authorized staff review before any cancellation-related action.

## Partial cancellation

Partial cancellations are not automatically supported in this demo. Staff should explain whether a new order is required; the AI must not claim that one item was removed from a paid order.

## Refund handling

Creating a Jira ticket for cancellation review does not refund payment. A refund is a separate, authorized payment operation not implemented by this demo assistant.
