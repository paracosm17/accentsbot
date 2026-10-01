from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

MAIN_MENU_TEXT = "Главное меню"

main_menu_reply_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=MAIN_MENU_TEXT)]],
    resize_keyboard=True,
    input_field_placeholder="Выберите режим или отправьте текст",
)
