from aiogram_dialog import Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Cancel, Checkbox
from aiogram_dialog.widgets.text import Format, Const

from tgbot.dialogs.broadcast.funcs import count_input, all_selected, send_messages, message_input, random_selected, \
    last_selected, check_changed
from tgbot.dialogs.broadcast.states import BroadcastStates


def broadcast_users_count_window():
    return Window(
        Format('Скольким людям сделать рассылку? Выберите всем активным ({start_data[users_count]}) '
               'или введите свое число \n ИЛИ только тем кто зарегистрировался после егэ 2023 '
               '(всего {start_data[users_count_after_ege]})'
               '\n Это всего лишь режим!!! то есть можно ввести свое число и просто выбрать режим что будет присылаться тем кто зарегался после егэ 2023 либо всем подряд'),
        Button(text=Format("Всем активным"), id="allbroadcast", on_click=all_selected),
        Checkbox(
            Format("Режим: только тем кто после ЕГЭ 2023 ({start_data[users_count_after_ege]})"),
            Format("Режим: Вообще всем ({start_data[users_count]})"),
            id="check",
            default=True,
            on_state_changed=check_changed,
        ),
        MessageInput(func=count_input),
        Cancel(Const("Отмена")),
        state=BroadcastStates.count_state,
    )


def random_or_last_window():
    return Window(
        Const('Каким пользователям разослать?'),
        Button(text=Format("Рандомным {dialog_data[users_to_send_count]} пользователям"), id="rand",
               on_click=random_selected),
        Button(text=Format("Последним {dialog_data[users_to_send_count]} пользователям"), id="last",
               on_click=last_selected),
        Cancel(Const("Отмена")),
        state=BroadcastStates.random_or_last_state,
    )


def message_window():
    return Window(
        Const('Отправьте сообщение, которое необходимо разослать'),
        Cancel(Const("Отмена")),
        MessageInput(func=message_input),
        state=BroadcastStates.message_state,
    )


def apply_window():
    return Window(
        Format('Разослать это сообщение {dialog_data[users_to_send_count]} пользователям?'),
        Button(text=Const("Разослать"), id="go", on_click=send_messages),
        Cancel(Const("Отмена")),
        state=BroadcastStates.apply_state,
    )
