from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    enabled_servers: list[str] = []
    tokens_path: str = "/opt/app/tokens"

    @field_validator("enabled_servers", mode="before")
    @classmethod
    def parse_comma_separated(cls, v: str | list) -> list[str]:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
