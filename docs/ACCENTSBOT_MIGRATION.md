# accentsbot migration journal

> AI-friendly factual migration log.
> Secrets are intentionally excluded.

## Status

Current phase: legacy audit + Git reconciliation.

Production cutover has NOT happened.

---

## 2026-10-01 — Legacy production audit

### Legacy location

```text
host: server
project: /opt/accentsbot
runtime: Docker Compose
container: accents_bot
command: python3 -m bot
Python: 3.11.15
```

Docker Compose metadata confirmed:

```text
compose project: accentsbot
working directory: /opt/accentsbot
container working directory: /usr/src/app/accents_bot
bind mount:
/opt/accentsbot -> /usr/src/app/accents_bot
```

No inspected project files were newer than the currently running bot process.

Selected host/container SHA256 comparisons matched.

Conclusion:

```text
/opt/accentsbot = legacy production source of truth
```

### Legacy services

```text
accents_bot
accents_bot_postgres
accents_bot_redis
```

Database:

```text
PostgreSQL: 14.11
database: accents_bot_db
table: public.user
rows: 19642
database size: ~11 MB
```

Redis persistence:

```text
/opt/accentsbot/cache -> /data
```

### PostgreSQL recovery warning

Legacy PostgreSQL has recovery-era Docker volume configuration.

Important external recovery volume:

```text
22845ff40998408bc91ff1076a7709abb8b6410c9fb47a0773104c456948d341
-> /var/lib/postgresql/data
```

Do NOT run:

```text
docker compose down -v
docker volume prune
```

until migration and rollback window are complete.

### Fresh production DB backup

```text
/opt/backups/postgres/accentsbot/accentsbot-pre-migration-20261001-100647.dump
SHA256:
b6a9f3d1312e9f935562d7f19ba5679565bbb1f504e96e58887bb1366218a1cf
```

pg_restore --list validation:

```text
OK
```

### Production source archive

```text
/opt/bot.zip
SHA256:
d1e3ab3481dae4aeede5d994450cb0d3c004d1d4e0b7fb408fa015830224e27e
```

Local WSL archive SHA256 matched legacy server.

---

## 2026-10-01 — Git reconciliation started

GitHub repository:

```text
paracosm17/accentsbot
```

Fresh working clone:

```text
/mnt/c/Users/admin/code/accentsbot
```

Default branch:

```text
master
```

GitHub baseline HEAD:

```text
32f8854928eee263b38627e32c8a5e36d90f7738
```

Exact extracted legacy production snapshot:

```text
/home/user/code/accentsbot-migration/legacy/accentsbot
```

Comparison report:

```text
/home/user/code/accentsbot-migration/github-vs-production.txt
```

No reconciliation commit or push has been performed yet.

---

## 2026-10-01 — Git reconciliation result

Legacy production and GitHub were compared before modifying the repository.

Original GitHub state:

```text
branch: master
HEAD: 32f8854928eee263b38627e32c8a5e36d90f7738
last commit date: 2023-08-20
```

Comparison with production snapshot:

```text
production files considered: 71
GitHub files considered: 45
identical: 17
different: 25
production-only: 29
GitHub-only: 3
```

GitHub-only obsolete files removed by the production baseline:

```text
infrastructure/ad/__init__.py
infrastructure/ad/ad_api.py
tgbot/middlewares/ad.py
```

Production runtime/private data intentionally excluded from Git:

```text
.env
database.db
dump_23.03.2026.sql
cache/
__pycache__/
*.pyc
```

Legacy server-specific Compose/recovery metadata is intentionally retained in
this historical baseline and will be replaced during the Coolify modernization
phase.

Baseline branch:

```text
migration/legacy-production-baseline
```

No application modernization is included in this baseline commit.

### Recovery note

The first baseline automation script was truncated while being copied from chat
and stopped at the beginning of migration-journal generation.

At that point:

```text
no git add
no commit
no push
no PR
```

Recovery procedure:

```text
1. archive partial working tree;
2. verify origin/master is still the audited commit;
3. reset the temporary branch/worktree;
4. regenerate the production baseline from the audited snapshot;
5. validate and commit normally.
```

### Security-only baseline deviation

During the pre-commit secret scan, `migrate_db.py` was found to contain
hardcoded legacy database credentials.

The scan stopped the workflow before any commit or push.

For the Git baseline, that file is intentionally the only production-source
file whose content differs from the audited legacy snapshot. The hardcoded
connection values were replaced with runtime environment lookups:

```text
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_DB
DB_HOST
DB_PORT
```

This is a security redaction, not an application/infrastructure modernization.

Validation policy for this baseline:

```text
all eligible production source files must match SHA256
except:
migrate_db.py   # security-only credential redaction

docs/ACCENTSBOT_MIGRATION.md is Git-only migration documentation
```

### Legacy CRLF / whitespace note

The historical production snapshot contains CRLF line endings in several
legacy source files.

A full `git diff --cached --check` therefore reports `trailing whitespace`
for those unchanged production bytes because the CR character is visible to
Git's whitespace checker.

For this historical baseline the files are intentionally NOT normalized:
preserving the audited production bytes is more important than formatting
legacy source during reconciliation.

The baseline uses:

```text
git config core.autocrlf false
```

and validates the staged Git index byte-for-byte against the production
snapshot.

Whitespace/line-ending normalization belongs to the later modernization
commit together with Ruff/formatting rules.

---

## 2026-10-01 — Git history cleanup before main/dev bootstrap

The legacy GitHub history contained ancestry inherited from an old Telegram bot
template. Those ancestor commits were not desired as part of the accentsbot
project history.

The previously validated production reconciliation commit was:

```text
b4080f06c8eb1043a319c650a8ca069b024347b1
```

Its code changes were reapplied onto a deliberately rebuilt clean history.

The old GitHub master tip before the rewrite was:

```text
32f8854928eee263b38627e32c8a5e36d90f7738
```

The visible historical sequence was recreated as four commits:

```text
from server -> 05f39213d43c03ed1aedc211941d99c2e4d92137
test        -> 87869bea49e9d8cd51e2d777956f0024450bf468
test        -> 53bfac8b5848b4b181445ff9fbcc9ec595f799b4
test        -> 10313fef982fcfe887ec0ae63775d96f7a75be66
```

Their commit IDs changed because Git commit hashes include the parent commit.
Removing unwanted ancestors while preserving the exact old SHA IDs is not
possible.

The recreated four-commit tip was verified to have the exact same Git tree as
the previous `master` tip before the production baseline was applied.

The obsolete PR #1 / `migration/legacy-production-baseline` path was closed and
is not used for the final branch model.
