# Payments and Refunds — Northline Outdoor Demo Policy

> This project uses Stripe **test mode** only. No real money is collected.

## Payment confirmation

A successful browser redirect is not proof of payment. The server relies on verified Stripe webhooks and order status. Orders are recorded in Canadian dollars (CAD), with amounts represented internally in cents.

## Refund requests

Customers may ask a support agent to review a refund request. The AI can create a human-review record but cannot issue a refund, promise a refund amount, or claim that a refund has been processed.

## Payment failures

A failed, canceled or expired test checkout does not represent a completed purchase. The inventory reservation may later be released after Stripe session reconciliation.

## Taxes and shipping charges

This demo does not calculate production Canadian sales tax or real shipping fees. Do not invent tax rates, delivery fees or actual bank settlement timelines.
