#states.py
from aiogram.fsm.state import StatesGroup, State

class CastingForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_age = State()
    waiting_for_city = State()
    waiting_for_video = State()  # Изменено с portfolio на video