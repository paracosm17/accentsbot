from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.types import Update

from infrastructure.ad import Bap


class AdMiddleware(BaseMiddleware):
    def __init__(self, api_key: str):
        self._bap = Bap(api_key)

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            update: Update,
            data: Dict[str, Any]
    ) -> Any:
        need_update = await self._bap.handle_update(update.model_dump(by_alias=True))

        if need_update:
            return await handler(update, data)
        return
