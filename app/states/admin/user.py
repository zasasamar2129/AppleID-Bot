from aiogram.fsm.state import State, StatesGroup


class AdminUserStates(StatesGroup):
    SEARCH = State()
    SELECT_USER = State()
    WALLET_ADJUST_AMOUNT = State()
    WALLET_ADJUST_REASON = State()
