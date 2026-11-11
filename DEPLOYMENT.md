# ChargeCircle: configuration, deployment and operations

This document describes what exists in the repository. Nothing here has been deployed by the authors of this change;
see "Verification status" at the end.

## 1. Environment variables

Templates: `.env.example` (local development) and `.env.production.example` (production). Real `.env*` files are git-ignored
and excluded from archives. In production the backend **refuses to start** if any of the checks in
`Settings.production_problems()` fail (default/short `SECRET_KEY`, `DEBUG`, wildcard CORS, mock payments, SQLite,
non-SMTP email, `AUTO_APPROVE_LISTINGS`, `AUTO_CREATE_TABLES`, localhost `FRONTEND_URL`, missing Razorpay secrets).

| Variable | Required | Purpose |
|---|---|---|
| `ENVIRONMENT` | yes | `development`, `test`, `staging`, `production` |
| `DATABASE_URL` | yes | PostgreSQL/PostGIS in production, e.g. `postgresql+psycopg2://user:pw@db:5432/chargecircle_db` |
| `SECRET_KEY` | yes | JWT signing and home-location fuzzing key. 32+ random chars. Rotating it logs everyone out and moves approximate home pins |
| `FRONTEND_URL`, `BACKEND_URL` | yes | Public URLs; `FRONTEND_URL` is used in emailed links |
| `CORS_ORIGINS` | yes | Comma-separated trusted origins; never `*` |
| `PAYMENT_MODE` | yes | `razorpay` (real) or `mock` (development only; refused in production) |
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` | if razorpay | Server-side API credentials (secret never sent to browsers) |
| `RAZORPAY_WEBHOOK_SECRET` | if razorpay | Secret configured on the Razorpay webhook; used to verify `X-Razorpay-Signature` |
| `EMAIL_BACKEND`, `SMTP_HOST/PORT/USER/PASSWORD`, `EMAIL_FROM` | production | `smtp` for real mail; `console` (prints emails) is development-only |
| `USE_LIVE_CHARGER_FEED`, `OCM_API_KEY` | optional | Enables Open Charge Map. Tunables: `OCM_MAX_RADIUS_KM`, `OCM_CACHE_TTL_SECONDS`, `OCM_ERROR_BACKOFF_SECONDS`, `OCM_TIMEOUT_SECONDS` |
| `ROUTING_PROVIDER`, `ORS_API_KEY` | optional | `openrouteservice` enables road distance/time and route preview. Without it none is shown |
| `BOOKING_HOLD_MINUTES`, `FREE_CANCELLATION_HOURS`, `PLATFORM_FEE_PERCENTAGE` | optional | Defaults 15, 2, 10 |
| `NEXT_PUBLIC_API_URL` | frontend build | Public API base incl. `/api/v1`. **Baked into the bundle at build time** |
| `POSTGRES_PASSWORD` | compose | Database password for the bundled compose file |

## 2. Provider setup

* **Razorpay**: create API keys (test keys for staging, live for production). Add a webhook to
  `https://<api-host>/api/v1/payments/webhook` with events `payment.captured`, `order.paid`, `payment.failed`,
  `refund.processed`, `refund.failed`, and put its secret in `RAZORPAY_WEBHOOK_SECRET`. Keep test and live
  credentials in separate environments; the app has no switch that mixes them.
* **Open Charge Map**: request a key at openchargemap.org, set `OCM_API_KEY` and `USE_LIVE_CHARGER_FEED=true`. Data is
  community-maintained and carries no live connector availability; the UI says so and shows attribution.
* **SMTP**: any SMTP relay with STARTTLS (SES, SendGrid SMTP, Postmark, Gmail Workspace relay, ...). Delivery results are
  stored in `email_logs` (no bodies, tokens or secrets).
* **OpenRouteService** (optional): key in `ORS_API_KEY`.

## 3. Database and migrations

* Schema is managed by Alembic (`backend/alembic`). `0001` is the schema as shipped before this work; `0002` adds the new
  columns/tables, applies data corrections and, on PostgreSQL, adds an exclusion constraint preventing overlapping bookings.
* Fresh install: `cd backend && alembic upgrade head`.
* Existing database created by the old `create_all()`: `alembic stamp 0001 && alembic upgrade head`. **Back up first.**
  Migration `0002` deliberately clears old schema *defaults* on non-sample stations (18.5 INR/kWh with 0 session fee,
  0 parking fee) because they were indistinguishable from "unknown". Re-enter genuine tariffs afterwards.
* Create the first admin (no default password exists): `cd backend && ADMIN_EMAIL=you@co.in python ../scripts/create_admin.py`.
* `scripts/seed_data.py` creates demo data and is refused when `ENVIRONMENT=production`.

## 4. Running

Local development:
```bash
cp .env.example backend/.env      # edit SECRET_KEY, ADMIN_PASSWORD
cd backend && python -m venv venv && . venv/bin/activate && pip install -r requirements.txt
alembic upgrade head && python ../scripts/seed_data.py
uvicorn app.main:app --reload --port 8000
# second terminal
cd frontend && echo 'NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1' > .env.local && npm ci && npm run dev
```
Production-style stack (Docker):
```bash
cp .env.production.example .env.production   # fill in real values
docker compose --env-file .env.production -f docker/docker-compose.yml up -d --build
```
The stack runs `alembic upgrade head` in a one-shot `migrate` service before the backend starts and publishes ports on
`127.0.0.1` only; put a TLS-terminating reverse proxy in front.

Scheduled job (reminders + releasing expired payment holds), e.g. every 15 minutes:
`cd backend && python ../scripts/run_reminders.py`.

## 5. HTTPS, backups, recovery

* **HTTPS**: terminate TLS at a reverse proxy/load balancer (Caddy, nginx + certbot, cloud LB) for both the app and API
  hostnames; redirect HTTP to HTTPS; set `FRONTEND_URL`, `BACKEND_URL`, `CORS_ORIGINS` to the https URLs. The backend runs
  with `--proxy-headers`. Service workers and geolocation require HTTPS outside localhost.
* **Backups**: nightly `pg_dump -Fc chargecircle_db > backup-$(date +%F).dump`, copied off-host and encrypted; keep at
  least 14 daily and 3 monthly copies; enable WAL archiving/PITR if your RPO is under a day. Back up `uploads/` too.
* **Restore drill**: `createdb restored && pg_restore -d restored backup.dump`, point a staging stack at it, run
  `alembic current` and the smoke checks below. Test this before you need it.
* **Migration procedure**: back up, deploy the new image, run `alembic upgrade head` (the compose `migrate` service does),
  check `/health/ready`, keep the previous image tagged for rollback. `alembic downgrade -1` exists for `0002` but loses
  data held in new columns; prefer restoring the backup.

## 6. Health and logging

`GET /health` (liveness, no dependencies) and `GET /health/ready` (queries the database, reports whether payment/webhook/
email/feed settings are present, never their values; 503 when the database is unreachable). Outside development, logs are
JSON lines with a request id (`X-Request-ID`); secrets, tokens and request bodies are never logged.

## 7. Verification status (what was and was not actually checked)

Checked in a sandbox: backend test suite on SQLite and on PostgreSQL 16; Alembic upgrade on both; upgrade of old-shaped
data; no schema drift (`alembic check`); frontend type-check and production build; real `uvicorn` and Next standalone
servers serving all PWA assets; production start-up refusal on unsafe config.

**Not** checked (needs credentials, hardware or a real environment): Razorpay live/test API calls and webhooks from
Razorpay (the code path is exercised only against mocked HTTP transports and locally signed payloads); a real SMTP
server; the real Open Charge Map and OpenRouteService APIs; PostGIS-specific features (none are used yet; distance is
computed in application code); Docker image builds and `docker compose up`; browser behaviour of the service worker,
Razorpay checkout window and geolocation; any real deployment, TLS or backup/restore.
