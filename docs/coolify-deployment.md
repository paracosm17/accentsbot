# accentsbot — Coolify deployment and migration runbook

This runbook is deliberately DEV-first. Production must not be created/cut over until the
same immutable application path and PostgreSQL restore procedure have been validated in DEV.

## 1. Safety invariants

```text
DEV first; production later.
Runtime secrets live in Coolify, not Git.
CI credentials live in GitHub, not the image.
Coolify management API stays loopback-only and is reached by restricted SSH forwarding.
Deploy exact GHCR digest, not a mutable branch tag.
APP_SMOKE_MODE=true before Telegram side effects.
PostgreSQL volume is not a backup.
Do not delete the legacy server/volumes during the rollback window.
```

Legacy PostgreSQL recovery volume that must not be pruned during migration:

```text
22845ff40998408bc91ff1076a7709abb8b6410c9fb47a0773104c456948d341
-> /var/lib/postgresql/data
```

Never run `docker compose down -v` or `docker volume prune` on the old host until the rollback
window is explicitly closed.

## 2. CI/CD bootstrap

Repository model:

```text
dev  -> GitHub Actions -> GHCR -> Coolify DEV
main -> GitHub Actions -> GHCR -> Coolify production
```

The server-level restricted CI transport is reused; do not create another Linux CI user/key
for this application.

On WSL/workstation, configure the repository-level transport and Coolify API credentials:

```bash
./ops/github-common.sh
```

The script validates the existing CI private-key fingerprint and configures generic repository
variables:

```text
DEPLOY_HOST
DEPLOY_SSH_USER
DEPLOY_SSH_KEY_FINGERPRINT
SSH_KNOWN_HOSTS
DEPLOY_DEV_ENABLED=false
DEPLOY_PRODUCTION_ENABLED=false
```

and repository secrets:

```text
DEPLOY_SSH_KEY
COOLIFY_API_TOKEN_RW
COOLIFY_API_TOKEN_DEPLOY
```

The Coolify API is not exposed to GitHub directly. Actions creates an SSH tunnel to
`127.0.0.1:8000` on the VPS and uses the runner-side endpoint `127.0.0.1:18000`.

## 3. Build the first DEV release

With deploy switches still false, push/merge the modernization into `dev` and wait for the
workflow. It must complete:

```text
quality
PostgreSQL 18 preflight
immutable image publish
exact-digest smoke verification
```

Read the immutable image from the Actions Summary:

```text
ghcr.io/paracosm17/accentsbot@sha256:<digest>
```

Use that exact digest for the first manual Coolify bootstrap.

## 4. Coolify DEV resources

Create/use a project with environment `dev` and three resources:

```text
accentsbot-db-dev      PostgreSQL 18
accentsbot-redis-dev   Redis
accentsbot-dev         Docker Image application
```

PostgreSQL:

```text
version: 18
public access: OFF
DEV-only database/user/password
```

Redis:

```text
public access: OFF
DEV-only password
```

Application:

```text
image: ghcr.io/paracosm17/accentsbot
image tag/hash: sha256-<digest from Actions Summary>
internal/exposed port: 8080
host port mapping: EMPTY
replicas: 1
domain: https://<DEV-domain>
```

The domain must include `https://` from the beginning.

For a private GHCR package, Docker credentials must belong to the Coolify server user (`ops`),
not only to root. If the schedulekco migration already configured `/home/ops/.docker/config.json`,
verify it before creating another credential:

```bash
ssh ops@31.59.174.254
ls -ld ~/.docker ~/.docker/config.json
docker pull 'ghcr.io/paracosm17/accentsbot@sha256:<digest>'
```

If login is missing, log in as `ops` without sudo using a GitHub token with `read:packages`.

## 5. DEV runtime environment

Start with Telegram side effects disabled:

```dotenv
APP_ENV=dev
LOG_LEVEL=INFO
APP_SMOKE_MODE=true
NOTIFY_ADMINS_ON_STARTUP=false

DATABASE_URL=postgresql://<DEV_USER>:<URL_ENCODED_PASSWORD>@<DEV_DB_INTERNAL_HOST>:5432/<DEV_DB>

USE_REDIS=true
REDIS_URL=redis://:<URL_ENCODED_PASSWORD>@<DEV_REDIS_INTERNAL_HOST>:6379/0

WEB_SERVER_HOST=0.0.0.0
PORT=8080

# Supply these before live DEV, but smoke mode does not use Telegram.
BOT_TOKEN=<SEPARATE_DEV_BOT_TOKEN>
ADMIN_IDS=<comma-separated-admin-ids>
WEBHOOK_BASE_URL=https://<DEV-domain>
WEBHOOK_PATH=/telegram/webhook
WEBHOOK_SECRET=<16-256-char-random-secret>
```

All values are runtime-only/buildtime-off in Coolify.

The legacy environment inventory was:

```text
ADMINS
BOT_NAME
BOT_TOKEN
DB_HOST
DB_PORT
POSTGRES_DB
POSTGRES_PASSWORD
POSTGRES_USER
REDIS_DB
REDIS_HOST
REDIS_PASSWORD
REDIS_PORT
USE_REDIS
```

`BOT_NAME` is no longer a runtime contract. The remaining old names have direct modern
replacements or compatibility fallbacks.

## 6. DEV database restore rehearsal

The audited source is PostgreSQL 14.11. A verified custom-format snapshot already exists on
the old host, but DEV should use the snapshot selected for the rehearsal and record its hash.

Current audited snapshot evidence:

```text
/opt/backups/postgres/accentsbot/accentsbot-pre-migration-20261001-100647.dump
SHA256: b6a9f3d1312e9f935562d7f19ba5679565bbb1f504e96e58887bb1366218a1cf
user rows at audit: 19642
```

Transfer a copy to the new VPS and verify SHA256 before restore. Keep the source dump immutable.

Before touching the target database, create a target rollback dump even if it is expected to be
empty:

```bash
DB_CONTAINER='<coolify-dev-postgres-container>'
TARGET_BACKUP="/tmp/accentsbot-dev-before-restore-$(date +%Y%m%d-%H%M%S).dump"

docker exec "$DB_CONTAINER" sh -lc \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl' \
  > "$TARGET_BACKUP"

docker exec -i "$DB_CONTAINER" pg_restore --list < "$TARGET_BACKUP" >/dev/null
sha256sum "$TARGET_BACKUP"
```

Fail closed unless the target public schema is empty before the first restore:

```bash
docker exec "$DB_CONTAINER" sh -lc \
  'psql -X -A -t -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
   "SELECT count(*) FROM pg_tables WHERE schemaname = '\''public'\'';"'
```

Restore the custom dump with PostgreSQL 18 `pg_restore`:

```bash
DUMP='/tmp/accentsbot-dev-source.dump'
docker exec -i "$DB_CONTAINER" sh -lc \
  'exec pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl --exit-on-error' \
  < "$DUMP"
```

Do not use the old SQLite `database.db`; it is historical residue and is not the production
source of truth.

## 7. Adopt restored schema with Alembic

After the legacy table is restored, deploy/start the DEV application using the exact image and
`APP_SMOKE_MODE=true`. Runtime startup only verifies schema availability; it does not silently
run DDL.

Find the current app container from the Coolify application UUID, then run:

```bash
APP_CONTAINER='<current-dev-app-container>'

docker exec "$APP_CONTAINER" \
  python -m scripts.migration_preflight --adopt-existing --expected-users 19642

docker exec "$APP_CONTAINER" \
  python -m scripts.db_verify --expected-users 19642
```

The adoption command verifies exact columns, PostgreSQL type/nullability contract, primary key,
row count, stamps the compatible legacy schema at Alembic head, and proves a second upgrade is
idempotent.

Smoke verification:

```bash
curl -fsS 'https://<DEV-domain>/healthz'
curl -fsS 'https://<DEV-domain>/'
```

Expected health contains:

```json
{"status":"ok","transport":"smoke"}
```

and the `release_revision` must match the Git commit for the deployed digest.

Redis is transient FSM state; legacy Redis data is not migrated as durable application data.

## 8. Enable live DEV Telegram webhook

Only after DB validation:

1. confirm DEV uses a Telegram token different from production;
2. set `APP_SMOKE_MODE=false`;
3. keep `NOTIFY_ADMINS_ON_STARTUP=false` for the first live deployment;
4. redeploy the same validated immutable digest.

Verify:

```text
/healthz -> 200
/ -> transport=telegram-webhook
Telegram getWebhookInfo URL -> https://<DEV-domain>/telegram/webhook
pending_update_count -> acceptable/near zero
last_error_message -> empty
```

Exercise user flows manually:

```text
/start
accent task
paronym task
/count
/top
admin /bot
admin broadcast dialog (small DEV recipient set only)
```

Verify an existing migrated user keeps their historical `words` count.

## 9. Bind GitHub DEV and enable DEV CD

Configure the DEV GitHub Environment once:

```bash
./ops/github-env.sh dev '<DEV_COOLIFY_APP_UUID>' 'https://<DEV-domain>'
```

Only after the live DEV checks pass:

```bash
./ops/enable-deploy.sh dev true
```

Keep production disabled:

```bash
./ops/enable-deploy.sh production false
```

Push a harmless DEV change and prove the complete automatic path:

```text
quality -> DB preflight -> publish -> exact digest smoke -> restricted-SSH Coolify deploy -> public revision check
```

## 10. Promotion to main

Do not promote before DEV is validated. The helper requires an explicit acknowledgement:

```bash
DEV_VALIDATED=YES ./ops/promote-dev.sh
```

This creates `dev -> main`, waits for required checks, and merges. `main` then publishes the
production candidate image, but production deployment remains disabled.

## 11. Production bootstrap and cutover

Create separate production PostgreSQL/Redis/application resources. Never reuse DEV database or
Redis volumes. Configure:

```text
APP_ENV=production
APP_SMOKE_MODE=true
production DATABASE_URL
production REDIS_URL
production BOT_TOKEN
production HTTPS WEBHOOK_BASE_URL
production WEBHOOK_SECRET
```

Bind the production GitHub Environment, but do not enable production CD yet:

```bash
./ops/github-env.sh production '<PROD_COOLIFY_APP_UUID>' 'https://<PROD-domain>'
./ops/enable-deploy.sh production false
```

Bootstrap the exact `main` digest manually in smoke mode and verify connectivity.

### Final data cutover

The first audit dump is a rollback/rehearsal artifact, not the final production cutover copy.
To avoid losing writes made after a live snapshot, use a short controlled write outage:

```text
1. Keep new production in APP_SMOKE_MODE=true.
2. Stop ONLY the legacy accents_bot application container; keep old PostgreSQL running.
3. Record the final legacy user count.
4. Create a fresh custom pg_dump from old PostgreSQL and validate pg_restore --list.
5. SHA256 the final dump and transfer it to the new VPS.
6. Back up the new target DB before restore.
7. Restore the final dump into the production PostgreSQL 18 target.
8. Run migration_preflight --adopt-existing --expected-users <FINAL_COUNT>.
9. Run db_verify --expected-users <FINAL_COUNT>.
10. Verify smoke /healthz and release_revision.
11. Set APP_SMOKE_MODE=false and redeploy the same immutable digest.
12. Verify Telegram webhook + representative bot flows.
13. Only now enable DEPLOY_PRODUCTION_ENABLED=true.
```

Do not delete the old database/container/volume after cutover. Keep them for the agreed rollback
window.

## 12. Rollback boundary

CI automatic rollback only restores the previous **container image digest**. It cannot undo:

```text
PostgreSQL schema/data changes
Redis state
Telegram side effects
external messages already sent
```

Before Telegram cutover, rollback is simply keeping/restarting the old polling service.
After a webhook has been registered, rolling back to the old polling bot also requires removing
the Telegram webhook without dropping pending updates, then starting the old bot. Perform that
as an explicit incident action, not as an automatic CI fallback.

If a deployment outcome is unknown, do not start a second deployment. Inspect Coolify first.
