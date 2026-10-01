from aiogram.fsm.state import State, StatesGroup


class AdminSupportStates(StatesGroup):
    """FSM states for the admin support panel.

    Deliberately separate from ``SupportStates`` in app/states/support.py:
    that group is registered on the user router, which is not admin-filtered,
    so reusing its REPLY state would swallow admin replies as user input.
    """

    REPLY = State()
