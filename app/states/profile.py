from aiogram.fsm.state import State, StatesGroup


class ProfileStates(StatesGroup):
    FIRST_NAME = State()
    LAST_NAME = State()
    PHONE = State()
