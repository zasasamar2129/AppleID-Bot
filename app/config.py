from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    bot_token: str
    admin_ids: str = ""
    default_language: str = "fa"
    default_currency: str = "IRR"
    timezone: str = "Asia/Tehran"
    maintenance_mode: bool = False
    log_level: str = "INFO"

    # Database
    database_url: str | None = None
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "apple_store"
    db_user: str = "apple_bot"
    db_password: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Mandatory channel membership
    required_channel_id: int = -1002143420264
    required_channel_username: str = "@mobilemeisam2"
    required_channel_url: str = "https://t.me/mobilemeisam2"

    # Encryption
    encryption_key: str

    # Payment
    payment_api_base_url: str | None = None
    payment_api_key: str | None = None
    payment_api_secret: str | None = None
    payment_callback_secret: str | None = None
    online_payment_enabled: bool = True

    # Payment Bridge (to Iran VPS)
    payment_bridge_url: str | None = None
    payment_bridge_api_key: str | None = None

    # SEP Payment
    sep_enabled: bool = False
    sep_merchant_id: str | None = None
    sep_terminal_id: str | None = None
    sep_username: str | None = None
    sep_password: str | None = None
    sep_callback_url: str | None = None
    # Endpoint overrides; unset means "use the reference package's default".
    sep_api_url: str | None = None
    sep_payment_url: str | None = None
    sep_verify_url: str | None = None
    # How long a payment may sit open at the bank before it stops being
    # treated as recoverable by reconciliation.
    payment_ttl_minutes: int = 30

    card_to_card_enabled: bool = True
    card_to_card_number: str | None = None
    card_to_card_holder: str | None = None
    card_to_card_bank: str | None = None
    payment_reconciliation_enabled: bool = True
    payment_reconciliation_interval_seconds: int = 60

    # Inventory
    inventory_reservation_seconds: int = 600

    # Broadcast
    broadcast_batch_size: int = 20
    broadcast_delay_seconds: int = 1

    # Rate limiting
    rate_limit_enabled: bool = True

    # Telegram Bot username (optional, for deep links)
    telegram_bot_username: str | None = None

    # Unicode emoji customization
    emoji_cart: str = "🛒"
    emoji_wallet: str = "💰"
    emoji_success: str = "✅"
    emoji_error: str = "❌"
    emoji_loading: str = "⏳"
    emoji_apple: str = "🍎"
    emoji_gift: str = "🎁"
    emoji_support: str = "🎧"

    # Custom emoji configuration
    custom_emoji_enabled: bool = False
    emoji_cart_id: str | None = None
    emoji_apple_id: str | None = None
    emoji_wallet_id: str | None = None
    emoji_success_id: str | None = None
    emoji_error_id: str | None = None
    emoji_payment_id: str | None = None
    emoji_support_id: str | None = None
    emoji_profile_id: str | None = None
    emoji_settings_id: str | None = None
    emoji_order_id: str | None = None
    emoji_inventory_id: str | None = None
    emoji_back_id: str | None = None
    emoji_cancel_id: str | None = None
    emoji_gift_id: str | None = None

    # Custom emoji IDs for main menu buttons
    emoji_buy_apple_id: str | None = None
    emoji_unlock_apple_id: str | None = None
    emoji_price_inquiry_id: str | None = None
    emoji_coupon_id: str | None = None
    emoji_referral_id: str | None = None
    emoji_language_id: str | None = None
    emoji_about_id: str | None = None
    emoji_learn_id: str | None = None

    @property
    def admin_ids_list(self) -> list[int]:
        if not self.admin_ids.strip():
            return []
        return [int(x) for x in self.admin_ids.split(",") if x.strip()]

    @property
    def database_url_final(self) -> str:
        if self.database_url:
            return self.database_url
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def is_online_payment_configured(self) -> bool:
        # Check for bridge or SEP (direct or bridged)
        return bool(
            (self.payment_bridge_url and self.payment_bridge_api_key) or
            (self.sep_enabled and self.sep_merchant_id and self.sep_terminal_id)
        )


settings = Settings()
