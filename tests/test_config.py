from __future__ import annotations

import os

import pytest

from tgbot.config import load_config, normalize_database_url

CONFIG_KEYS = {
    "APP_ENV",
    "LOG_LEVEL",
    "APP_SMOKE_MODE",
    "NOTIFY_ADMINS_ON_STARTUP",
    "RELEASE_REVISION",
    "WEB_SERVER_HOST",
    "PORT",
    "WEBHOOK_BASE_URL",
    "WEBHOOK_PATH",
    "WEBHOOK_SECRET",
    "BOT_TOKEN",
    "ADMIN_IDS",
    "ADMINS",
    "DATABASE_URL",
    "DB_HOST",
    "DB_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "USE_REDIS",
    "REDIS_URL",
    "REDIS_HOST",
    "REDIS_PORT",
    "REDIS_DB",
    "REDIS_PASSWORD",
}


def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in CONFIG_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_smoke_config_needs_no_telegram_token(monkeypatch: pytest.MonkeyPatch) -> None:
    clean_env(monkeypatch)
    monkeypatch.setenv("APP_SMOKE_MODE", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db:5432/app")

    config = load_config()

    assert config.app.smoke_mode is True
    assert config.tg_bot.token is None
    assert config.db.construct_sqlalchemy_url() == "postgresql+asyncpg://user:pass@db:5432/app"


def test_live_config_requires_https_webhook(monkeypatch: pytest.MonkeyPatch) -> None:
    clean_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db/app")
    monkeypatch.setenv("BOT_TOKEN", "dummy-bot-token-for-config-test")
    monkeypatch.setenv("WEBHOOK_BASE_URL", "http://example.test")
    monkeypatch.setenv("WEBHOOK_SECRET", "secret")

    with pytest.raises(ValueError, match="https://"):
        load_config()


def test_legacy_database_and_redis_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    clean_env(monkeypatch)
    monkeypatch.setenv("APP_SMOKE_MODE", "true")
    monkeypatch.setenv("DB_HOST", "postgres")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "accents")
    monkeypatch.setenv("POSTGRES_USER", "legacy")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss word")
    monkeypatch.setenv("USE_REDIS", "true")
    monkeypatch.setenv("REDIS_HOST", "redis")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.setenv("REDIS_DB", "2")
    monkeypatch.setenv("REDIS_PASSWORD", "p@ss word")
    monkeypatch.setenv("ADMINS", "1,2")

    config = load_config()

    assert config.tg_bot.admin_ids == (1, 2)
    assert config.db.construct_sqlalchemy_url().startswith("postgresql+asyncpg://legacy:")
    assert "%40" in config.db.construct_sqlalchemy_url()
    assert config.redis.dsn() == "redis://:p%40ss%20word@redis:6379/2"


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("postgres://u:p@db/app", "postgresql+asyncpg://u:p@db/app"),
        ("postgresql://u:p@db/app", "postgresql+asyncpg://u:p@db/app"),
        ("postgresql+asyncpg://u:p@db/app", "postgresql+asyncpg://u:p@db/app"),
    ],
)
def test_normalize_database_url(raw: str, normalized: str) -> None:
    assert normalize_database_url(raw) == normalized


def test_environment_does_not_need_dotenv_file(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    clean_env(monkeypatch)
    monkeypatch.setenv("APP_SMOKE_MODE", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db/app")
    missing = tmp_path / ".env"
    assert not os.path.exists(missing)
    assert load_config(missing).app.smoke_mode is True


def test_live_config_rejects_short_webhook_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    clean_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db/app")
    monkeypatch.setenv("BOT_TOKEN", "dummy-bot-token-for-config-test")
    monkeypatch.setenv("WEBHOOK_BASE_URL", "https://example.test")
    monkeypatch.setenv("WEBHOOK_SECRET", "too-short")

    with pytest.raises(ValueError, match="16-256"):
        load_config()


def test_webhook_path_rejects_query(monkeypatch: pytest.MonkeyPatch) -> None:
    clean_env(monkeypatch)
    monkeypatch.setenv("APP_SMOKE_MODE", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db/app")
    monkeypatch.setenv("WEBHOOK_PATH", "/telegram/webhook?bad=1")

    with pytest.raises(ValueError, match="application path"):
        load_config()


def test_webhook_base_url_rejects_path(monkeypatch: pytest.MonkeyPatch) -> None:
    clean_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db/app")
    monkeypatch.setenv("BOT_TOKEN", "dummy-bot-token-for-config-test")
    monkeypatch.setenv("WEBHOOK_BASE_URL", "https://example.test/base")
    monkeypatch.setenv("WEBHOOK_SECRET", "0123456789abcdef")

    with pytest.raises(ValueError, match="origin"):
        load_config()
