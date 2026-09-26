from aiogram.fsm.state import State, StatesGroup


class AppleUnlockStates(StatesGroup):
    select_model = State()
    email_access = State()
    apple_id_email = State()
    apple_id_password = State()
    imei = State()
    other_iphone_locked = State()
    phone_number = State()
    additional_information = State()
    confirm = State()
    # Sub-states for editing a specific field
    edit_select = State()
    edit_series = State()
    edit_email_access = State()
    edit_apple_id_email = State()
    edit_apple_id_password = State()
    edit_imei = State()
    edit_other_locked = State()
    edit_phone_number = State()
    edit_additional = State()


# Legacy/inquiry-based states (kept for the old unlock_inquiries flow)
class UnlockAppleIDStates(StatesGroup):
    SELECT_PHONE_MODEL = State()
    ENTER_APPLE_ID_EMAIL = State()
    ENTER_PHONE_NUMBER = State()
    CONFIRM_CREDENTIALS_ACCESS = State()
    COMPLETED = State()