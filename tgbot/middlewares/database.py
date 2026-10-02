from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from infrastructure.database.models.users import User
from infrastructure.database.repo.requests import RequestsRepo


class DatabaseMiddleware(BaseMiddleware):
    def __init__(self, session_pool, engine):
        self.session_pool = session_pool
        self.engine = engine

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self.session_pool() as session:
            repo = RequestsRepo(session)
            from_user = getattr(event, "from_user", None)

            if from_user is not None and not from_user.is_bot:
                user: User = await repo.users.update_or_create_user(
                    user_id=from_user.id,
                    full_name=from_user.full_name,
                    language_code=from_user.language_code,
                    username=from_user.username,
                )

                if user.banned:
                    if isinstance(event, Message):
                        await event.answer("Вы заблокированы в боте.")
                    elif isinstance(event, CallbackQuery):
                        await event.answer("Вы заблокированы в боте.", show_alert=True)
                    return None

                data["user"] = user

            data["session"] = session
            data["session_pool"] = self.session_pool
            data["engine"] = self.engine
            data["repo"] = repo

            return await handler(event, data)
