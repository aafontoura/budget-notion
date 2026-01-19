"""Unit tests for import PDF use case."""

import pytest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from src.application.dtos import ImportPDFDTO
from src.application.use_cases.import_pdf import ImportPDFUseCase
from src.infrastructure.ai.response_parser import CategorizationResult
from src.infrastructure.parsers.pdf_parser import PDFParserError


class TestImportPDFUseCase:
    """Test suite for ImportPDFUseCase."""

    @pytest.fixture
    def mock_repository(self):
        """Create mock repository."""
        return Mock()

    @pytest.fixture
    def mock_pdf_parser(self):
        """Create mock PDF parser."""
        return Mock()

    @pytest.fixture
    def mock_categorization_service(self):
        """Create mock categorization service."""
        return Mock()

    @pytest.fixture
    def use_case(self, mock_repository, mock_pdf_parser, mock_categorization_service):
        """Create ImportPDFUseCase instance."""
        return ImportPDFUseCase(
            repository=mock_repository,
            pdf_parser=mock_pdf_parser,
            categorization_service=mock_categorization_service
        )

    @pytest.fixture
    def sample_pdf_path(self, tmp_path):
        """Create a sample PDF file path."""
        pdf_file = tmp_path / "test_statement.pdf"
        pdf_file.write_text("dummy pdf content")
        return str(pdf_file)

    def test_execute_nonexistent_file(self, use_case):
        """Test import with non-existent file."""
        dto = ImportPDFDTO(file_path="/nonexistent/file.pdf")

        with pytest.raises(ValueError, match="PDF file not found"):
            use_case.execute(dto)

    def test_execute_pdf_parsing_error(self, use_case, mock_pdf_parser, sample_pdf_path):
        """Test import with PDF parsing error."""
        dto = ImportPDFDTO(file_path=sample_pdf_path)
        mock_pdf_parser.extract_transactions.side_effect = PDFParserError("Parse failed")

        with pytest.raises(ValueError, match="Failed to parse PDF"):
            use_case.execute(dto)

    def test_execute_no_transactions_found(self, use_case, mock_pdf_parser, sample_pdf_path):
        """Test import when no transactions are found."""
        dto = ImportPDFDTO(file_path=sample_pdf_path)
        mock_pdf_parser.extract_transactions.return_value = []

        result = use_case.execute(dto)

        assert result["total_parsed"] == 0
        assert result["successful_imports"] == 0
        assert result["failed_imports"] == 0
        assert result["needs_review"] == 0
        assert result["transactions"] == []

    def test_execute_success_with_ai(self, use_case, mock_pdf_parser, mock_categorization_service, mock_repository, sample_pdf_path):
        """Test successful import with AI categorization."""
        # Setup DTO
        dto = ImportPDFDTO(
            file_path=sample_pdf_path,
            account_name="Test Account",
            use_ai_categorization=True,
            confidence_threshold=0.7
        )

        # Mock PDF extraction
        raw_transactions = [
            {"date": "2025-01-19", "description": "Albert Heijn", "amount": "-50.00"},
            {"date": "2025-01-18", "description": "Gas Station", "amount": "-60.00"},
        ]
        mock_pdf_parser.extract_transactions.return_value = raw_transactions

        # Mock AI categorization
        categorization_results = [
            CategorizationResult("FOOD & GROCERIES", "Groceries", 0.95, "{}"),
            CategorizationResult("TRANSPORTATION", "Car Fuel", 0.85, "{}"),
        ]
        mock_categorization_service.categorize_batch.return_value = categorization_results

        # Mock repository save
        from src.domain.entities import Transaction
        saved_transactions = []
        for i, raw_txn in enumerate(raw_transactions):
            txn = Transaction(
                id=f"txn-{i}",
                date=datetime.strptime(raw_txn["date"], "%Y-%m-%d"),
                description=raw_txn["description"],
                amount=Decimal(raw_txn["amount"]),
                category=categorization_results[i].category,
                subcategory=categorization_results[i].subcategory,
                ai_confidence=categorization_results[i].confidence,
                account="Test Account",
                reviewed=False,
            )
            saved_transactions.append(txn)

        # Mock create_transaction_use_case
        with patch.object(use_case.create_transaction_use_case, 'execute') as mock_execute:
            mock_execute.side_effect = saved_transactions

            result = use_case.execute(dto)

            # Verify results
            assert result["total_parsed"] == 2
            assert result["successful_imports"] == 2
            assert result["failed_imports"] == 0
            assert result["needs_review"] == 0  # Both above threshold
            assert len(result["transactions"]) == 2

            # Verify AI categorization was called
            mock_categorization_service.categorize_batch.assert_called_once_with(raw_transactions)

    def test_execute_success_without_ai(self, use_case, mock_pdf_parser, mock_categorization_service, mock_repository, sample_pdf_path):
        """Test successful import without AI categorization."""
        dto = ImportPDFDTO(
            file_path=sample_pdf_path,
            use_ai_categorization=False
        )

        raw_transactions = [
            {"date": "2025-01-19", "description": "Test", "amount": "-50.00"},
        ]
        mock_pdf_parser.extract_transactions.return_value = raw_transactions

        from src.domain.entities import Transaction
        saved_txn = Transaction(
            id="txn-1",
            date=datetime(2025, 1, 19),
            description="Test",
            amount=Decimal("-50.00"),
            category="Miscellaneous",
            subcategory="Uncategorized",
            ai_confidence=0.0,
            reviewed=False,
        )

        with patch.object(use_case.create_transaction_use_case, 'execute') as mock_execute:
            mock_execute.return_value = saved_txn

            result = use_case.execute(dto)

            # Verify AI was not used
            mock_categorization_service.categorize_batch.assert_not_called()

            # Verify default categorization
            assert result["successful_imports"] == 1
            assert result["transactions"][0].category == "Miscellaneous"

    def test_execute_with_low_confidence_transactions(self, use_case, mock_pdf_parser, mock_categorization_service, sample_pdf_path):
        """Test import with low confidence transactions."""
        dto = ImportPDFDTO(
            file_path=sample_pdf_path,
            confidence_threshold=0.7
        )

        raw_transactions = [
            {"date": "2025-01-19", "description": "Test 1", "amount": "-50.00"},
            {"date": "2025-01-18", "description": "Test 2", "amount": "-60.00"},
        ]
        mock_pdf_parser.extract_transactions.return_value = raw_transactions

        # One high confidence, one low confidence
        categorization_results = [
            CategorizationResult("FOOD & GROCERIES", "Groceries", 0.95, "{}"),  # High
            CategorizationResult("TRANSPORTATION", "Car Fuel", 0.50, "{}"),  # Low
        ]
        mock_categorization_service.categorize_batch.return_value = categorization_results

        from src.domain.entities import Transaction
        saved_transactions = [
            Transaction(
                id="txn-1",
                date=datetime(2025, 1, 19),
                description="Test 1",
                amount=Decimal("-50.00"),
                category="FOOD & GROCERIES",
                ai_confidence=0.95,
                reviewed=False,
            ),
            Transaction(
                id="txn-2",
                date=datetime(2025, 1, 18),
                description="Test 2",
                amount=Decimal("-60.00"),
                category="TRANSPORTATION",
                ai_confidence=0.50,
                reviewed=False,
            ),
        ]

        with patch.object(use_case.create_transaction_use_case, 'execute') as mock_execute:
            mock_execute.side_effect = saved_transactions

            result = use_case.execute(dto)

            assert result["successful_imports"] == 2
            assert result["needs_review"] == 1  # One transaction below threshold

    def test_execute_with_invalid_date(self, use_case, mock_pdf_parser, sample_pdf_path):
        """Test import with invalid date."""
        dto = ImportPDFDTO(file_path=sample_pdf_path, use_ai_categorization=False)

        raw_transactions = [
            {"date": "invalid-date", "description": "Test", "amount": "-50.00"},
        ]
        mock_pdf_parser.extract_transactions.return_value = raw_transactions

        result = use_case.execute(dto)

        assert result["total_parsed"] == 1
        assert result["successful_imports"] == 0
        assert result["failed_imports"] == 1

    def test_execute_with_invalid_amount(self, use_case, mock_pdf_parser, sample_pdf_path):
        """Test import with invalid amount."""
        dto = ImportPDFDTO(file_path=sample_pdf_path, use_ai_categorization=False)

        raw_transactions = [
            {"date": "2025-01-19", "description": "Test", "amount": "invalid"},
        ]
        mock_pdf_parser.extract_transactions.return_value = raw_transactions

        result = use_case.execute(dto)

        assert result["total_parsed"] == 1
        assert result["successful_imports"] == 0
        assert result["failed_imports"] == 1

    def test_execute_ai_categorization_fails(self, use_case, mock_pdf_parser, mock_categorization_service, sample_pdf_path):
        """Test import when AI categorization fails."""
        dto = ImportPDFDTO(file_path=sample_pdf_path, use_ai_categorization=True)

        raw_transactions = [
            {"date": "2025-01-19", "description": "Test", "amount": "-50.00"},
        ]
        mock_pdf_parser.extract_transactions.return_value = raw_transactions

        # AI categorization fails
        mock_categorization_service.categorize_batch.side_effect = Exception("AI failed")

        from src.domain.entities import Transaction
        saved_txn = Transaction(
            id="txn-1",
            date=datetime(2025, 1, 19),
            description="Test",
            amount=Decimal("-50.00"),
            category="Miscellaneous",
            ai_confidence=0.0,
            reviewed=False,
        )

        with patch.object(use_case.create_transaction_use_case, 'execute') as mock_execute:
            mock_execute.return_value = saved_txn

            result = use_case.execute(dto)

            # Should fallback to default categorization
            assert result["successful_imports"] == 1
            assert result["transactions"][0].category == "Miscellaneous"

    def test_parse_date_valid(self, use_case):
        """Test date parsing with valid date."""
        result = use_case._parse_date("2025-01-19")
        assert result == datetime(2025, 1, 19)

    def test_parse_date_invalid(self, use_case):
        """Test date parsing with invalid date."""
        result = use_case._parse_date("invalid-date")
        assert result is None

    def test_parse_amount_valid(self, use_case):
        """Test amount parsing with valid amount."""
        result = use_case._parse_amount("-50.00")
        assert result == Decimal("-50.00")

    def test_parse_amount_invalid(self, use_case):
        """Test amount parsing with invalid amount."""
        result = use_case._parse_amount("invalid")
        assert result is None
