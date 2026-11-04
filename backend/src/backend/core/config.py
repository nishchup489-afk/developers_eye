from functools import lru_cache 
from pydantic_settings import SettingsConfigDict , BaseSettings 
from pathlib import Path
from pydantic import SecretStr


class Settings(BaseSettings):
    app_name : str  = "Developers Eye"
    app_env : str = "development"
    debug: bool = False 

    database_url : str  
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
