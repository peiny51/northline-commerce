# Order Cancellation — Northline Outdoor Demo Policy

> Portfolio-only policy for simulated transactions and Stripe test payments.

## Requesting cancellation

A customer may ask to cancel an order by providing its order number. The assistant may explain how to contact support and submit an approval request. The AI cannot directly cancel an order.

## Pending payment vs paid order

A pending Stripe Checkout reservation is not the same as a completed payment. An unpaid reservation can expire and inventory can be released by the reconciliation process after confirming Stripe session state. A test-paid order requires authorized staff review before any cancellation-related action.

## Partial cancellation

Partial cancellations are not automatically supported in this demo. Staff should explain whether a new order is required; the AI must not claim that one item was removed from a paid order.

## Refund handling

Approving a cancellation request does not automatically refund payment. A refund is a separate, authorized payment operation not implemented by this demo assistant.
