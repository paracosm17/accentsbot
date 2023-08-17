from aiogram import Router, F
from aiogram.filters.command import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.markdown import hcode

from infrastructure.database.repo.requests import RequestsRepo
from infrastructure.accents import Word, Accenter
from tgbot.keyboards.inline import get_word_keyboard, MyCallback


router = Router()


@router.message(Command("start"))
async def user_start(message: Message):
    k = await get_word_keyboard(Word())
    await message.answer("Выберите правильный вариант", reply_markup=k.as_markup())


@router.message(Command("help"))
async def user_help(message: Message):
    await message.reply("Бот для тренировки ударений на ЕГЭ по русскому. Пиши /start.\n"
                        "Узнать свою статистику: /count\n"
                        "Все слова: /words\n"
                        "Топ: /top")


@router.message(Command("words"))
async def user_words(message: Message):
    msg = ", ".join(Word().get_all_words())
    await message.answer(msg)


@router.message(Command("top"))
async def user_words(message: Message, repo: RequestsRepo):
    users = await repo.users.get_biggest_words()
    msg = "Топ пользователей:\n\n"

    for index, user in enumerate(users):
        msg += f'{index+1}. {user.first_name} - {user.words}\n'

    await message.answer(msg)


@router.message(Command("count"))
async def user_words(message: Message, repo: RequestsRepo):
    words = await repo.users.get_words_count_by_id(message.from_user.id)
    await message.reply(f"Решено заданий: {words}")


@router.callback_query(MyCallback.filter())
async def word(call: CallbackQuery, callback_data: MyCallback, repo: RequestsRepo):
    current_word = Word(callback_data.id)
    if callback_data.ans == current_word.right:
        await repo.users.add_word(call.from_user.id)
        await call.message.edit_text(f"Верно! <b>{current_word.right}</b>")
        k = await get_word_keyboard(Word())
        await call.message.answer("Выберите правильный вариант", reply_markup=k.as_markup())
    else:
        await call.answer("Неверно! Попробуй ещё раз", show_alert=True)


@router.message(F.text, F.not_contains("/"))
async def make_accent(message: Message):
    await message.answer(hcode(Accenter(message.text).result()))
