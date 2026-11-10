from functools import lru_cache 
from pydantic_settings import SettingsConfigDict , BaseSettings 
from pathlib import Path
from pydantic import SecretStr, field_validator, model_validator


class Settings(BaseSettings):
    app_name : str  = "Developers Eye"
    app_env : str = "development"
    debug: bool = False 
    edge_shared_secret: SecretStr | None = None
    api_docs_enabled: bool = True

    @field_validator("edge_shared_secret", mode="before")
    @classmethod
    def validate_edge_secret(cls, value):
        if value is None or value == "":
            return None
        raw = value.get_secret_value() if isinstance(value, SecretStr) else value
        if len(raw) < 32 or not raw.isascii() or any(ch.isspace() for ch in raw):
            raise ValueError("EDGE_SHARED_SECRET must be 32+ ASCII characters without whitespace")
        return value

    @model_validator(mode="after")
    def require_production_edge_secret(self):
        if self.app_env.lower() in {"production", "prod"} and self.edge_shared_secret is None:
            raise ValueError("EDGE_SHARED_SECRET is required in production")
        return self

    # AI overview is entirely backend-owned; no Groq configuration in Next.js.
    groq_api_key: SecretStr | None = None
    groq_model: str = "qwen/qwen3.8-27b"
    ai_overview: bool = True
    # Only trust a header overwritten by the ingress and preserved by the UI proxy.
    ai_overview_client_ip_header: str = ""

    database_url : str  
    # Per process. Keep (pool_size + max_overflow) * processes under Postgres max_connections.
    db_pool_size: int = 2
    db_max_overflow: int = 2
    db_pool_timeout_seconds: float = 30.0
    db_pool_recycle_seconds: int = 1800
    crawler_report_api_key: SecretStr | None = None
    # Must match the indexer worker's INDEXER_INDEX_VERSION.
    indexer_index_version: int = 1
    # Admin capacity planning: database disk budget and document goal.
    admin_db_budget_gb: float = 120.0
    admin_target_documents: int = 5_000_000
    # Matches the crawler's DEFAULT_MIN_INTERVAL_SECONDS (per process, per host).
    admin_host_min_interval_seconds: float = 2.0
    # crawl_event rows older than this are purged by admin_services.maintenance.
    admin_event_retention_days: int = 14


    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

@lru_cache
def get_settings() -> Settings :
    return Settings() 

settings = get_settings()
