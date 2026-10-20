# Northline Outdoor — Django REST + Agentic AI Commerce


## Architecture

- **Catalog:** Django ORM, Django Admin, public search/filter/sort/load-more endpoints.
- **Authentication:** Auth0 RS256 JWT verification for React customers; Django user mapping; Django Groups + model permissions for store staff. Demo identity headers are accepted **only** with both `DEBUG=true` and `DEMO_MODE=true`.
- **Commerce:** ProductVariant stock, per-user cart, order snapshots in CAD cents, transaction/row-lock-based stock reservations, Stripe **test-mode** Checkout and verified webhooks, payment event deduplication, expiration reconciliation.
- **Support:** AI chat, customer-owned conversations, support-agent claims, automatic Jira MCP ticket escalation, Channels notifications with short-lived signed WebSocket tickets, REST polling fallback.
- **Agent:** LangGraph intent router with general / policy (RAG) / database / hybrid / recommendation / escalation nodes; Django ORM product and authenticated order tools; Gemini for language generation. Policy RAG uses persistent Qdrant dense + BM25 sparse RRF and cross-encoder reranking.
- **Admin:** `/admin/` with catalog inlines, orders as read-only business records, staff groups, conversations. 

### Explicit limitations

This is an implementation **requiring local integration testing**, not a production-certified payment system. The example pricing does not compute Canadian taxes, shipping, or refunds. The AI can automatically create a Jira support ticket through MCP when the configured, authenticated Atlassian connection is available. A ticket does not approve or execute refunds or cancellations; authorized staff decide and perform such actions. Configure `ATLASSIAN_MCP_URL`, `ATLASSIAN_CLOUD_ID`, and `JIRA_PROJECT_KEY` with a trusted authenticated MCP endpoint or OAuth gateway. Ticket delivery requires integration testing. Neither Stripe nor Auth0 nor Gemini can function without your own credentials. A background scheduler is not included; schedule `expire_reservations` yourself. Django migrations are committed; run `migrate` to apply them.

## First start (macOS)

Do not point the new Django models at the old Flask database. The Compose project uses a separate PostgreSQL database/volume and ports (5545, 6334, 6381), intentionally avoiding 5432–5434 conflicts.

```bash
cp .env.example .env
# Change DJANGO_SECRET_KEY; set Stripe/Auth0/Google secrets when ready.
docker compose up -d
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_roles
python manage.py seed_catalog
python manage.py createsuperuser
python -m daphne -b 127.0.0.1 -p 8000 backend.config.asgi:application
```

Second terminal:

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Storefront: <http://127.0.0.1:5173/> · Django Admin: <http://127.0.0.1:8000/admin/> · API: <http://127.0.0.1:8000/api/products>

### AI policy index

Set `GOOGLE_API_KEY` (Gemini Embeddings) in `.env`. Only on first index or changes:

```bash
python -m scripts.sync_documents
```

The index persists in the Qdrant Docker volume. **No re-embedding happens on application startup**. For changes, the sync uses document hashes to avoid unnecessary embedding calls. Gemini calls in normal chat still consume API usage.

### Stripe test checkout

Configure `STRIPE_SECRET_KEY=sk_test_...` and `STRIPE_WEBHOOK_SECRET=whsec_...` in `.env`. Run Stripe CLI forwarding test events:

```bash
stripe listen --forward-to http://127.0.0.1:8000/api/stripe/webhook
```

Copy the generated `whsec_...` into `.env` and restart Daphne. Use Stripe test card 4242 4242 4242 4242. Unconfigured keys cause an explicit checkout error, **not a simulated paid order**. The UI must never trust redirect alone as proof of payment.

For abandoned orders, schedule a periodic task (e.g. every 1–5 minutes):

```bash
python manage.py expire_reservations
```

This command checks Stripe's actual session state before releasing reserved stock. The `support.0002_remove_approvalrequest` migration drops legacy approval records; back up any existing data before running it.

### RBAC and Django Admin

`python manage.py seed_roles` creates `Support Agent`, `Store Manager`, and `Admin` groups. Assign users to groups in Django Admin. Grant `is_staff` for those requiring `/admin/`. `is_superuser` provides all permissions. Assigning a Django Group **does not automatically enable admin login**.

In local `DEBUG=true, DEMO_MODE=true`, the role seeding command also creates `demo_agent` and `demo_manager` and grants appropriate staff groups for browser tests. **Never deploy with Demo Mode on**. For Auth0, configure Domain, Audience and frontend Client ID, then assign staff groups to the corresponding Django users in Admin after their first login.

### Security expectations

- Customer ownership and support-role checks run in the backend, not based on React navigation state.
- Inventory is reserved in one `transaction.atomic()` unit using `select_for_update()` and stable lock order; a checkout key guards duplicate retries. Only the server sets item prices.
- Stripe events are signature-checked and deduplicated by event ID; pending-to-paid and pending-to-expired transitions are transactional.
- Payment reconciliation depends on Stripe state. For real commerce, implement stronger dispute handling, operational alerts and tax calculations.
- Signed WebSocket tickets expire after 60 seconds and are checked again for conversation access. Only room notifications flow over WS; message content travels via authenticated REST.
- AI Jira escalation creates staff follow-up tickets, not approval records; no refund or cancellation is executed automatically.

## Tests

```bash
python manage.py test tests --verbosity 2
python -m unittest tests.test_policy_sync -v
python -m compileall -q backend tests
cd frontend && npm run build
```

Concurrency tests require PostgreSQL (not SQLite). The test runner needs a PostgreSQL role with test DB creation permission. Check real Stripe webhooks and Chat/AI connections in your own environment.

## Key directories

```
backend/
  accounts/      # custom Django user, Auth0 JWT, RBAC
  catalog/       # products, variants, admin, search/filter
  orders/        # cart, reservations, Stripe integration, reconciler
  support/       # human chat, Jira escalation, Channels
  ai/graph/      # reserved for graph extensions
  ai/rag/        # persistent Qdrant policy retrieval + reranking
  ai/workflow.py # LangGraph route and nodes
frontend/src/
  pages/         # catalog, detail, cart, orders, staff workspace
  components/    # support chat and recommendation cards
```

### Policy RAG content and provenance

The index uses six local **fictional demo store** Markdown policies under `data/policies/notes/`. They cover return requests, payment/refunds, cancellation, fulfillment limitations, support approval, and inventory/checkout. `data/policies/sources.json` enumerates the indexed documents. Original eBay-based reference notes are linked in `data/policies/reference/README.md`, and intentionally **not indexed as Northline store rules**. These policies are sample product requirements, not real legal/consumer terms.

After changing policies: `python -m scripts.sync_documents`. Qdrant persists embeddings, and the SHA-256 sync skips unchanged files. Sync is **not** run during Django startup.
