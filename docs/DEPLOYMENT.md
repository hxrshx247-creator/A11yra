# Deployment verification

## What ran on this Windows host

| Command | Result |
| --- | --- |
| `Get-Command docker,podman,wsl,psql -ErrorAction SilentlyContinue` | Found only the WSL launcher. |
| `wsl.exe --list --quiet` | Reported that WSL is not installed. |
| `docker compose version` | PowerShell could not find `docker`. |
| `docker compose up --build --wait` | PowerShell could not find `docker`. The stack did not start. |
| `alembic -c backend/alembic.ini upgrade head --sql` with `DATABASE_URL=postgresql+psycopg://localhost/a11yra` | Generated PostgreSQL DDL offline. The GitHub Actions PostgreSQL migration job checks the schema against a live database. |

A clean-clone Compose build, migration against a live PostgreSQL instance, backend tests on PostgreSQL, and Playwright through the Compose proxy remain unverified locally. The CI Compose job is configured to run these steps on a clean checkout after the changes are pushed.

## Repeat on a Docker host

Set `SUPPORT_EMAIL` to the team's monitored public address before building the frontend. For Compose, set it in the root `.env` or in the build environment. For a standalone frontend build, export it before running Vite. Rebuild after changing the address. A production build without an address hides the email link.

Use a fresh checkout containing the hardening changes and a disposable Compose project. Stop any development frontend already listening on port 5173. Use synthetic data.

```sh
docker compose -p a11yra-verify up --build --wait
docker compose -p a11yra-verify exec -T api alembic upgrade head
docker compose -p a11yra-verify exec -T api alembic check
docker compose -p a11yra-verify exec -T api sh -c 'python -m venv --system-site-packages /tmp/a11yra-tests && /tmp/a11yra-tests/bin/python -m pip install -r requirements-dev.txt && A11YRA_TEST_POSTGRES_URL="$DATABASE_URL" /tmp/a11yra-tests/bin/python -m pytest -q'
npm ci --prefix reader
npx --prefix reader playwright-core install --with-deps chromium
node --test reader/test-product.mjs
```

The container entrypoint applies migrations before starting Uvicorn. Compose waits for database readiness, then API readiness, then checks that the API is reachable through the web proxy. Pytest uses a fresh PostgreSQL schema per test and private temporary file storage. The browser test uses the real Compose URL at `http://127.0.0.1:5173`. On Windows with Microsoft Edge installed, the Playwright flow uses Edge and can skip the Chromium install command. When the disposable verification project is no longer needed, `docker compose -p a11yra-verify down -v` removes its test volumes.

## Single-worker operation

Run one Uvicorn worker and one API replica with a persistent private volume. Document file locking and request rate limits live in that process, and the same process runs the retention sweep. A restart resets the in-memory counters.

Scaling beyond one worker would require shared rate limiting, such as Redis, object storage for document and reader files, distributed coordination for document edits, and a job queue for audit work and retention jobs. The current Compose command uses one worker.
