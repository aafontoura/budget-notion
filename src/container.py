"""Dependency injection container."""

import logging

from dependency_injector import containers, providers
from notion_client import Client

from config.settings import Settings
from src.application.use_cases import CreateTransactionUseCase, ImportCSVUseCase
from src.infrastructure.repositories import (
    NotionTransactionRepository,
    SQLiteTransactionRepository,
)

logger = logging.getLogger(__name__)


class Container(containers.DeclarativeContainer):
    """
    Dependency injection container.

    Manages application dependencies and their lifecycles.
    Enables easy swapping of implementations (e.g., Notion → SQLite).
    """

    # Configuration
    config = providers.Singleton(Settings)

    # Notion Client (only if using Notion repository)
    notion_client = providers.Singleton(
        Client,
        auth=config.provided.get_notion_token,
    )

    # Transaction Repository (conditional based on config)
    transaction_repository = providers.Selector(
        config.provided.repository_type,
        notion=providers.Singleton(
            NotionTransactionRepository,
            client=notion_client,
            database_id=config.provided.get_notion_database_id,
        ),
        sqlite=providers.Singleton(
            SQLiteTransactionRepository,
            db_path=config.provided.sqlite_db_path,
        ),
    )

    # Use Cases
    create_transaction_use_case = providers.Factory(
        CreateTransactionUseCase,
        repository=transaction_repository,
    )

    import_csv_use_case = providers.Factory(
        ImportCSVUseCase,
        repository=transaction_repository,
    )


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure application logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
