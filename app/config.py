from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_SECRET_TOKEN: str  # For verifying webhook comes from Telegram
    TELEGRAM_WEBHOOK_URL: str | None = (
        None  # Webhook URL for Telegram (set via scripts)
    )
    TELEGRAM_WEBHOOK_MAX_AGE_SECONDS: int = 300  # Reject updates older than this window; 0 disables.
    TELEGRAM_WEBHOOK_REPLAY_TTL_SECONDS: int = 300  # How long to keep update IDs for replay detection; 0 disables.
    TELEGRAM_WEBHOOK_REPLAY_CACHE_SIZE: int = 10000  # Max cached update IDs for replay detection; 0 disables.

    # LLM
    LLM_API_KEY: str
    LLM_BASE_URL: str
    LLM_MODEL: str

    # Supabase (migration-only; optional at runtime)
    SUPABASE_URL: str | None = None
    SUPABASE_KEY: str | None = None  # service_role preferred for migration

    # Internal
    ADMIN_API_KEY: str  # For securing cron endpoints

    # App
    TZ: str = "Asia/Almaty"
    TARGET_CHAT_ID: int | None = None
    SUPERUSER_TELEGRAM_IDS: list[int] = []

    # Habit Reward Integration (shared base URL; per-user keys stored in UserSettings DB)
    HABIT_REWARD_BASE_URL: str = "https://habitreward.org"
    HABIT_REWARD_TIMEOUT: int = 10  # HTTP timeout in seconds

    @field_validator("TARGET_CHAT_ID", mode="before")
    @classmethod
    def parse_target_chat_id(cls, v):
        if v == "" or v is None:
            return None
        if isinstance(v, str):
            return int(v) if v.strip() else None
        return v

    @field_validator("SUPERUSER_TELEGRAM_IDS", mode="before")
    @classmethod
    def parse_superuser_ids(cls, v):
        """Parse comma-separated telegram user IDs."""
        if v == "" or v is None:
            return []
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, list):
            return v
        return []

    @field_validator("HABIT_REWARD_BASE_URL", mode="before")
    @classmethod
    def parse_habit_reward_url(cls, v):
        """Normalize base URL by removing trailing slash."""
        if v == "" or v is None:
            return "https://habitreward.org"
        if isinstance(v, str):
            return v.rstrip("/")
        return v

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
