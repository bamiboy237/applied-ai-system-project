from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env"
    )

    openai_api_key: SecretStr = Field(alias="OPENAI_API_KEY")
    openai_model: str = "gpt-5.4-nano"
    project_root: Path = Path("/Users/bogningguy-robert/Desktop/codereview").resolve()


def get_settings() -> Settings:
    try:
        return Settings()
    except Exception as e:
        raise RuntimeError(f"Failed to load settings: {e}")
