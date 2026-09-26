from aiogram.fsm.state import State, StatesGroup


class AdminPriceInquiryStates(StatesGroup):
    NAME_FA = State()
    NAME_EN = State()
    PRICE = State()
    EDIT_PRICE = State()
