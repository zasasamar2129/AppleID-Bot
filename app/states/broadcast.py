from aiogram.fsm.state import State, StatesGroup


class BroadcastStates(StatesGroup):
    CONTENT = State()
    AUDIENCE = State()
    PREVIEW = State()
    CONFIRM = State()
