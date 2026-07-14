from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_id: str
    app_secret: str
    default_root_folder_token: str = ""
    folder_cache_ttl: int = 300
    max_concurrent_uploads: int = 3

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
