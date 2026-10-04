PYTHON ?= .venv/bin/python
RUFF ?= .venv/bin/ruff
PYTHON_VERSION ?= 3.13.15

# Formatting is intentionally ratcheted over the code touched by the migration.
# compileall still covers the complete Python tree; legacy modules can be added to
# RUFF_TARGETS as they are changed without creating one giant behavior-neutral diff.
RUFF_TARGETS := \
	bot.py \
	infrastructure/accents/accent.py \
	infrastructure/database/models/base.py \
	infrastructure/database/models/users.py \
	infrastructure/database/repo/users.py \
	infrastructure/database/setup.py \
	infrastructure/migrations/env.py \
	tgbot/app.py \
	tgbot/config.py \
	tgbot/dialogs/broadcast/funcs.py \
	tgbot/handlers/admin.py \
	tgbot/middlewares/config.py \
	tgbot/middlewares/database.py \
	tgbot/services/broadcaster.py \
	tgbot/services/check_active.py \
	tgbot/services/tasks.py \
	tgbot/web.py \
	scripts \
	tests

.PHONY: setup format lint test check preflight verify-db run compose-up compose-down

setup:
	UV_LINK_MODE=copy uv venv --python $(PYTHON_VERSION)
	UV_LINK_MODE=copy uv pip install --python $(PYTHON) -r requirements-dev.txt

format:
	$(RUFF) check --fix $(RUFF_TARGETS)
	$(RUFF) format $(RUFF_TARGETS)

lint:
	$(RUFF) check $(RUFF_TARGETS)
	$(RUFF) format --check $(RUFF_TARGETS)

test:
	$(PYTHON) -m pytest

check:
	$(PYTHON) -m compileall -q bot.py infrastructure tgbot scripts tests
	$(RUFF) check $(RUFF_TARGETS)
	$(RUFF) format --check $(RUFF_TARGETS)
	$(PYTHON) -m pytest
	git diff --check

preflight:
	$(PYTHON) -m scripts.migration_preflight

verify-db:
	$(PYTHON) -m scripts.db_verify

run:
	$(PYTHON) -m bot

compose-up:
	docker compose -f compose.dev.yml up --build -d

compose-down:
	docker compose -f compose.dev.yml down
