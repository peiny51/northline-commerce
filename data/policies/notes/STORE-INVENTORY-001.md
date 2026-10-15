# Inventory, Cart and Checkout — Northline Outdoor Demo Policy

> Portfolio-only purchasing rules; inventory is a test dataset.

## Product variants

Availability is tracked per variant (such as size and color). A product being listed does not guarantee that every size is available.

## Cart vs reservation

Adding an item to a cart does not reserve stock. Inventory is validated again during checkout.

## Limited inventory

Two customers may attempt to purchase the last item. The server uses a PostgreSQL transaction and row lock to reserve stock for at most one successful checkout. The other customer may receive an out-of-stock response.

## Unpaid reservations

A Stripe Checkout session can be abandoned. A background reconciliation task verifies session status before releasing stock. A browser redirect alone must never mark an order as paid.

## Order limits

The assistant may recommend or compare products but should not promise a variant remains in stock until checkout finishes.
