from aiogram.fsm.state import State, StatesGroup


class AdminOrderStates(StatesGroup):
    SELECT_ORDER = State()
    ADD_NOTE = State()
    REFUND_CONFIRM = State()
    CONFIRM_DELETE = State()
