from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.localization import get_text
from app.utils.message_manager import MessageCleanupService

router = Router()

LOGIN_GUIDE_FA = """🇮🇷 <b>آموزش ورود به Apple ID</b>
<b>📱 آیفون و آیپد</b>

1. وارد <b>Settings</b> شوید.
2. روی <b>Sign in to your (iPhone/iPad)</b> بزنید.
3. گزینه <b>Sign in Manually</b> را انتخاب کنید.
4. Apple ID و رمز عبور را وارد کرده و <b>Sign In / Continue</b> را بزنید.
5. اگر پیام <b>Apple ID Security</b> نمایش داده شد، روی <b>Continue</b> نزنید.
6. گزینه <b>Other Options → Don't Upgrade</b> را انتخاب کنید و <b>Terms & Conditions</b> را بپذیرید.

<b>💻 مک</b>

1. روی ‎<b></b> در بالای صفحه کلیک کنید → <b>System Settings</b>.
2. روی <b>Sign in with your Apple ID</b> بزنید.
3. Apple ID و رمز عبور را وارد کنید.
4. اگر پیام <b>Apple ID Security</b> آمد، <b>Continue</b> را نزنید.
5. <b>Other Options → Don't Upgrade</b> را انتخاب کرده و شرایط را بپذیرید.

⚠️ <b>نکته مهم:</b>
حتماً <b>Find My iPhone</b> را خاموش کنید.
"""

LOGIN_GUIDE_EN = """🇬🇧 <b>Apple ID Login Guide</b>
<b>📱 iPhone & iPad</b>

1. Open <b>Settings</b>.
2. Tap <b>Sign in to your (iPhone/iPad)</b>.
3. Select <b>Sign in Manually</b>.
4. Enter your Apple ID and password → tap <b>Sign In / Continue</b>.
5. If <b>Apple ID Security</b> appears, <b>DO NOT</b> tap Continue.
6. Select <b>Other Options → Don't Upgrade</b>, then accept the Terms & Conditions.

<b>💻 Mac</b>

1. Click <b>‎</b> → <b>System Settings</b>.
2. Tap <b>Sign in with your Apple ID</b>.
3. Enter your Apple ID and password.
4. If <b>Apple ID Security</b> appears, <b>DO NOT</b> tap Continue.
5. Select <b>Other Options → Don't Upgrade</b>, then accept the terms.

⚠️ <b>Important:</b>
make sure <b>Find My iPhone</b> is turned off.
"""

FINDMY_GUIDE_FA = """🇮🇷 <b>خاموش کردن Find My iPhone</b>

1. وارد <b>Settings</b> شوید.
2. روی <b>نام / Apple ID</b> خود در بالای صفحه بزنید.
3. وارد <b>Find My (یافتن من)</b> شوید.
4. روی <b>Find My iPhone</b> بزنید.
5. گزینه <b>Find My iPhone</b> را خاموش کنید.
6. رمز Apple ID را وارد کنید.
7. روی <b>Turn Off</b> بزنید. ✅

⚠️ <b>نکته:</b> برای خاموش کردن Find My iPhone، داشتن رمز Apple ID ضروری است.
"""

FINDMY_GUIDE_EN = """🇬🇧 <b>How to Turn Off Find My iPhone</b>

1. Open <b>Settings</b>.
2. Tap your <b>Name / Apple ID</b> at the top.
3. Go to <b>Find My</b>.
4. Tap <b>Find My iPhone</b>.
5. Turn <b>Find My iPhone</b> OFF.
6. Enter your Apple ID password.
7. Tap <b>Turn Off</b>. ✅

⚠️ <b>Note:</b> Your Apple ID password is required to turn off Find My iPhone.
"""


@router.callback_query(F.data == "menu:learn_how_to")
async def learn_how_to_menu(callback: CallbackQuery, lang="fa"):
    kb = InlineKeyboardBuilder()
    kb.button(text=f"📱 {get_text('tutorial.login', lang)}", callback_data="tutorial:login")
    kb.button(text=f"🌐 {get_text('tutorial.findmy', lang)}", callback_data="tutorial:findmy")
    kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data="menu:main")
    kb.adjust(1)

    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=get_text("tutorial.menu", lang),
        reply_markup=kb.as_markup(),
        force_new=True,
    )
    await callback.answer()


@router.callback_query(F.data == "tutorial:login")
async def tutorial_login(callback: CallbackQuery, lang="fa"):
    text = LOGIN_GUIDE_FA if lang == "fa" else LOGIN_GUIDE_EN
    kb = InlineKeyboardBuilder()
    kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data="menu:learn_how_to")
    kb.button(text=f"🏠 {get_text('common.main_menu', lang)}", callback_data="menu:main")
    kb.adjust(1)
    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=text,
        reply_markup=kb.as_markup(),
        force_new=True,
    )
    await callback.answer()


@router.callback_query(F.data == "tutorial:findmy")
async def tutorial_findmy(callback: CallbackQuery, lang="fa"):
    text = FINDMY_GUIDE_FA if lang == "fa" else FINDMY_GUIDE_EN
    kb = InlineKeyboardBuilder()
    kb.button(text=f"⬅️ {get_text('common.back', lang)}", callback_data="menu:learn_how_to")
    kb.button(text=f"🏠 {get_text('common.main_menu', lang)}", callback_data="menu:main")
    kb.adjust(1)
    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=text,
        reply_markup=kb.as_markup(),
        force_new=True,
    )
    await callback.answer()