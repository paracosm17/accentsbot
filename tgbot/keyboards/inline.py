from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.keyboard import CallbackData
from aiogram.types import InlineKeyboardButton

from infrastructure.accents import Word


class MyCallback(CallbackData, prefix="w"):
    id: int
    ans: str


async def get_word_keyboard(word: Word) -> InlineKeyboardBuilder:
    words_keyboard = InlineKeyboardBuilder()
    for variant in word.variants:
        words_keyboard.add(InlineKeyboardButton(text=variant,
                           callback_data=MyCallback(id=word.id, ans=variant).pack()))
    words_keyboard.adjust(1)
    return words_keyboard
