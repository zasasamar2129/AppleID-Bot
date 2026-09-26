from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards import button, get_custom_emoji_id
from app.localization import get_text


def main_menu_keyboard(lang: str = "fa") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()

    # All main-menu buttons go through the `button()` helper, which:
    #  - prefixes the localized text with its Unicode emoji (from get_text) as fallback,
    #  - and when a custom emoji ID resolves, sets icon_custom_emoji_id and strips the
    #    leading Unicode emoji so only the custom animated emoji shows.
    def add_button(text_key: str, callback: str, style: str | None = None, emoji_field: str | None = None):
        kb.add(button(
            get_text(text_key, lang),
            callback_data=callback,
            style=style,
            emoji_id=get_custom_emoji_id(emoji_field) if emoji_field else None,
        ))

    # Buy Apple ID - success style, custom emoji
    add_button("menu.buy_apple_id", "menu:buy", style="success", emoji_field="emoji_buy_apple_id")

    # Unlock Apple ID - danger style, custom emoji
    add_button("menu.unlock_apple_id", "menu:unlock_apple_id", style="danger", emoji_field="emoji_unlock_apple_id")

    # Price Inquiry
    #add_button("menu.price_inquiry", "menu:price_inquiry", style="primary", emoji_field="emoji_price_inquiry_id")

    # My Purchases - custom emoji
    add_button("menu.my_purchases", "menu:purchases", style="primary", emoji_field="emoji_order_id")

    # Profile - custom emoji
    add_button("menu.profile", "menu:profile", style="primary", emoji_field="emoji_profile_id")

    # Wallet
    add_button("menu.wallet", "menu:wallet", emoji_field="emoji_wallet_id")

    # Discount Code
    add_button("menu.discount_code", "menu:coupon", emoji_field="emoji_coupon_id")

    # Referral Program
    add_button("menu.referral", "menu:referral", emoji_field="emoji_referral_id")

    # Support
    add_button("menu.support", "menu:support", emoji_field="emoji_support_id")

    # Language
    add_button("menu.language", "menu:language", emoji_field="emoji_language_id")

    # About
    add_button("menu.about", "menu:about", emoji_field="emoji_about_id")

    # Learn How To (آموزش)
    add_button("menu.learn_how_to", "menu:learn_how_to", emoji_field="emoji_learn_id")

    # Layout: Buy, Unlock, Inquiry, Purchases, Profile each on own row;
    # remaining buttons in pairs.
    kb.adjust(1, 1, 1, 1, 1, 2, 2, 2, 1)
    return kb.as_markup()