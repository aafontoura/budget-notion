"""Application configuration management."""

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with environment variable support.

    Supports loading from .env files and Docker Secrets.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Notion Configuration
    notion_token: str = ""
    notion_database_id: str = ""

    # Repository Configuration
    repository_type: str = "sqlite"  # "notion" or "sqlite"
    sqlite_db_path: str = "data/transactions.db"

    # Application Configuration
    default_category: str = "Uncategorized"
    log_level: str = "DEBUG"
    environment: str = "development"  # "development" or "production"

    # LLM Configuration (Unified for all providers)
    llm_provider: str = "ollama"  # "ollama", "openai", "anthropic", "google", "litellm"
    llm_model: str = "llama3.1:8b"  # Model identifier (provider-specific)
    llm_api_key: Optional[str] = None  # API key for commercial providers
    llm_base_url: Optional[str] = "http://supermicro:11434"  # Base URL (for Ollama or custom endpoints)
    llm_timeout: int = 300  # Request timeout in seconds
    llm_temperature: float = 0.1  # Sampling temperature (0.0 = deterministic, 1.0 = creative)
    llm_batch_size: int = 5  # Number of transactions to categorize in one batch
    ai_confidence_threshold: float = 0.7  # Transactions below this need review

    # Backward compatibility (deprecated, use llm_* fields instead)
    @property
    def ollama_base_url(self) -> str:
        """Deprecated: Use llm_base_url instead."""
        return self.llm_base_url or "http://supermicro:11434"

    @property
    def ollama_model(self) -> str:
        """Deprecated: Use llm_model instead."""
        return self.llm_model if self.llm_provider == "ollama" else "llama3.1:8b"

    @property
    def ollama_timeout(self) -> int:
        """Deprecated: Use llm_timeout instead."""
        return self.llm_timeout

    @property
    def ollama_batch_size(self) -> int:
        """Deprecated: Use llm_batch_size instead."""
        return self.llm_batch_size

    # Security
    encryption_key: Optional[str] = None

    def get_notion_token(self) -> str:
        """
        Get Notion token from environment or Docker Secret.

        Returns:
            Notion API token.

        Raises:
            ValueError: If token is not configured.
        """
        # Try Docker Secret first
        secret_file = os.environ.get("NOTION_TOKEN_FILE")
        if secret_file and os.path.exists(secret_file):
            with open(secret_file, "r") as f:
                return f.read().strip()

        # Fall back to environment variable
        if self.notion_token:
            return self.notion_token

        raise ValueError(
            "Notion token not configured. Set NOTION_TOKEN environment variable "
            "or NOTION_TOKEN_FILE for Docker Secrets."
        )

    def get_notion_database_id(self) -> str:
        """
        Get Notion database ID from environment or Docker Secret.

        Returns:
            Notion database ID.

        Raises:
            ValueError: If database ID is not configured.
        """
        # Try Docker Secret first
        secret_file = os.environ.get("NOTION_DATABASE_ID_FILE")
        if secret_file and os.path.exists(secret_file):
            with open(secret_file, "r") as f:
                return f.read().strip()

        # Fall back to environment variable
        if self.notion_database_id:
            return self.notion_database_id

        raise ValueError(
            "Notion database ID not configured. Set NOTION_DATABASE_ID environment variable "
            "or NOTION_DATABASE_ID_FILE for Docker Secrets."
        )

    def get_encryption_key(self) -> Optional[str]:
        """
        Get encryption key from environment or Docker Secret.

        Returns:
            Encryption key or None if not configured.
        """
        # Try Docker Secret first
        secret_file = os.environ.get("ENCRYPTION_KEY_FILE")
        if secret_file and os.path.exists(secret_file):
            with open(secret_file, "r") as f:
                return f.read().strip()

        # Fall back to environment variable
        return self.encryption_key

    def ensure_data_directory(self) -> None:
        """Ensure data directory exists for SQLite database."""
        db_path = Path(self.sqlite_db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"


# Global settings instance
settings = Settings()
