from __future__ import annotations

import asyncio
import logging
import signal

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import DefaultKeyBuilder, RedisStorage
from aiogram_dialog import setup_dialogs
from aiohttp import web
from redis.asyncio import Redis

from infrastructure.database.setup import (
    create_postgres_engine,
    create_session_pool,
    verify_runtime_schema,
)
from tgbot.config import Config, load_config
from tgbot.dialogs.broadcast import broadcast_dialogs
from tgbot.dialogs.broadcast.funcs import broadcast_router
from tgbot.filters.admin import AdminFilter
from tgbot.handlers import routers_list
from tgbot.middlewares.config import ConfigMiddleware
from tgbot.middlewares.database import DatabaseMiddleware
from tgbot.services import broadcaster
from tgbot.services.tasks import drain_background_tasks
from tgbot.web import create_web_app

logger = logging.getLogger(__name__)


def setup_logging(config: Config) -> None:
    level = getattr(logging, config.app.log_level, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )


def get_storage(config: Config) -> BaseStorage:
    if config.redis.enabled:
        return RedisStorage.from_url(
            config.redis.dsn(),
            key_builder=DefaultKeyBuilder(with_bot_id=True, with_destiny=True),
        )
    return MemoryStorage()


def register_global_middlewares(
    dispatcher: Dispatcher,
    config: Config,
    session_pool,
    engine,
) -> None:
    middlewares = [
        ConfigMiddleware(config),
        DatabaseMiddleware(session_pool, engine),
    ]

    for middleware in middlewares:
        dispatcher.message.outer_middleware(middleware)
        dispatcher.chat_member.outer_middleware(middleware)
        dispatcher.my_chat_member.outer_middleware(middleware)
        dispatcher.callback_query.outer_middleware(middleware)


def create_dispatcher(config: Config, session_pool, engine) -> tuple[Dispatcher, BaseStorage]:
    storage = get_storage(config)
    dispatcher = Dispatcher(storage=storage)

    broadcast_router.message.filter(AdminFilter())
    dispatcher.include_routers(broadcast_router, *broadcast_dialogs())
    setup_dialogs(dispatcher)
    dispatcher.include_routers(*routers_list)
    register_global_middlewares(dispatcher, config, session_pool, engine)
    return dispatcher, storage


async def _notify_admins(bot: Bot, config: Config) -> None:
    if not config.app.notify_admins_on_startup or not config.tg_bot.admin_ids:
        return
    try:
        await broadcaster.broadcast(bot, config.tg_bot.admin_ids, "Бот запущен")
    except Exception:
        logger.exception("Failed to send startup notification")


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:  # pragma: no cover - Windows only
            pass


async def run(config: Config | None = None) -> None:
    config = config or load_config()
    setup_logging(config)

    engine = create_postgres_engine(config.db)
    session_pool = create_session_pool(engine)
    redis_client: Redis | None = None
    bot: Bot | None = None
    dispatcher: Dispatcher | None = None
    storage: BaseStorage | None = None
    runner: web.AppRunner | None = None
    dispatcher_started = False

    try:
        # Schema changes are intentionally NOT performed during application start.
        # Deployment/migration tooling owns Alembic. Runtime only verifies readiness.
        await verify_runtime_schema(engine)

        if config.redis.enabled:
            redis_client = Redis.from_url(config.redis.dsn(), decode_responses=True)
            await redis_client.ping()

        if not config.app.smoke_mode:
            bot = Bot(
                token=config.tg_bot.token or "",
                default=DefaultBotProperties(parse_mode="HTML"),
            )
            dispatcher, storage = create_dispatcher(config, session_pool, engine)
            await dispatcher.emit_startup(bot=bot)
            dispatcher_started = True

        app = create_web_app(
            config=config,
            engine=engine,
            redis_client=redis_client,
            bot=bot,
            dispatcher=dispatcher,
        )
        runner = web.AppRunner(app, access_log=logger)
        await runner.setup()
        site = web.TCPSite(runner, host=config.web.host, port=config.web.port)
        await site.start()

        logger.info(
            "accentsbot started env=%s smoke=%s release=%s listen=%s:%s",
            config.app.env,
            config.app.smoke_mode,
            config.app.release_revision,
            config.web.host,
            config.web.port,
        )

        if bot is not None and dispatcher is not None:
            await bot.set_webhook(
                url=config.webhook.url or "",
                secret_token=config.webhook.secret,
                allowed_updates=dispatcher.resolve_used_update_types(),
                drop_pending_updates=False,
            )
            await _notify_admins(bot, config)
            logger.info("Telegram webhook registered: %s", config.webhook.url)

        stop_event = asyncio.Event()
        _install_signal_handlers(stop_event)
        await stop_event.wait()
    finally:
        if runner is not None:
            await runner.cleanup()
        await drain_background_tasks()
        if dispatcher is not None and dispatcher_started and bot is not None:
            try:
                await dispatcher.emit_shutdown(bot=bot)
            except Exception:
                logger.exception("Dispatcher shutdown hook failed")
        if storage is not None:
            await storage.close()
        if bot is not None:
            await bot.session.close()
        if redis_client is not None:
            await redis_client.aclose()
        await engine.dispose()
        logger.info("accentsbot stopped")
