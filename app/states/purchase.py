from aiogram.fsm.state import State, StatesGroup


class PurchaseStates(StatesGroup):
    SELECT_TYPE = State()
    SELECT_REGION = State()
    SELECT_PRODUCT = State()
    SELECT_OPTIONS = State()
    COLLECT_FIRST_NAME = State()
    COLLECT_LAST_NAME = State()
    COLLECT_EMAIL_ASK = State()
    COLLECT_EMAIL = State()
    COLLECT_PHONE = State()
    REVIEW_ORDER = State()
    SELECT_COUPON = State()
    SELECT_PAYMENT = State()
    WAITING_PAYMENT = State()
    PROCESSING = State()
    COMPLETED = State()
