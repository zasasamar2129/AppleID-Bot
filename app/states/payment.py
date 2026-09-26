from aiogram.fsm.state import State, StatesGroup


class PaymentStates(StatesGroup):
    SELECT_METHOD = State()
    WAITING_ONLINE_PAYMENT = State()
    WAITING_CARD_TRANSFER = State()
    WAITING_REFERENCE = State()
    WAITING_RECEIPT = State()
    VERIFYING = State()


class CardToCardStates(StatesGroup):
    SHOW_INSTRUCTIONS = State()
    WAITING_FOR_RECEIPT = State()   # customer can send photo or text
