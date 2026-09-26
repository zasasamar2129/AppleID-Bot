from aiogram.fsm.state import State, StatesGroup


class AdminUnlockStates(StatesGroup):
    PAYMENT_AMOUNT = State()
    ADD_NOTE = State()