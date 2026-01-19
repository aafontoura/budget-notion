"""Integration tests for PDF import workflow."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from src.application.dtos import ImportPDFDTO
from src.application.services.categorization_service import CategorizationService
from src.application.use_cases.import_pdf import ImportPDFUseCase
from src.infrastructure.ai.ollama_client import OllamaClient
from src.infrastructure.ai.prompt_builder import CategorizationPromptBuilder
from src.infrastructure.ai.response_parser import (
    CategorizationResponseParser,
    CategorizationResult,
)
from src.infrastructure.parsers.pdf_parser import PDFParser


class TestPDFImportIntegration:
    """Integration tests for PDF import workflow with sample PDFs."""

    @pytest.fixture
    def fixtures_path(self):
        """Get path to PDF fixtures."""
        return Path(__file__).parent.parent / "fixtures" / "pdfs"

    @pytest.fixture
    def pdf_parser(self):
        """Create real PDF parser."""
        return PDFParser()

    @pytest.fixture
    def mock_repository(self):
        """Create mock repository."""
        return Mock()

    @pytest.fixture
    def mock_ollama_client(self):
        """Create mock Ollama client for testing without real server."""
        client = Mock(spec=OllamaClient)
        # Mock category responses
        client.generate.return_value = '{"category": "FOOD & GROCERIES", "confidence": 0.95}'
        return client

    @pytest.fixture
    def categorization_service(self, mock_ollama_client):
        """Create categorization service with mock Ollama client."""
        prompt_builder = CategorizationPromptBuilder()
        response_parser = CategorizationResponseParser()
        return CategorizationService(
            ollama_client=mock_ollama_client,
            prompt_builder=prompt_builder,
            response_parser=response_parser,
            batch_size=5,
            confidence_threshold=0.7
        )

    @pytest.fixture
    def import_use_case(self, mock_repository, pdf_parser, categorization_service):
        """Create import PDF use case."""
        return ImportPDFUseCase(
            repository=mock_repository,
            pdf_parser=pdf_parser,
            categorization_service=categorization_service
        )

    def test_extract_simple_statement(self, pdf_parser, fixtures_path):
        """Test extracting transactions from simple statement."""
        pdf_path = fixtures_path / "simple_statement.pdf"

        if not pdf_path.exists():
            pytest.skip("Sample PDF not generated yet")

        transactions = pdf_parser.extract_transactions(pdf_path)

        # Verify basic extraction
        assert len(transactions) > 0
        assert all("date" in txn for txn in transactions)
        assert all("description" in txn for txn in transactions)
        assert all("amount" in txn for txn in transactions)

        # Verify specific transactions
        descriptions = [txn["description"] for txn in transactions]
        assert any("Albert Heijn" in desc for desc in descriptions)
        assert any("Shell" in desc or "Gas" in desc for desc in descriptions)

    def test_extract_dutch_statement(self, pdf_parser, fixtures_path):
        """Test extracting transactions from Dutch ABN AMRO statement."""
        pdf_path = fixtures_path / "abn_amro_statement.pdf"

        if not pdf_path.exists():
            pytest.skip("Sample PDF not generated yet")

        transactions = pdf_parser.extract_transactions(pdf_path)

        # Verify extraction
        assert len(transactions) > 0

        # Check Dutch format dates are normalized to YYYY-MM-DD
        assert all(txn["date"].count("-") == 2 for txn in transactions)

        # Check amounts are normalized (European comma format)
        amounts = [txn["amount"] for txn in transactions]
        assert len(amounts) > 0
        # Should have both positive and negative amounts
        positive = [a for a in amounts if not a.startswith("-")]
        negative = [a for a in amounts if a.startswith("-")]
        assert len(positive) > 0
        assert len(negative) > 0

    def test_extract_mixed_format_statement(self, pdf_parser, fixtures_path):
        """Test extracting transactions with mixed date/amount formats."""
        pdf_path = fixtures_path / "mixed_format_statement.pdf"

        if not pdf_path.exists():
            pytest.skip("Sample PDF not generated yet")

        transactions = pdf_parser.extract_transactions(pdf_path)

        # Verify extraction handles multiple formats
        assert len(transactions) > 0

        # All dates should be normalized to YYYY-MM-DD
        for txn in transactions:
            assert txn["date"].count("-") == 2
            parts = txn["date"].split("-")
            assert len(parts[0]) == 4  # Year is 4 digits
            assert len(parts[1]) == 2  # Month is 2 digits
            assert len(parts[2]) == 2  # Day is 2 digits

    @pytest.mark.integration
    def test_full_import_workflow_simple_statement(self, import_use_case, fixtures_path, mock_repository):
        """Test full import workflow with simple statement."""
        pdf_path = fixtures_path / "simple_statement.pdf"

        if not pdf_path.exists():
            pytest.skip("Sample PDF not generated yet")

        dto = ImportPDFDTO(
            file_path=str(pdf_path),
            account_name="Test Account",
            use_ai_categorization=True,
            confidence_threshold=0.7
        )

        # Mock transaction creation
        from src.domain.entities import Transaction
        from datetime import datetime
        from decimal import Decimal

        def create_mock_transaction(dto, ai_confidence):
            return Transaction(
                id=f"txn-{datetime.now().timestamp()}",
                date=dto.date,
                description=dto.description,
                amount=dto.amount,
                category=dto.category,
                subcategory=dto.subcategory,
                ai_confidence=ai_confidence,
                account=dto.account,
                reviewed=False,
            )

        with patch.object(import_use_case.create_transaction_use_case, 'execute') as mock_execute:
            mock_execute.side_effect = create_mock_transaction

            result = import_use_case.execute(dto)

            # Verify results
            assert result["total_parsed"] > 0
            assert result["successful_imports"] > 0
            assert result["failed_imports"] == 0
            assert len(result["transactions"]) == result["successful_imports"]

            # Verify transactions have required fields
            for txn in result["transactions"]:
                assert txn.date is not None
                assert txn.description is not None
                assert txn.amount is not None
                assert txn.category is not None
                assert txn.account == "Test Account"

    @pytest.mark.integration
    def test_full_import_workflow_without_ai(self, import_use_case, fixtures_path):
        """Test full import workflow without AI categorization."""
        pdf_path = fixtures_path / "simple_statement.pdf"

        if not pdf_path.exists():
            pytest.skip("Sample PDF not generated yet")

        dto = ImportPDFDTO(
            file_path=str(pdf_path),
            use_ai_categorization=False  # Disable AI
        )

        from src.domain.entities import Transaction
        from datetime import datetime

        def create_mock_transaction(dto, ai_confidence):
            return Transaction(
                id=f"txn-{datetime.now().timestamp()}",
                date=dto.date,
                description=dto.description,
                amount=dto.amount,
                category=dto.category,
                subcategory=dto.subcategory,
                ai_confidence=0.0,
                account=dto.account,
                reviewed=False,
            )

        with patch.object(import_use_case.create_transaction_use_case, 'execute') as mock_execute:
            mock_execute.side_effect = create_mock_transaction

            result = import_use_case.execute(dto)

            # Verify results
            assert result["successful_imports"] > 0

            # All transactions should have default categorization
            for txn in result["transactions"]:
                assert txn.category == "Miscellaneous"
                assert txn.ai_confidence == 0.0

    @pytest.mark.integration
    @pytest.mark.skipif(
        not Path(__file__).parent.parent / "fixtures" / "pdfs" / "simple_statement.pdf",
        reason="Sample PDFs not available"
    )
    def test_pdf_extraction_performance(self, pdf_parser, fixtures_path):
        """Test PDF extraction performance with simple statement."""
        import time

        pdf_path = fixtures_path / "simple_statement.pdf"

        start_time = time.time()
        transactions = pdf_parser.extract_transactions(pdf_path)
        elapsed = time.time() - start_time

        # Extraction should be fast (< 5 seconds for small PDF)
        assert elapsed < 5.0, f"PDF extraction took {elapsed:.2f}s (expected < 5s)"
        assert len(transactions) > 0

    @pytest.mark.real_ollama
    @pytest.mark.skip(reason="Requires real Ollama server - run manually")
    def test_full_workflow_with_real_ollama(self, fixtures_path, mock_repository):
        """Test full workflow with real Ollama server (manual test)."""
        # This test requires a real Ollama server running
        # Run with: pytest -m real_ollama tests/test_integration/test_pdf_import_integration.py

        pdf_path = fixtures_path / "simple_statement.pdf"

        if not pdf_path.exists():
            pytest.skip("Sample PDF not generated yet")

        # Create real components (no mocks)
        pdf_parser = PDFParser()
        ollama_client = OllamaClient(
            base_url="http://supermicro:11434",
            model="llama3.1:8b",
            timeout=60
        )
        prompt_builder = CategorizationPromptBuilder()
        response_parser = CategorizationResponseParser()

        categorization_service = CategorizationService(
            ollama_client=ollama_client,
            prompt_builder=prompt_builder,
            response_parser=response_parser,
            batch_size=5,
            confidence_threshold=0.7
        )

        import_use_case = ImportPDFUseCase(
            repository=mock_repository,
            pdf_parser=pdf_parser,
            categorization_service=categorization_service
        )

        dto = ImportPDFDTO(
            file_path=str(pdf_path),
            account_name="Test Account",
            use_ai_categorization=True
        )

        from src.domain.entities import Transaction
        from datetime import datetime

        def create_mock_transaction(dto, ai_confidence):
            return Transaction(
                id=f"txn-{datetime.now().timestamp()}",
                date=dto.date,
                description=dto.description,
                amount=dto.amount,
                category=dto.category,
                subcategory=dto.subcategory,
                ai_confidence=ai_confidence,
                account=dto.account,
                reviewed=False,
            )

        with patch.object(import_use_case.create_transaction_use_case, 'execute') as mock_execute:
            mock_execute.side_effect = create_mock_transaction

            # Test connection first
            assert categorization_service.test_connection(), "Cannot connect to Ollama server"

            result = import_use_case.execute(dto)

            # Verify results
            assert result["successful_imports"] > 0
            print(f"\n✓ Successfully imported {result['successful_imports']} transactions")

            # Verify AI categorization worked
            for txn in result["transactions"]:
                print(f"  - {txn.description[:40]:40} → {txn.category:20} "
                      f"(confidence: {txn.ai_confidence:.0%})")
                assert txn.category != "Miscellaneous" or txn.ai_confidence == 0.0
