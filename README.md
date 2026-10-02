# accentsbot

Telegram bot for Russian EGE accent and paronym practice.

The repository is the deployment source of truth for the modernized service. The legacy
Docker Compose stack remains on the old server only for the rollback window; it is not the
current deployment model.

## Architecture

```text
Telegram
   |
   | HTTPS webhook
   v
Coolify / reverse proxy
   |
   v
accentsbot :8080
   |-- GET  /
   |-- GET  /healthz
   `-- POST /telegram/webhook
        |
        +--> PostgreSQL
        `--> Redis (aiogram FSM storage)
```

Runtime characteristics:

- Python 3.13.15;
- aiogram 3 webhook transport;
- PostgreSQL managed by Alembic;
- Redis for FSM state, with in-memory fallback when explicitly disabled;
- non-root container UID/GID `10001`;
- fail-closed `/healthz` checks PostgreSQL and Redis;
- `APP_SMOKE_MODE=true` starts HTTP/DB/Redis checks without creating a Telegram client,
  registering a webhook, sending startup notifications, or starting external bot work.

## Branch and release model

```text
dev  -> development release -> Coolify DEV
main -> production release  -> Coolify production
```

Pull requests run quality checks, PostgreSQL 18 migration preflight, and a Docker build.
Pushes to `dev`/`main` additionally publish an immutable GHCR image, then run that exact
registry digest in smoke mode. Automatic Coolify deployment is guarded independently by:

```text
DEPLOY_DEV_ENABLED
DEPLOY_PRODUCTION_ENABLED
```

Both switches stay `false` during bootstrap. The canonical release identity is the
`ghcr.io/...@sha256:...` digest printed in the GitHub Actions Summary.

## Local development

Prerequisites: Docker, `uv`, Git, and Python 3.13.15 (uv can install Python itself).

```bash
export UV_LINK_MODE=copy   # recommended for WSL repositories under /mnt/c
make setup
make check
```

Run a complete local smoke stack with PostgreSQL 18 + Redis + the application:

```bash
make compose-up
curl -fsS http://127.0.0.1:8080/healthz
make compose-down
```

`compose.dev.yml` runs Alembic preflight before starting the application. PostgreSQL 18 data
is mounted at `/var/lib/postgresql` rather than the pre-18 `/var/lib/postgresql/data` path.

## Configuration

Copy `.env.example` for local use; do not commit `.env` files.

Modern runtime variables:

```text
APP_ENV
LOG_LEVEL
APP_SMOKE_MODE
NOTIFY_ADMINS_ON_STARTUP
RELEASE_REVISION

DATABASE_URL

USE_REDIS
REDIS_URL

BOT_TOKEN
ADMIN_IDS

WEB_SERVER_HOST
PORT
WEBHOOK_BASE_URL
WEBHOOK_PATH
WEBHOOK_SECRET
```

The old `DB_*` / `POSTGRES_*`, `REDIS_*`, and `ADMINS` names remain accepted as migration
fallbacks. Coolify should use `DATABASE_URL`, `REDIS_URL`, and `ADMIN_IDS`.

DEV and production must use different Telegram bot tokens.

## Database migration

The actual legacy production database is already PostgreSQL 14, not SQLite. Migration to the
new PostgreSQL 18 resource is therefore dump/restore + schema adoption, not an SQLite import.

After restoring the intended legacy dump into a fresh target database:

```bash
python -m scripts.migration_preflight --adopt-existing --expected-users <count>
python -m scripts.db_verify --expected-users <count>
```

The preflight validates the complete `user` column set, important PostgreSQL types,
nullability, primary key, row count, and Alembic revision. It refuses to stamp an incompatible
legacy schema.

## Deployment operations

See [`docs/coolify-deployment.md`](docs/coolify-deployment.md) for the DEV-first migration,
GitHub environment setup, private GHCR bootstrap, PostgreSQL restore, cutover, and rollback
procedure.

The historical evidence and migration decisions are recorded in
[`docs/ACCENTSBOT_MIGRATION.md`](docs/ACCENTSBOT_MIGRATION.md).
