from aiogram.fsm.state import State, StatesGroup


class CouponStates(StatesGroup):
    ENTER_CODE = State()
