from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    anakin_api_key: str | None = None
    gemini_api_key: str | None = None
    anakin_base_url: str = "https://api.anakin.io/v1"
    cache_ttl_seconds: int = 900
    request_timeout_seconds: float = 45.0
    wire_poll_interval_seconds: float = 1.5
    wire_max_poll_seconds: float = 30.0
    enable_gemini: bool = False

    @field_validator("anakin_base_url", mode="before")
    @classmethod
    def normalize_anakin_base_url(cls, value: object) -> str:
        base_url = str(value or "https://api.anakin.io/v1").strip().rstrip("/")
        base_url = base_url.replace("https://anakin.io/", "https://api.anakin.io/")

        if "/wire/" in base_url:
            base_url = base_url.split("/wire/", maxsplit=1)[0]
        elif base_url.endswith("/wire"):
            base_url = base_url.removesuffix("/wire")

        return base_url

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
