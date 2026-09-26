from aiogram.fsm.state import State, StatesGroup


class AdminCouponStates(StatesGroup):
    CREATE_CODE = State()
    CREATE_TYPE = State()
    CREATE_VALUE = State()
    CREATE_MAX_DISCOUNT = State()
    CREATE_MIN_ORDER = State()
    CREATE_GLOBAL_LIMIT = State()
    CREATE_PER_USER_LIMIT = State()
    CREATE_START_DATE = State()
    CREATE_END_DATE = State()
    EDIT_SELECT = State()
    EDIT_FIELD = State()
