from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_SECRET_TOKEN: str  # For verifying webhook comes from Telegram
    
    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str  # service_role key preferred for backend, or anon if using RLS carefully

    # Internal
    ADMIN_API_KEY: str  # For securing cron endpoints
    
    # App
    TZ: str = "Asia/Almaty"
    TARGET_CHAT_ID: int | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

