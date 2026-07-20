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
    # Comment/journal backfill (Activity API is one call per work package —
    # paced across sync runs instead of all at once). Steady-state syncs only
    # refetch a WP's journal when its updated_at has moved since last pull.
    openproject_journal_batch: int = 250
    openproject_journal_comment_cap: int = 20  # comments kept per WP for RAG

    # AI layer (Phase 5). Providers are pluggable (AI-010); auto-picks by key.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"  # cheapest capable model — cost guard
    ai_max_tokens: int = 400  # hard cap per answer — cost guard
    insights_cache_hours: int = 6  # department insight cards recompute at most this often

    # RAG embeddings (Ask IO semantic recall). Local + free — no API key.
    # `rag_embeddings_enabled=False` (or a missing/failing `fastembed` install)
    # degrades to the deterministic HashingEmbedder; nothing breaks either way.
    rag_embeddings_enabled: bool = True
    rag_embed_model: str = "BAAI/bge-small-en-v1.5"
    rag_top_k: int = 10
    rag_min_score: float = 0.35

    # Document uploads (FlyNava archive / approval workflows)
    upload_dir: str = "uploads"

    # Email / SMTP (bug report sending). If unset, reports run in preview mode.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True

    # Reporting hub: background scheduler for automated report delivery.
    # Disabled in tests (see tests/conftest.py) so pytest never races a live
    # thread against its mongomock fixtures.
    scheduler_enabled: bool = True
    scheduler_interval_sec: int = 30


settings = Settings()
