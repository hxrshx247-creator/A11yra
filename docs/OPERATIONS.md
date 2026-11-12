# A11yra operations

## Deployment environments

| Setting | Development | Staging | Production |
| --- | --- | --- | --- |
| Database | SQLite by default or Compose Postgres | Isolated Postgres | Managed Postgres |
| Files | Private local directory | Isolated writable volume | Encrypted persistent volume, one API worker |
| Cookies | Loopback HTTP or Secure on HTTPS | Secure over HTTPS | Secure over HTTPS |
| Mail | Console delivery or STARTTLS SMTP | Test SMTP and synthetic addresses | STARTTLS SMTP with a verified sender |
| Billing | Demo plans by default | Demo or Stripe test | Test-only support |
| Monitoring | Local structured logs | Readiness and restricted metrics | Readiness, restricted metrics, optional Sentry |

`make dev` starts API, web and Postgres at [http://127.0.0.1:5173](http://127.0.0.1:5173). You can run `docker compose up --build` directly on Windows. `compose.yaml` uses local-only database credentials and binds the web port to loopback. The API and Postgres services have no published host port.

See [deployment verification](DEPLOYMENT.md) for the clean-checkout Compose commands and host limitations.

For an HTTPS deployment, serve the built frontend and route `/api/*` and `/r/*` to the API at the same public origin. Set `A11YRA_ENV`, `A11YRA_PUBLIC_URL`, `A11YRA_CORS_ORIGINS`, `A11YRA_SECRET`, `DATABASE_URL`, SMTP settings and `A11YRA_DATA_DIR` in the host’s secret or environment manager. Keep API access logs and proxy logs off for reader paths. Trust forwarded client addresses only from a proxy you control. Run one API worker while rate limits and file locks live in-process. Set `SUPPORT_EMAIL` at frontend build time.

### Free-tier preview

Create a Render Docker web service from the repo root with `backend/Dockerfile` and `/api/ready` as the health path. Provision a separate free Postgres database. The Docker entrypoint migrates the database before startup. Deploy the frontend on a static host that can proxy both API and learner paths without rewriting response cookies, and set the public URL to that frontend origin. Configure a test SMTP server on an allowed STARTTLS port. A private local demo is the simplest alternative for exercising verification links printed to the development console.

Use synthetic files on Render’s free tier. Restarts clear the free web service’s filesystem, free Postgres expires after 30 days, and common SMTP ports are restricted. A persistent file volume and durable database are required for a real pilot. [Render free-tier limits](https://render.com/docs/free), [Render web service setup](https://render.com/docs/web-services)

### Render API and Vercel frontend

1. Connect this repository to Render and create a Docker web service from the repository root. Set the Dockerfile path to `backend/Dockerfile` and the health check path to `/api/ready`. Attach a writable private disk at `/app/backend/.a11yra-data` for persistent uploads and published readers.
2. Connect the same repository to Vercel. Build from the repository root with `npm ci --prefix frontend && npm run build --prefix frontend`, and publish `frontend/dist`. Building from the root makes the shared plan configuration available to Vite.
3. Route `/api/:path*` and `/r/:path*` to the matching paths on the Render service. Put those rewrites ahead of the frontend SPA fallback to `/index.html` so a direct audit or sign-in URL loads the app while API and reader URLs reach the backend.
4. On Render, set `A11YRA_ENV=production`, `A11YRA_DATA_DIR=/app/backend/.a11yra-data`, and set both `A11YRA_PUBLIC_URL` and `A11YRA_CORS_ORIGINS` to the exact public Vercel HTTPS origin. Add the Postgres URL as `DATABASE_URL`, a generated `A11YRA_SECRET`, and the SMTP settings in the dashboard. Keep these values out of Git. Use a STARTTLS port your Render plan and mail provider both support.
5. After deployment, check `/api/ready` through the Vercel URL. Use a synthetic account to sign in, open a sample, approve a repair, re-audit, and download the offline reader. Also open a published reader URL if sharing is enabled for the demo.

[Render Docker services](https://render.com/docs/docker) · [Vercel external rewrites](https://vercel.com/docs/routing/rewrites)

## Runbook

- **Migrate** — Run `alembic -c backend/alembic.ini upgrade head` before startup when running without the Docker entrypoint. Run `alembic -c backend/alembic.ini check` to compare the database with model metadata.
- **Back up** — Pause the writer and sweep before taking a coordinated database and private-volume snapshot. For Postgres, use a restricted `pg_dump -Fc` export or provider snapshot. For SQLite, stop the API before copying the database. Store encrypted backups with limited access and an expiry policy consistent with the product’s retention.
- **Restore** — Restore both stores to an isolated environment. Run Alembic, start cleanup, and compare document and share metadata with stored files. Reapply deletions made after the snapshot before exposing the service. Invalidate sessions from the snapshot.
- **Rotate** — Rotate the database and SMTP credentials using the deployment secret store. Replace `A11YRA_SECRET` and clear sessions so each user signs in with a fresh CSRF token. Revoke affected workspace API keys and issue new ones. Rotate the metrics token and Stripe webhook secret at their respective providers.
- **Delete a user** — Ask the signed-in user to use **Account and data → Delete my account and all data**, with their password and confirmation. For an operator-assisted request, verify identity and use the same deletion service during a controlled maintenance window. Direct SQL deletion leaves files behind. Account deletion anonymizes actor identifiers on retained activity and records a deletion event.
- **Inspect an incident** — Use request IDs, status counts and route templates. API and reader tokens, request bodies, document names and document text belong outside service logs. Console email in development includes synthetic recipients and link tokens. Use SMTP outside development.

## Stripe test billing

Create Educator and Institution test prices. Set `STRIPE_TEST_ENABLED=1` with a test secret key, signing secret and both price IDs. Register `/api/billing/webhook` for `customer.subscription.created`, `customer.subscription.updated` and `customer.subscription.deleted`. Stripe is the hosted test checkout provider. Manage test subscription cancellation and switching in Stripe. [Stripe testing documentation](https://docs.stripe.com/automated-testing)

## Integration API

The owner of an Institution workspace creates a key in **Workspace → API keys**. Copy the key when shown. The endpoint returns the existing Audit JSON contract and records usage and last-used time. The upload is not added to the workspace document list.

```sh
curl -X POST http://127.0.0.1:5173/api/public/v1/audit \
  -H "Authorization: Bearer ${A11YRA_API_KEY}" \
  -F 'file=@backend/fixtures/pilot-syllabus.docx;type=application/vnd.openxmlformats-officedocument.wordprocessingml.document'
```

API reference is at `/api/docs`. Health is at `/api/health`, database and storage readiness at `/api/ready`, and request counts at `/api/metrics` with a separate bearer token. Enable the optional Sentry hook with `A11YRA_SENTRY_DSN`. The hook sends a generic failure event with request and PII integrations disabled.
