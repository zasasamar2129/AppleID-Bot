from aiogram.fsm.state import State, StatesGroup


class SupportStates(StatesGroup):
    SELECT_CATEGORY = State()
    ENTER_SUBJECT = State()
    ENTER_MESSAGE = State()
    CONFIRM = State()
    REPLY = State()
