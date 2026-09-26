from aiogram.fsm.state import State, StatesGroup


class AdminProductStates(StatesGroup):
    CREATE_NAME = State()
    CREATE_DESCRIPTION = State()
    CREATE_TYPE = State()
    CREATE_REGION = State()
    CREATE_PRICE = State()
    CREATE_DISCOUNT = State()
    CREATE_PROCESSING_TIME = State()
    CREATE_DELIVERY_TYPE = State()
    CREATE_BADGES = State()
    CREATE_SORT_ORDER = State()
    EDIT_SELECT = State()
    EDIT_FIELD = State()
    EDIT_PRICE = State()
    EDIT_NAME = State()
    CONFIRM_DELETE = State()
