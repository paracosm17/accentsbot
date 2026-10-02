import asyncio
import logging
from collections.abc import Sequence

from aiogram import Bot, exceptions
from aiogram.types import InlineKeyboardMarkup

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


async def send_message(
    bot: Bot,
    user_id: int | str,
    text: str,
    disable_notification: bool = False,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    for attempt in range(MAX_RETRIES + 1):
        try:
            await bot.send_message(
                user_id,
                text,
                disable_notification=disable_notification,
                reply_markup=reply_markup,
            )
            return True
        except exceptions.TelegramForbiddenError:
            logger.info("Target [ID:%s] blocked the bot", user_id)
            return False
        except exceptions.TelegramRetryAfter as exc:
            if attempt >= MAX_RETRIES:
                logger.error("Target [ID:%s] exhausted flood retries", user_id)
                return False
            await asyncio.sleep(float(exc.retry_after) + 0.1)
        except exceptions.TelegramBadRequest as exc:
            logger.warning("Target [ID:%s] bad request: %s", user_id, exc.message)
            return False
        except exceptions.TelegramAPIError as exc:
            logger.warning("Target [ID:%s] Telegram API error: %s", user_id, exc.message)
            return False
    return False


async def broadcast(
    bot: Bot,
    users: Sequence[int | str],
    text: str,
    disable_notification: bool = False,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> int:
    count = 0
    for user_id in users:
        if await send_message(bot, user_id, text, disable_notification, reply_markup):
            count += 1
        await asyncio.sleep(0.05)
    logger.info("Broadcast complete: sent=%d requested=%d", count, len(users))
    return count


async def send_message_by_copy(
    bot: Bot,
    user_id: int | str,
    from_user_id: int,
    message_id: int,
    reply_markup: InlineKeyboardMarkup | None,
) -> bool:
    for attempt in range(MAX_RETRIES + 1):
        try:
            await bot.copy_message(
                user_id,
                from_user_id,
                message_id,
                reply_markup=reply_markup,
            )
            return True
        except exceptions.TelegramForbiddenError:
            logger.info("Target [ID:%s] blocked the bot", user_id)
            return False
        except exceptions.TelegramRetryAfter as exc:
            if attempt >= MAX_RETRIES:
                logger.error("Target [ID:%s] exhausted flood retries", user_id)
                return False
            await asyncio.sleep(float(exc.retry_after) + 0.1)
        except exceptions.TelegramBadRequest as exc:
            logger.warning("Target [ID:%s] bad request: %s", user_id, exc.message)
            return False
        except exceptions.TelegramAPIError as exc:
            logger.warning("Target [ID:%s] Telegram API error: %s", user_id, exc.message)
            return False
    return False


async def broadcast_by_copy(
    bot: Bot,
    users: Sequence[int | str],
    from_user_id: int,
    message_id: int,
    reply_markup: InlineKeyboardMarkup | None,
) -> int:
    count = 0
    for user_id in users:
        if await send_message_by_copy(bot, user_id, from_user_id, message_id, reply_markup):
            count += 1
        await asyncio.sleep(0.05)
    logger.info("Copy broadcast complete: sent=%d requested=%d", count, len(users))
    return count
