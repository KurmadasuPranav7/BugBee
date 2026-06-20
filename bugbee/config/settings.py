"""Configuration handling for BugBee.

BugBee loads configuration from:

1. Environment variables
2. .env file
3. Optional YAML configuration

Environment variables always take precedence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from platformdirs import user_cache_dir, user_data_dir


class Settings(BaseSettings):
    """Global configuration for BugBee."""

    # ------------------------------------------------------------------
    # Pydantic Settings Configuration
    # ------------------------------------------------------------------

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore unknown environment variables
    )

    # ------------------------------------------------------------------
    # General
    # ------------------------------------------------------------------

    log_level: str = "INFO"

    temperature: float = 0.1

    retrieval_k: int = 3

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------

    cache_file: Path = Field(
        default_factory=lambda: Path(user_cache_dir("bugbee")) / "cache.json"
    )

    chromadb_path: Path = Field(
        default_factory=lambda: Path(user_data_dir("bugbee")) / "chromadb"
    )

    # ------------------------------------------------------------------
    # LLM Configuration
    # ------------------------------------------------------------------

    llm_endpoint: str = (
        "https://api-inference.huggingface.co/models/deepseek-ai/DeepSeek-R1"
    )

    # ------------------------------------------------------------------
    # API Keys
    # ------------------------------------------------------------------

    openai_api_key: str | None = Field(
        default=None,
        alias="OPENAI_API_KEY",
    )

    anthropic_api_key: str | None = Field(
        default=None,
        alias="ANTHROPIC_API_KEY",
    )

    google_api_key: str | None = Field(
        default=None,
        alias="GOOGLE_API_KEY",
    )

    openrouter_api_key: str | None = Field(
        default=None,
        alias="OPENROUTER_API_KEY",
    )

    huggingface_api_key: str | None = Field(
        default=None,
        validation_alias="HF_TOKEN",
    )


    # ------------------------------------------------------------------
    # Optional YAML Loader
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "Settings":
        """Load configuration from a YAML file."""

        if not yaml_path.exists():
            return cls()

        data: Mapping[str, Any] = yaml.safe_load(
            yaml_path.read_text(encoding="utf-8")
        ) or {}

        return cls(**data)


# Singleton instance used across the project.
settings = Settings()