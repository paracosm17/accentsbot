import asyncio
import logging
from collections.abc import Sequence

from aiogram import Bot, exceptions

from infrastructure.database.repo.requests import RequestsRepo

logger = logging.getLogger(__name__)
MAX_RETRIES = 3


async def send_chat_action(bot: Bot, user_id: int | str, repo: RequestsRepo) -> bool:
    for attempt in range(MAX_RETRIES + 1):
        try:
            await bot.send_chat_action(user_id, "typing")
            await repo.users.active_user(int(user_id), active=True)
            return True
        except exceptions.TelegramForbiddenError:
            await repo.users.active_user(int(user_id), active=False)
            return False
        except exceptions.TelegramRetryAfter as exc:
            if attempt >= MAX_RETRIES:
                logger.error("Target [ID:%s] exhausted flood retries", user_id)
                return False
            await asyncio.sleep(float(exc.retry_after) + 0.1)
        except (exceptions.TelegramBadRequest, exceptions.TelegramAPIError) as exc:
            logger.warning("Target [ID:%s] activity check failed: %s", user_id, exc)
            await repo.users.active_user(int(user_id), active=False)
            return False
    return False


async def check_active_users(
    bot: Bot,
    users: Sequence[int | str],
    repo: RequestsRepo,
) -> int:
    count = 0
    for user_id in users:
        if await send_chat_action(bot, user_id, repo):
            count += 1
        await asyncio.sleep(0.05)
    logger.info("Activity check complete: active=%d requested=%d", count, len(users))
    return count
