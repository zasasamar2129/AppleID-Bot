from aiogram.fsm.state import State, StatesGroup


class AdminAdminStates(StatesGroup):
    ADD_TELEGRAM_ID = State()
    SELECT_ROLE = State()
    EDIT_PERMISSIONS = State()
