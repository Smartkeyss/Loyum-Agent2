# app/core/config.py
from __future__ import annotations
from functools import lru_cache
from typing import Literal
from pathlib import Path

from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"

class Settings(BaseSettings):
    openai_api_key: str = Field(..., validation_alias=AliasChoices("OPENAI_API_KEY"))
    openai_model: str = Field("gpt-5", validation_alias=AliasChoices("OPENAI_MODEL"))

    apify_token: str = Field(..., validation_alias=AliasChoices("APIFY_TOKEN"))
    apify_tiktok_actor: str = Field(
        "clockworks~tiktok-trends-scraper",
        validation_alias=AliasChoices("APIFY_TIKTOK_ACTOR"),
    )
    apify_x_actor: str = Field(
        "oCAEibQtPGKXcF5MM",
        validation_alias=AliasChoices("APIFY_X_ACTOR"),
    )
    apify_default_timeout_sec: int = Field(
        900, validation_alias=AliasChoices("APIFY_DEFAULT_TIMEOUT_SEC")
    )
    apify_facebook_actor: str = Field(
        "apify~facebook-posts-scraper",
        validation_alias=AliasChoices("APIFY_FACEBOOK_ACTOR"),
    )

    backend_port: int = Field(8000, validation_alias=AliasChoices("BACKEND_PORT"))
    
    apify_force_input_json: str | None = Field(
        None, validation_alias=AliasChoices("APIFY_FORCE_INPUT_JSON"))

    # Pydantic v2 settings config (replaces class Config)
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

PlatformLiteral = Literal["tiktok", "x", "facebook"]

@lru_cache
def get_settings() -> Settings:
    return Settings()
