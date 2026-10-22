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
