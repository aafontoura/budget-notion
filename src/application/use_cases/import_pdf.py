"""Use case for importing transactions from PDF bank statements."""

import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from src.application.dtos import CreateTransactionDTO, ImportPDFDTO
from src.application.services.categorization_service import CategorizationService
from src.application.use_cases.create_transaction import CreateTransactionUseCase
from src.domain.entities import Transaction
from src.domain.repositories import TransactionRepository
from src.infrastructure.parsers.pdf_parser import PDFParser, PDFParserError

logger = logging.getLogger(__name__)


class ImportPDFUseCase:
    """
    Use case for importing transactions from PDF bank statements.

    Workflow:
    1. Extract transactions from PDF (PDFParser)
    2. Categorize transactions using AI (CategorizationService)
    3. Validate and create transactions
    4. Return results with review status
    """

    def __init__(
        self,
        repository: TransactionRepository,
        pdf_parser: PDFParser,
        categorization_service: CategorizationService,
    ):
        """
        Initialize use case.

        Args:
            repository: Transaction repository.
            pdf_parser: PDF parser for transaction extraction.
            categorization_service: Service for AI categorization.
        """
        self.repository = repository
        self.pdf_parser = pdf_parser
        self.categorization_service = categorization_service
        self.create_transaction_use_case = CreateTransactionUseCase(repository)

    def execute(self, dto: ImportPDFDTO) -> dict:
        """
        Import transactions from PDF file.

        Args:
            dto: Import configuration.

        Returns:
            Dictionary with import statistics:
            {
                "total_parsed": int,
                "successful_imports": int,
                "failed_imports": int,
                "needs_review": int,  # Transactions with low confidence
                "transactions": list[Transaction]
            }

        Raises:
            ValueError: If PDF file is invalid or cannot be parsed.
            PDFParserError: If PDF extraction fails.
        """
        file_path = Path(dto.file_path)

        if not file_path.exists():
            raise ValueError(f"PDF file not found: {file_path}")

        logger.info(f"Importing transactions from PDF: {file_path}")

        # Step 1: Extract transactions from PDF
        try:
            raw_transactions = self.pdf_parser.extract_transactions(file_path)
            logger.info(f"Extracted {len(raw_transactions)} transactions from PDF")
        except PDFParserError as e:
            logger.error(f"PDF parsing failed: {e}")
            raise ValueError(f"Failed to parse PDF: {e}") from e

        if not raw_transactions:
            logger.warning("No transactions found in PDF")
            return {
                "total_parsed": 0,
                "successful_imports": 0,
                "failed_imports": 0,
                "needs_review": 0,
                "transactions": [],
            }

        # Step 2: Categorize transactions using AI (optimized batch mode)
        categorization_results = {}
        if dto.use_ai_categorization:
            logger.info("Starting AI categorization (optimized batch mode)...")
            try:
                # Assign temporary IDs to transactions for batch processing
                transactions_with_ids = []
                for i, raw_txn in enumerate(raw_transactions):
                    txn_with_id = {
                        "id": str(i),  # Use index as temporary ID
                        "description": raw_txn["description"],
                        "amount": raw_txn["amount"],
                        "date": raw_txn.get("date", ""),
                    }
                    transactions_with_ids.append(txn_with_id)

                # Use optimized batch categorization
                categorization_results = (
                    self.categorization_service.categorize_batch_optimized(
                        transactions_with_ids
                    )
                )
                logger.info(
                    f"Categorized {len(categorization_results)} transactions "
                    f"using optimized batching"
                )
            except Exception as e:
                logger.error(f"AI categorization failed: {e}")
                # Continue with default categorization
                logger.warning("Falling back to default categorization (Miscellaneous)")

        # Step 3: Import transactions
        imported_transactions = []
        failed_count = 0
        needs_review_count = 0

        for i, raw_txn in enumerate(raw_transactions):
            try:
                # Parse date
                date = self._parse_date(raw_txn["date"])
                if not date:
                    logger.warning(f"Invalid date for transaction: {raw_txn}")
                    failed_count += 1
                    continue

                # Parse amount
                amount = self._parse_amount(raw_txn["amount"])
                if amount is None:
                    logger.warning(f"Invalid amount for transaction: {raw_txn}")
                    failed_count += 1
                    continue

                # Get categorization result (if available)
                txn_id = str(i)
                if txn_id in categorization_results:
                    result = categorization_results[txn_id]
                    category = result.category
                    subcategory = result.subcategory
                    ai_confidence = result.confidence
                else:
                    # Fallback to default
                    category = "Miscellaneous"
                    subcategory = "Uncategorized"
                    ai_confidence = 0.0

                # Create transaction DTO
                transaction_dto = CreateTransactionDTO(
                    date=date,
                    description=raw_txn["description"],
                    amount=amount,
                    category=category,
                    subcategory=subcategory,
                    ai_confidence=ai_confidence,
                    account=dto.account_name,
                    notes=None,
                )

                # Save transaction
                saved_transaction = self.create_transaction_use_case.execute(
                    transaction_dto, ai_confidence
                )
                imported_transactions.append(saved_transaction)

                # Track if needs review
                if saved_transaction.needs_review:
                    needs_review_count += 1

                logger.debug(
                    f"Imported: {saved_transaction.description} → "
                    f"{category}/{subcategory} (confidence: {ai_confidence:.2f})"
                )

            except Exception as e:
                logger.warning(f"Failed to import transaction: {e}")
                logger.debug(f"Transaction data: {raw_txn}")
                failed_count += 1
                continue

        # Log summary
        logger.info(
            f"Import complete: {len(imported_transactions)} successful, "
            f"{failed_count} failed, {needs_review_count} need review "
            f"(out of {len(raw_transactions)} total)"
        )

        return {
            "total_parsed": len(raw_transactions),
            "successful_imports": len(imported_transactions),
            "failed_imports": failed_count,
            "needs_review": needs_review_count,
            "transactions": imported_transactions,
        }

    def _parse_date(self, date_str: str) -> datetime | None:
        """
        Parse date string to datetime.

        Args:
            date_str: Date string in YYYY-MM-DD format.

        Returns:
            Datetime object or None if parsing fails.
        """
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            logger.debug(f"Failed to parse date: {date_str}")
            return None

    def _parse_amount(self, amount_str: str) -> Decimal | None:
        """
        Parse amount string to Decimal.

        Args:
            amount_str: Amount string (e.g., "123.45" or "-123.45").

        Returns:
            Decimal object or None if parsing fails.
        """
        try:
            return Decimal(amount_str)
        except Exception:
            logger.debug(f"Failed to parse amount: {amount_str}")
            return None
