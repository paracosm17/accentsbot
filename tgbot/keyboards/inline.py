from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from infrastructure.accents import Word
from infrastructure.paronyms import ParonymTask


class MyCallback(CallbackData, prefix="word"):
    id: int
    ans: str


class MenuCallback(CallbackData, prefix="menu"):
    mode: str


class ParonymCallback(CallbackData, prefix="paronym"):
    task: str
    ans: str


async def get_word_keyboard(word: Word):
    builder = InlineKeyboardBuilder()
    for variant in word.variants:
        builder.add(InlineKeyboardButton(
            text=variant,
            callback_data=MyCallback(id=word.id, ans=variant).pack(),
        ))
    builder.adjust(1)
    return builder


async def get_main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Задание 4: ударения", callback_data=MenuCallback(mode="accents").pack()))
    builder.add(InlineKeyboardButton(text="Задание 5: паронимы", callback_data=MenuCallback(mode="paronyms").pack()))
    builder.adjust(1)
    return builder


async def get_paronym_keyboard(task: ParonymTask):
    builder = InlineKeyboardBuilder()
    payload = task.callback_payload()
    for variant in task.variants:
        builder.add(InlineKeyboardButton(
            text=variant,
            callback_data=ParonymCallback(task=payload, ans=variant).pack(),
        ))
    builder.adjust(1)
    return builder
