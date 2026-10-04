import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from infrastructure.database.repo.requests import RequestsRepo
from tgbot.filters.admin import AdminFilter
from tgbot.services.check_active import check_active_users
from tgbot.services.tasks import spawn

logger = logging.getLogger(__name__)

admin_router = Router()
admin_router.message.filter(AdminFilter())


@admin_router.message(Command("ban"))
async def ban_user(message: Message, command: CommandObject, repo: RequestsRepo):
    arg = command.args
    if arg and arg.isdigit():
        user_id = int(arg)
        if user_id > 9_223_372_036_854_775_807:
            await message.reply("Слишком большой id.")
            return
        banned = await repo.users.ban_user(user_id)
        await message.reply("Успешно забанен." if banned else "В боте нет такого пользователя.")
        return
    await message.reply("Введите id пользователя. /ban some_id")


@admin_router.message(Command("bot"))
async def admin_stats(message: Message, repo: RequestsRepo):
    await message.reply(
        f"""Всего пользователей: {await repo.users.users_count()}
Из них активных: {await repo.users.users_count(only_active=True)}

Активность:
За день: {await repo.users.get_users_active_count_by_days(1)}
За неделю: {await repo.users.get_users_active_count_by_days(7)}
За месяц: {await repo.users.get_users_active_count_by_days(31)}
За год: {await repo.users.get_users_active_count_by_days(365)}

Новые пользователи:
За день: {await repo.users.get_users_created_count_by_days(1)}
За неделю: {await repo.users.get_users_created_count_by_days(7)}
За месяц: {await repo.users.get_users_created_count_by_days(31)}
За год: {await repo.users.get_users_created_count_by_days(365)}
"""
    )


async def _run_active_check(bot, chat_id: int, users: list[int], session_pool) -> None:
    async with session_pool() as session:
        repo = RequestsRepo(session)
        active_count = await check_active_users(bot=bot, users=users, repo=repo)
    await bot.send_message(
        chat_id,
        f"Активных пользователей: {active_count}\nВсего пользователей: {len(users)}",
    )


@admin_router.message(Command("checkactiveusers"))
async def checkactiveusers(message: Message, repo: RequestsRepo, session_pool):
    await message.reply("Начинаю проверку в фоне...")
    users_ids = list(await repo.users.get_all_users_ids())
    spawn(
        _run_active_check(message.bot, message.chat.id, users_ids, session_pool),
        name=f"check-active-{message.from_user.id}",
    )
    logger.info(
        "Active-user check queued by admin=%s users=%d", message.from_user.id, len(users_ids)
    )
