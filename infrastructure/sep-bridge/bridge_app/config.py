from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bridge_host: str = "0.0.0.0"
    bridge_port: int = 8443
    bridge_api_key: str
    allowed_client_ip: str | None = None

    request_timeout_seconds: float = 15.0
    log_level: str = "INFO"

    sep_token_api_url: str = "https://sep.shaparak.ir/OnlinePG/OnlinePG"
    sep_payment_url: str = "https://sep.shaparak.ir/OnlinePG/OnlinePG"
    sep_verify_api_url: str = "https://sep.shaparak.ir/verifyTxnRandomSessionkey/ipg/VerifyTransaction"

    sep_merchant_id: str
    sep_terminal_id: str | None = None
    sep_username: str | None = None
    sep_password: str | None = None

settings = Settings()
