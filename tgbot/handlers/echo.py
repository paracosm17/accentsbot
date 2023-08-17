from aiogram import types, Router

echo_router = Router()


@echo_router.message()
async def bot_echo_all(message: types.Message):
    await message.answer("Я не знаю такой команды! Пиши /start")
