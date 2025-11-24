from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_SECRET_TOKEN: str  # For verifying webhook comes from Telegram
    TELEGRAM_WEBHOOK_URL: str | None = (
        None  # Webhook URL for Telegram (set via scripts)
    )

    # LLM
    LLM_API_KEY: str
    LLM_BASE_URL: str
    LLM_MODEL: str

    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: (
        str  # service_role key preferred for backend, or anon if using RLS carefully
    )

    # Internal
    ADMIN_API_KEY: str  # For securing cron endpoints

    # App
    TZ: str = "Asia/Almaty"
    TARGET_CHAT_ID: int | None = None

    @field_validator("TARGET_CHAT_ID", mode="before")
    @classmethod
    def parse_target_chat_id(cls, v):
        if v == "" or v is None:
            return None
        if isinstance(v, str):
            return int(v) if v.strip() else None
        return v

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
