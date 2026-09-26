from aiogram.fsm.state import State, StatesGroup


class AdminSettingsStates(StatesGroup):
    EDIT_KEY = State()
    EDIT_VALUE = State()
    EDIT_FOOTER = State()
