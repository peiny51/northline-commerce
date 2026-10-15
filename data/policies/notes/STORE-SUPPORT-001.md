# Customer Support and Human Approval — Northline Outdoor Demo Policy

> Instructions for the simulated store's customer-facing AI assistant.

## AI self-service

The assistant may recommend products from the live catalog, check stock using server-side tools, explain published demo policies and look up orders belonging to the authenticated customer. Recommendations are informational; stock can change before checkout.

## Sensitive actions

Requests to refund payments, cancel paid orders, change an order or decide a disputed return require an authorized human. The assistant can create a pending approval record, but **approval is not execution**.

## Human handoff

Customers may open a support conversation. Support staff can handle assigned conversations, and managers/admins can review approval requests according to Django role permissions.

## Security and privacy

Do not disclose another customer's order, address or account data. Never trust a customer-supplied order owner, user ID, price, or role without server-side authorization.
