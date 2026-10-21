"""
Central configuration. Everything comes from environment variables (.env).
Never hardcode secrets here — see .env.example for the full list.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "AdPilot"
    ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me"  # used for JWT signing
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h

    # --- Database ---
    DATABASE_URL: str = "postgresql+psycopg://adpilot:adpilot@localhost:5432/adpilot"

    # --- Redis / Queue ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- LLM (LiteLLM abstraction: gemini -> groq -> ollama fallback chain) ---
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini/gemini-flash-latest"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "groq/llama-3.1-8b-instant"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "ollama/llama3.1:8b"
    LLM_TIMEOUT_SECONDS: int = 60

    # --- Meta / Facebook Marketing API ---
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    META_API_VERSION: str = "v21.0"
    META_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/meta/oauth/callback"
    # System user token used ONLY for our own dev/test ad account (Milestone 1-2).
    META_SYSTEM_USER_TOKEN: str = ""

    # --- Encryption for stored Meta tokens ---
    FERNET_KEY: str = ""  # generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

    # --- Budget Guard (hard ceilings — NOT configurable via API, see agents/budget_guard.py) ---
    MAX_DAILY_BUDGET_INR: int = 5000
    MAX_CAMPAIGN_LIFETIME_INR: int = 50000

    # --- Sentry ---
    SENTRY_DSN: str = ""

    # --- CORS ---
    CORS_ORIGINS: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
