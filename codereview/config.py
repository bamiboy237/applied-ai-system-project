"""Application settings and `.env` loading for the codereview package."""

from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE)

    openai_api_key: SecretStr = Field(alias="OPENAI_API_KEY")
    openai_model: str = "gpt-5.4-mini"
    project_root: Path = Path(ENV_FILE.parent.resolve()).resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache application settings from the configured `.env` file."""
    settings_type = cast(Any, Settings)
    return settings_type(_env_file=ENV_FILE)
