from __future__ import annotations

import hmac
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiohttp import web
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tgbot.config import Config

logger = logging.getLogger(__name__)


def _base_payload(config: Config) -> dict[str, object]:
    return {
        "service": "accentsbot",
        "env": config.app.env,
        "release_revision": config.app.release_revision,
        "smoke_mode": config.app.smoke_mode,
        "transport": "smoke" if config.app.smoke_mode else "telegram-webhook",
    }


async def _check_database(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        # Checking the table (not merely SELECT 1) makes health fail closed if a
        # deployment points at an empty or incorrectly restored database.
        await connection.execute(text('SELECT user_id FROM "user" LIMIT 1'))


async def _check_redis(redis_client: Redis | None) -> None:
    if redis_client is not None:
        await redis_client.ping()


def create_web_app(
    *,
    config: Config,
    engine: AsyncEngine,
    redis_client: Redis | None,
    bot: Bot | None,
    dispatcher: Dispatcher | None,
) -> web.Application:
    app = web.Application(client_max_size=1024 * 1024)

    async def index(_: web.Request) -> web.Response:
        return web.json_response({"status": "ok", **_base_payload(config)})

    async def healthz(_: web.Request) -> web.Response:
        checks: dict[str, str] = {}
        try:
            await _check_database(engine)
            checks["postgresql"] = "ok"
            await _check_redis(redis_client)
            if redis_client is not None:
                checks["redis"] = "ok"
        except Exception as exc:  # health endpoint must fail closed
            logger.warning("Health check failed: %s", exc)
            return web.json_response(
                {"status": "error", "checks": checks, **_base_payload(config)},
                status=503,
            )

        return web.json_response({"status": "ok", "checks": checks, **_base_payload(config)})

    async def telegram_webhook(request: web.Request) -> web.Response:
        if config.app.smoke_mode or bot is None or dispatcher is None:
            return web.json_response({"status": "smoke-mode"}, status=503)

        supplied_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        expected_secret = config.webhook.secret or ""
        if not hmac.compare_digest(supplied_secret, expected_secret):
            return web.json_response({"error": "unauthorized"}, status=401)

        try:
            payload = await request.json()
            update = Update.model_validate(payload, context={"bot": bot})
            await dispatcher.feed_update(bot, update)
        except Exception:
            logger.exception("Telegram webhook update failed")
            return web.json_response({"error": "update-processing-failed"}, status=500)

        return web.json_response({"ok": True})

    app.router.add_get("/", index)
    app.router.add_get("/healthz", healthz)
    app.router.add_post(config.webhook.path, telegram_webhook)
    return app
