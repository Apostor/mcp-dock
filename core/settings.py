from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    enabled_servers: str = ""
    tokens_path: str = "/opt/app/tokens"
    credentials_path: str = "/opt/app/credentials"

    def get_enabled_servers(self) -> list[str]:
        return [s.strip() for s in self.enabled_servers.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
