import html

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import (
    KICKED,
    MEMBER,
    ChatMemberUpdatedFilter,
    Command,
    CommandStart,
)
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message

from infrastructure.accents import Accenter, Word
from infrastructure.database.repo.requests import RequestsRepo
from infrastructure.paronyms import ParonymTask
from tgbot.keyboards.inline import (
    MenuCallback,
    MyCallback,
    ParonymCallback,
    get_main_menu_keyboard,
    get_paronym_keyboard,
    get_word_keyboard,
)
from tgbot.keyboards.reply import MAIN_MENU_TEXT, main_menu_reply_keyboard

user_router = Router()


async def safe_edit_text(message, text: str, **kwargs):
    try:
        return await message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
        return None


async def send_main_menu(message: Message):
    k = await get_main_menu_keyboard()
    await message.answer(
        "Что хотите потренировать?",
        reply_markup=main_menu_reply_keyboard,
    )
    await message.answer("Выберите задание:", reply_markup=k.as_markup())


async def send_accent_task(message: Message):
    task = Word()
    k = await get_word_keyboard(task)
    await message.answer(
        "Задание 4. Выберите правильное ударение:", reply_markup=k.as_markup()
    )


async def send_paronym_task(message: Message):
    task = ParonymTask()
    k = await get_paronym_keyboard(task)
    await message.answer(
        f"Задание 5. Паронимы.\n\n{task.question}", reply_markup=k.as_markup()
    )


@user_router.message(CommandStart())
async def user_start(message: Message):
    await send_main_menu(message)


@user_router.message(F.text == MAIN_MENU_TEXT)
async def main_menu_button(message: Message):
    await send_main_menu(message)


@user_router.callback_query(MenuCallback.filter(F.mode == "accents"))
async def choose_accents(call: CallbackQuery):
    await call.answer()
    await safe_edit_text(call.message, "Режим: задание 4, ударения.")
    await send_accent_task(call.message)


@user_router.callback_query(MenuCallback.filter(F.mode == "paronyms"))
async def choose_paronyms(call: CallbackQuery):
    await call.answer()
    await safe_edit_text(call.message, "Режим: задание 5, паронимы.")
    await send_paronym_task(call.message)


@user_router.message(Command("help"))
async def user_help(message: Message):
    await message.reply(
        "Бот для тренировки ЕГЭ по русскому.\n"
        "/start — выбрать задание\n"
        "/count — статистика\n"
        "/words — слова задания 4\n"
        "/paronyms — паронимы задания 5\n"
        "/top — топ пользователей"
    )


@user_router.message(Command("words"))
async def user_words(message: Message):
    msg = ", ".join(Word().get_all_words())
    await message.answer(
        "В тренажёре задания 4 используются слова из официального материала ФИПИ:\n\n"
        "«Навигатор самостоятельной подготовки к ЕГЭ 2026. Русский язык. "
        "Фонетика и орфоэпия»\n\n"
        "Источник: https://doc.fipi.ru/navigator-podgotovki/navigator-ege/2026/ru-1-fonetika.pdf\n\n"
        "Важно: орфоэпический список взят из ФИПИ, а варианты с неправильными ударениями "
        "сгенерированы для тренировочного формата."
    )
    await message.answer(msg)


@user_router.message(Command("paronyms"))
async def user_paronyms(message: Message):
    msg = ", ".join(ParonymTask().get_all_words())
    await message.answer(
        "В тренажёре задания 5 используются паронимы из официального материала ФИПИ:\n\n"
        "«Навигатор самостоятельной подготовки к ЕГЭ 2026. Русский язык. "
        "Лексика и фразеология»\n\n"
        "Источник: https://doc.fipi.ru/navigator-podgotovki/navigator-ege/2026/ru-2-leksika-i-frazeologija.pdf\n\n"
        "Важно: список паронимов взят из ФИПИ, а краткие пояснения и тренировочные примеры "
        "составлены для удобства запоминания."
    )
    await message.answer(msg)


@user_router.message(Command("top"))
async def user_top(message: Message, repo: RequestsRepo):
    users = await repo.users.get_biggest_words()
    msg = "Топ пользователей:\n\n"
    for index, user in enumerate(users):
        msg += f"{index + 1}. {html.escape(user.full_name)} - {user.words}\n"
    await message.answer(msg)


@user_router.message(Command("count"))
async def user_count(message: Message, repo: RequestsRepo):
    words = await repo.users.get_words_count_by_id(message.from_user.id)
    await message.reply(f"Решено заданий: {words}")


@user_router.callback_query(MyCallback.filter())
async def word(call: CallbackQuery, callback_data: MyCallback, repo: RequestsRepo):
    current_word = Word(callback_data.id)
    if callback_data.ans == current_word.right:
        await repo.users.add_word(call.from_user.id)
        await safe_edit_text(call.message, f"Верно! <b>{current_word.right}</b>")
        await send_accent_task(call.message)
    else:
        await call.answer("Неверно! Попробуй ещё раз", show_alert=True)


@user_router.callback_query(ParonymCallback.filter())
async def paronym(
    call: CallbackQuery, callback_data: ParonymCallback, repo: RequestsRepo
):
    current_task = ParonymTask.from_payload(callback_data.task)
    if callback_data.ans == current_task.right:
        await repo.users.add_word(call.from_user.id)
        await safe_edit_text(
            call.message,
            (
                f"✅ Верно! <b>{current_task.right}</b>\n\n"
                f"{current_task.explanation_with_examples}"
            ),
        )
        await send_paronym_task(call.message)
    else:
        await call.answer("Неверно! Попробуй ещё раз", show_alert=True)


@user_router.message(F.text, ~F.text.startswith("/"))
async def make_accent(message: Message):
    await message.answer(str(Accenter(message.text)))


@user_router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=KICKED))
async def user_blocked_bot(event: ChatMemberUpdated, repo: RequestsRepo):
    await repo.users.active_user(event.from_user.id, active=False)


@user_router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=MEMBER))
async def user_unblocked_bot(event: ChatMemberUpdated, repo: RequestsRepo):
    await repo.users.active_user(event.from_user.id, active=True)
