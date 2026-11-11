# ChargeCircle ⚡

India-first EV charging discovery and home-charging marketplace (Next.js + FastAPI). Setup, configuration, operations and
an honest list of what was and was not verified are in **[DEPLOYMENT.md](DEPLOYMENT.md)**.

## What it does

* **Public stations**: search by city/location/radius; Open Charge Map integration (key required) with caching, de-duplication,
  provenance and attribution; sample and manually entered data is always labelled; availability is never claimed as live.
* **Price transparency**: per-kWh, session, time, idle, parking, tax status, source, last-updated and verified flag. Unknown
  prices show **"Price unavailable"**; nothing is defaulted. A cost estimator shows its working, assumptions and exclusions.
* **Navigation**: server-provided destination coordinates; Google/Apple Maps links; optional road distance/time and route
  preview via OpenRouteService; no straight-line distance is ever presented as road distance; no in-app turn-by-turn.
* **Vehicle profiles & compatibility**: only the specs you save are used; unknown stays unknown; results explain why a charger
  is incompatible or unconfirmed and show the effective charging power when known.
* **Comparison**: public stations and home chargers side by side in ₹; "lowest estimated total" is only awarded among options
  whose prices are fully known.
* **Home charging marketplace**: public pins are approximate (300–500 m); the exact address/coordinates are released by the
  backend only to the host, an admin, or a driver whose booking is paid and confirmed. Server-priced bookings, availability
  checks, row-locked overlap protection (plus a PostgreSQL exclusion constraint), 15-minute payment holds.
* **Payments**: Razorpay orders created server-side, HMAC signature verification plus provider confirmation, authenticated and
  idempotent webhooks, refund and cancellation policy (full refund ≥ 2 h before start, host cancellations always refunded),
  admin dispute resolution with audited refunds. A clearly labelled development mock (disabled in production) uses the same
  verification path.
* **Email**: SMTP (configurable), verification, password reset, booking/payment/cancellation/refund/reminder emails, security
  alert on password change, de-duplicated delivery log.
* **Trust & safety**: one review per completed booking (sanitised), reports with moderation states, dispute workflow, admin queues,
  audit trail; one unverified negative report never marks a charger unavailable.
* **Sessions**: scheduled → started → completed/cancelled/disputed. Energy is a *manual entry* recorded as not measured, with a
  recalculated-charge record. There is no metering hardware integration.
* **PWA**: valid manifest/icons, offline page, service worker that never caches account, booking or payment pages.

## Quick start (development)

```bash
cp .env.example backend/.env       # then edit SECRET_KEY / ADMIN_PASSWORD
cd backend && python -m venv venv && . venv/bin/activate && pip install -r requirements.txt
alembic upgrade head && python ../scripts/seed_data.py && uvicorn app.main:app --reload --port 8000
cd ../frontend && echo 'NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1' > .env.local && npm ci && npm run dev
```
Demo accounts created by the seed script are for development only (see `scripts/seed_data.py`).

## Tests

```bash
cd backend && pytest -q                                         # 42 tests on SQLite
TEST_DATABASE_URL=postgresql+psycopg2://user:pw@host/db pytest -q   # same suite on PostgreSQL
python ../scripts/test_e2e_journey.py                           # 29-step end-to-end journey (in-process, mocked externals)
cd ../frontend && npx tsc --noEmit && npm run build
```

## Known limitations / remaining work

* Real Razorpay, SMTP, Open Charge Map and OpenRouteService calls are untested without credentials (only mocked transports).
* The recalculated final charge from a session is recorded but **not** settled automatically (needs a product decision on
  extra charges/partial refunds).
* No host approval workflow for non-instant listings (`instant_booking` is informational); no push notifications.
* Authenticated requests are never cached, so offline access covers signed-out public browsing only.
* PostGIS is provisioned but not yet used; proximity search uses a bounding box plus haversine in application code.
* Several older screens (host dashboard, listing creation, some modals) still use `alert()` for errors.
* Access tokens are held in `localStorage`; moving to HttpOnly cookies would reduce XSS exposure.
* No rate limiting beyond the per-user email-token limit; add one at the proxy or with a library before launch.
