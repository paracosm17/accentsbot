from aiogram import Router
from aiogram.filters.command import Command
from aiogram.types import Message

from tgbot.filters.admin import AdminFilter
from infrastructure.database.repo.requests import RequestsRepo

admin_router = Router()
admin_router.message.filter(AdminFilter())


@admin_router.message(Command("stats"))
async def stats(message: Message, repo: RequestsRepo):
    users = await repo.users.get_biggest_words()
    msg = ""

    for index, user in enumerate(users):
        if user.username:
            msg += f"{index+1}. @{user.username} - {user.words}\n"
            continue
        msg += f'{index+1}. <a href="tg://user?id={user.telegram_id}">{user.first_name}</a> - {user.words}\n'

    count_users = await repo.users.users_count()
    msg += f"\nВсего пользователей: {count_users}"

    users_today = await repo.users.get_users_today()
    msg += f"\nНовых пользователей за сегодня: {users_today}"

    await message.answer(msg)
