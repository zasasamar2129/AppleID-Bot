from aiogram.fsm.state import State, StatesGroup


class AdminPaymentStates(StatesGroup):
    REJECT_REASON = State()
