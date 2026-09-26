from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiogram.types import CallbackQuery, Message
    from aiogram.fsm.context import FSMContext

from app.utils.message_manager import MessageCleanupService
from app.bot.keyboards.main_menu import main_menu_keyboard
from app.localization import get_text


async def navigate_back(
    callback_or_message: CallbackQuery | Message,
    target_text: str,
    target_callback_data: str | None = None,
    state: FSMContext | None = None,
    lang: str = "fa",
) -> None:
    """Navigate back with proper message deletion.

    Args:
        callback_or_message: The CallbackQuery or Message triggering navigation
        target_text: Text to show in target menu
        target_callback_data: Callback data for target menu (if None, goes to main menu)
        state: Optional FSM state to clear
        lang: Language code
    """
    if state:
        await state.clear()

    chat_id = (
        callback_or_message.message.chat.id
        if hasattr(callback_or_message, 'message')
        else callback_or_message.chat.id
    )

    # Delete the current menu message
    if hasattr(callback_or_message, 'message'):
        # CallbackQuery - delete the message containing the button
        try:
            await MessageCleanupService.delete_message(
                chat_id,
                callback_or_message.message.message_id
            )
        except Exception:
            pass  # Message might not be tracked or already deleted

    # Cleanup temporary messages
    await MessageCleanupService.cleanup_user_ui(chat_id)

    if target_callback_data == "menu:main" or target_callback_data is None:
        # Going to main menu
        await MessageCleanupService.show_screen(
            chat_id=chat_id,
            text=get_text("start.welcome", lang, name=callback_or_message.from_user.first_name),
            reply_markup=main_menu_keyboard(lang),
            force_new=True,
        )
    else:
        # Going to other menu - would need to import specific handler
        # For now, use show_screen with force_new
        pass