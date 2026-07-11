"""Application configuration loaded from environment / .env.

All config lives here — nothing hardcoded elsewhere (PRD NFR-013).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    # MongoDB
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "io"

    # CORS
    cors_origins: str = "*"

    # Auth / security
    jwt_secret: str = "dev-insecure-change-me"
    jwt_alg: str = "HS256"
    access_token_ttl_min: int = 30
    refresh_token_ttl_days: int = 7
    session_idle_min: int = 30  # PRD SEC-005
    bcrypt_rounds: int = 12  # PRD SEC-003 (min cost 12)

    # Rate limiting (PRD API-004)
    rate_limit_enabled: bool = True
    rate_limit_per_min: int = 100

    # OpenProject integration (Phase 2)
    openproject_base_url: str = "https://op.flynava.ai"
    openproject_api_key: str = ""

    # AI layer (Phase 5). Providers are pluggable (AI-010); auto-picks by key.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"  # cheapest capable model — cost guard
    ai_max_tokens: int = 400  # hard cap per answer — cost guard

    # Document uploads (FlyNava archive / approval workflows)
    upload_dir: str = "uploads"

    # Email / SMTP (bug report sending). If unset, reports run in preview mode.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True


settings = Settings()
