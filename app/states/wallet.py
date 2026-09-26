from aiogram.fsm.state import State, StatesGroup


class WalletStates(StatesGroup):
    SELECT_DEPOSIT_METHOD = State()
    ENTER_AMOUNT = State()
    WAITING_PAYMENT = State()
    WAITING_REFERENCE = State()
    WAITING_RECEIPT = State()

class WalletTopUpStates(StatesGroup):
    ENTER_AMOUNT = State()
    SELECT_METHOD = State()
    WAITING_CONFIRMATION = State()
    WAITING_RECEIPT = State()
    WAITING_REFERENCE = State()
