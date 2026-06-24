# keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import config

def get_moderation_keys(app_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Одобрить", callback_data=f"approve_{app_id}")
    builder.button(text="❌ Отклонить", callback_data=f"reject_{app_id}")
    builder.button(text="🗑 Удалить", callback_data=f"delete_{app_id}")
    builder.adjust(2)
    return builder.as_markup()

# Функцию get_vote_button() можно удалить или закомментировать
# def get_vote_button():
#     ...