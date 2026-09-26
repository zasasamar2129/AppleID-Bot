from aiogram.fsm.state import State, StatesGroup


class AdminBroadcastStates(StatesGroup):
    CONTENT = State()
    AUDIENCE = State()
    PREVIEW = State()
    CONFIRM = State()
