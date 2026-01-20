"""Dependency injection container."""

import logging

from dependency_injector import containers, providers
from notion_client import Client

from config.settings import Settings
from src.application.services.categorization_service import CategorizationService
from src.application.use_cases import (
    CreateTransactionUseCase,
    ImportCSVUseCase,
    UpdateReimbursementUseCase,
)
from src.application.use_cases.import_camt053 import ImportCAMT053UseCase
from src.application.use_cases.import_pdf import ImportPDFUseCase
from src.infrastructure.ai.ollama_client import OllamaClient
from src.infrastructure.ai.prompt_builder import CategorizationPromptBuilder
from src.infrastructure.ai.response_parser import CategorizationResponseParser
from src.infrastructure.parsers.camt053_parser import CAMT053Parser
from src.infrastructure.parsers.pdf_parser import PDFParser
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
        auth=config.provided.get_notion_token.call(),
    )

    # Transaction Repository (conditional based on config)
    transaction_repository = providers.Selector(
        config.provided.repository_type,
        notion=providers.Singleton(
            NotionTransactionRepository,
            client=notion_client,
            database_id=config.provided.get_notion_database_id.call(),
        ),
        sqlite=providers.Singleton(
            SQLiteTransactionRepository,
            db_path=config.provided.sqlite_db_path,
        ),
    )

    # Parsers
    pdf_parser = providers.Singleton(PDFParser)
    camt053_parser = providers.Singleton(CAMT053Parser)

    # Ollama LLM Client
    ollama_client = providers.Singleton(
        OllamaClient,
        base_url=config.provided.ollama_base_url,
        model=config.provided.ollama_model,
        timeout=config.provided.ollama_timeout,
    )

    # AI Categorization Components
    prompt_builder = providers.Singleton(CategorizationPromptBuilder)

    response_parser = providers.Singleton(CategorizationResponseParser)

    categorization_service = providers.Singleton(
        CategorizationService,
        ollama_client=ollama_client,
        prompt_builder=prompt_builder,
        response_parser=response_parser,
        batch_size=config.provided.ollama_batch_size,
        confidence_threshold=config.provided.ai_confidence_threshold,
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

    import_pdf_use_case = providers.Factory(
        ImportPDFUseCase,
        repository=transaction_repository,
        pdf_parser=pdf_parser,
        categorization_service=categorization_service,
    )

    import_camt053_use_case = providers.Factory(
        ImportCAMT053UseCase,
        repository=transaction_repository,
        camt053_parser=camt053_parser,
        categorization_service=categorization_service,
    )

    update_reimbursement_use_case = providers.Factory(
        UpdateReimbursementUseCase,
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
