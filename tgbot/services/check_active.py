import asyncio
import logging
from typing import Union

from aiogram import Bot
from aiogram import exceptions

from infrastructure.database.repo.requests import RequestsRepo


async def send_chat_action(
        bot: Bot,
        user_id: Union[int, str],
        repo: RequestsRepo
) -> bool:
    try:
        await bot.send_chat_action(
            user_id,
            "typing"
        )
        await repo.users.active_user(user_id, active=True)
    except exceptions.TelegramForbiddenError:
        logging.error(f"Target [ID:{user_id}]: got TelegramForbiddenError")
        await repo.users.active_user(user_id, active=False)
    except exceptions.TelegramRetryAfter as e:
        logging.error(
            f"Target [ID:{user_id}]: Flood limit is exceeded. Sleep {e.retry_after} seconds."
        )
        await asyncio.sleep(e.retry_after)
        return await send_chat_action(bot, user_id, repo)
    except exceptions.TelegramBadRequest as e:
        logging.error(f"Target [ID:{user_id}]: failed - {e.message}")
        await repo.users.active_user(user_id, active=False)
    except exceptions.TelegramAPIError as e:
        logging.error(f"Target [ID:{user_id}]: failed - {e.message}")
        await repo.users.active_user(user_id, active=False)
    else:
        logging.info(f"Target [ID:{user_id}]: success")
        return True
    return False


async def check_active_users(
        bot: Bot,
        users: list[Union[str, int]],
        repo: RequestsRepo
) -> int:
    count = 0
    try:
        for user_id in users:
            if await send_chat_action(bot, user_id, repo):
                count += 1
            await asyncio.sleep(
                0.05
            )
    finally:
        logging.info(f"{count} юзеров активно")

    return count
