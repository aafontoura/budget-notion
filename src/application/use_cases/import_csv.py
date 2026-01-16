"""Use case for importing transactions from CSV."""

import logging
from pathlib import Path

from src.application.dtos import CreateTransactionDTO, ImportCSVDTO
from src.application.use_cases.create_transaction import CreateTransactionUseCase
from src.domain.entities import Transaction
from src.domain.repositories import TransactionRepository
from src.infrastructure.parsers import (
    CSVParser,
    CSVParserConfig,
    get_dutch_bank_configs,
    get_international_bank_configs,
)

logger = logging.getLogger(__name__)


class ImportCSVUseCase:
    """
    Use case for importing transactions from CSV files.

    Handles parsing bank statements and creating transactions.
    """

    def __init__(self, repository: TransactionRepository):
        """
        Initialize use case.

        Args:
            repository: Transaction repository.
        """
        self.repository = repository
        self.create_transaction_use_case = CreateTransactionUseCase(repository)

    def execute(self, dto: ImportCSVDTO) -> dict:
        """
        Import transactions from CSV file.

        Args:
            dto: Import configuration.

        Returns:
            Dictionary with import statistics:
            {
                "total_parsed": int,
                "successful_imports": int,
                "failed_imports": int,
                "transactions": list[Transaction]
            }

        Raises:
            ValueError: If CSV file is invalid or cannot be parsed.
        """
        file_path = Path(dto.file_path)

        if not file_path.exists():
            raise ValueError(f"CSV file not found: {file_path}")

        # Get parser configuration
        parser_config = self._get_parser_config(dto.bank_config)
        parser = CSVParser(parser_config)

        logger.info(f"Importing transactions from {file_path}")

        # Parse CSV file
        parsed_transactions = parser.parse(
            file_path=file_path,
            default_category=dto.default_category,
            account_name=dto.account_name,
        )

        # Import parsed transactions
        imported_transactions = []
        failed_count = 0

        for transaction in parsed_transactions:
            try:
                # Convert to DTO
                transaction_dto = CreateTransactionDTO(
                    date=transaction.date,
                    description=transaction.description,
                    amount=transaction.amount,
                    category=transaction.category,
                    account=transaction.account,
                    notes=transaction.notes,
                )

                # Create transaction
                saved_transaction = self.create_transaction_use_case.execute(transaction_dto)
                imported_transactions.append(saved_transaction)

            except Exception as e:
                logger.warning(f"Failed to import transaction: {e}")
                failed_count += 1
                continue

        # Log summary
        logger.info(
            f"Import complete: {len(imported_transactions)} successful, "
            f"{failed_count} failed out of {len(parsed_transactions)} total"
        )

        return {
            "total_parsed": len(parsed_transactions),
            "successful_imports": len(imported_transactions),
            "failed_imports": failed_count,
            "transactions": imported_transactions,
        }

    def _get_parser_config(self, bank_config: str | None) -> CSVParserConfig:
        """
        Get parser configuration for specified bank.

        Args:
            bank_config: Bank configuration name (e.g., "ing", "rabobank").

        Returns:
            CSV parser configuration.
        """
        if not bank_config:
            # Return default configuration
            return CSVParserConfig()

        # Get all available configs
        all_configs = {
            **get_dutch_bank_configs(),
            **get_international_bank_configs(),
        }

        config = all_configs.get(bank_config.lower())

        if not config:
            available_banks = list(all_configs.keys())
            logger.warning(
                f"Unknown bank config '{bank_config}'. "
                f"Available: {available_banks}. Using default."
            )
            return CSVParserConfig()

        logger.info(f"Using parser config for: {bank_config}")
        return config
