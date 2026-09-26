from aiogram.fsm.state import State, StatesGroup


class AdminInventoryStates(StatesGroup):
    SELECT_PRODUCT = State()
    ENTER_EMAIL = State()
    ENTER_PASSWORD = State()
    ENTER_REGION = State()
    ENTER_NOTES = State()
    BULK_UPLOAD = State()
    WAITING_FORMATTED_TEXT = State()
