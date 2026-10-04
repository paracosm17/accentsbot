from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlsplit

from environs import Env
from sqlalchemy.engine import URL

_WEBHOOK_SECRET_RE = re.compile(r"^[A-Za-z0-9_-]{16,256}$")


@dataclass(frozen=True, slots=True)
class AppConfig:
    env: str
    log_level: str
    smoke_mode: bool
    notify_admins_on_startup: bool
    release_revision: str


@dataclass(frozen=True, slots=True)
class WebServerConfig:
    host: str
    port: int


@dataclass(frozen=True, slots=True)
class WebhookConfig:
    base_url: str | None
    path: str
    secret: str | None

    @property
    def url(self) -> str | None:
        if not self.base_url:
            return None
        return f"{self.base_url.rstrip('/')}{self.path}"


@dataclass(frozen=True, slots=True)
class DbConfig:
    url: str

    def construct_sqlalchemy_url(self) -> str:
        return normalize_database_url(self.url)


@dataclass(frozen=True, slots=True)
class TgBot:
    token: str | None
    admin_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class RedisConfig:
    enabled: bool
    url: str | None

    def dsn(self) -> str:
        if not self.url:
            raise ValueError("REDIS_URL is required when USE_REDIS=true")
        return self.url


@dataclass(frozen=True, slots=True)
class Config:
    app: AppConfig
    web: WebServerConfig
    webhook: WebhookConfig
    tg_bot: TgBot
    db: DbConfig
    redis: RedisConfig

    def validate_runtime(self) -> None:
        if not 1 <= self.web.port <= 65535:
            raise ValueError("PORT must be between 1 and 65535")
        if self.app.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR or CRITICAL")

        if self.redis.enabled and not self.redis.url:
            raise ValueError("REDIS_URL or legacy Redis variables are required when USE_REDIS=true")
        if self.redis.url and not self.redis.url.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL must use redis:// or rediss://")

        if self.app.smoke_mode:
            return

        if not self.tg_bot.token:
            raise ValueError("BOT_TOKEN is required when APP_SMOKE_MODE=false")
        if not self.webhook.base_url:
            raise ValueError("WEBHOOK_BASE_URL is required when APP_SMOKE_MODE=false")
        base = urlsplit(self.webhook.base_url)
        if (
            base.scheme != "https"
            or not base.netloc
            or base.path not in {"", "/"}
            or base.query
            or base.fragment
        ):
            raise ValueError(
                "WEBHOOK_BASE_URL must be an https:// origin without path/query/fragment"
            )
        if not self.webhook.secret:
            raise ValueError("WEBHOOK_SECRET is required when APP_SMOKE_MODE=false")
        if not _WEBHOOK_SECRET_RE.fullmatch(self.webhook.secret):
            raise ValueError(
                "WEBHOOK_SECRET must be 16-256 characters using only A-Z, a-z, 0-9, _ and -"
            )


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    if url.startswith("postgresql+asyncpg://"):
        return url
    raise ValueError("DATABASE_URL must use postgres://, postgresql:// or postgresql+asyncpg://")


def _load_env(path: str | Path | None) -> Env:
    env = Env()
    if path is not None and Path(path).is_file():
        env.read_env(str(path), override=False)
    return env


def _database_url(env: Env) -> str:
    modern = env.str("DATABASE_URL", default="").strip()
    if modern:
        return modern

    host = env.str("DB_HOST", default="").strip()
    password = env.str("POSTGRES_PASSWORD", default="")
    user = env.str("POSTGRES_USER", default="").strip()
    database = env.str("POSTGRES_DB", default="").strip()
    port = env.int("DB_PORT", default=5432)

    if not all((host, user, database)):
        raise ValueError(
            "DATABASE_URL is required; legacy DB_HOST/POSTGRES_USER/POSTGRES_DB fallback is incomplete"
        )

    return URL.create(
        drivername="postgresql+asyncpg",
        username=user,
        password=password,
        host=host,
        port=port,
        database=database,
    ).render_as_string(hide_password=False)


def load_database_config(path: str | Path | None = None) -> DbConfig:
    return DbConfig(url=_database_url(_load_env(path)))


def _redis_url(env: Env, enabled: bool) -> str | None:
    modern = env.str("REDIS_URL", default="").strip()
    if modern:
        return modern
    if not enabled:
        return None

    host = env.str("REDIS_HOST", default="").strip()
    port = env.int("REDIS_PORT", default=6379)
    database = env.int("REDIS_DB", default=0)
    password = env.str("REDIS_PASSWORD", default="")

    if not host:
        return None

    auth = f":{quote(password, safe='')}@" if password else ""
    return f"redis://{auth}{host}:{port}/{database}"


def _admin_ids(env: Env) -> tuple[int, ...]:
    raw = env.str("ADMIN_IDS", default="").strip() or env.str("ADMINS", default="").strip()
    if not raw:
        return ()
    return tuple(int(part.strip()) for part in raw.split(",") if part.strip())


def load_config(path: str | Path | None = None) -> Config:
    env = _load_env(path)
    smoke_mode = env.bool("APP_SMOKE_MODE", default=False)
    use_redis = env.bool("USE_REDIS", default=False)

    webhook_path = env.str("WEBHOOK_PATH", default="/telegram/webhook").strip()
    if not webhook_path.startswith("/"):
        webhook_path = f"/{webhook_path}"
    if webhook_path in {"/", "/healthz"} or "?" in webhook_path or "#" in webhook_path:
        raise ValueError(
            "WEBHOOK_PATH must be a non-root application path and must not collide with /healthz"
        )

    config = Config(
        app=AppConfig(
            env=env.str("APP_ENV", default="development").strip(),
            log_level=env.str("LOG_LEVEL", default="INFO").upper().strip(),
            smoke_mode=smoke_mode,
            notify_admins_on_startup=env.bool("NOTIFY_ADMINS_ON_STARTUP", default=False),
            release_revision=env.str("RELEASE_REVISION", default="unknown").strip() or "unknown",
        ),
        web=WebServerConfig(
            host=env.str("WEB_SERVER_HOST", default="0.0.0.0").strip(),
            port=env.int("PORT", default=8080),
        ),
        webhook=WebhookConfig(
            base_url=env.str("WEBHOOK_BASE_URL", default="").strip() or None,
            path=webhook_path,
            secret=env.str("WEBHOOK_SECRET", default="").strip() or None,
        ),
        tg_bot=TgBot(
            token=env.str("BOT_TOKEN", default="").strip() or None,
            admin_ids=_admin_ids(env),
        ),
        db=DbConfig(url=_database_url(env)),
        redis=RedisConfig(enabled=use_redis, url=_redis_url(env, use_redis)),
    )
    config.validate_runtime()
    return config
