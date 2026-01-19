"""Unit tests for PDF parser."""

import pytest
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from src.infrastructure.parsers.pdf_parser import PDFParser, PDFParserError


class TestPDFParser:
    """Test suite for PDFParser."""

    @pytest.fixture
    def parser(self):
        """Create PDFParser instance."""
        return PDFParser()

    def test_normalize_date_various_formats(self, parser):
        """Test date normalization with various formats."""
        test_cases = [
            ("2025-01-19", "2025-01-19"),
            ("19-01-2025", "2025-01-19"),
            ("19/01/2025", "2025-01-19"),
            ("19 Jan 2025", "2025-01-19"),
            ("19 January 2025", "2025-01-19"),
        ]

        for input_date, expected in test_cases:
            result = parser._normalize_date(input_date)
            assert result == expected, f"Failed for {input_date}"

    def test_normalize_date_invalid(self, parser):
        """Test date normalization with invalid dates."""
        invalid_dates = ["invalid", "99-99-9999", ""]

        for invalid_date in invalid_dates:
            result = parser._normalize_date(invalid_date)
            assert result is None

    def test_normalize_amount_european_format(self, parser):
        """Test amount normalization with European format (1.234,56)."""
        test_cases = [
            ("€1.234,56", "1234.56"),
            ("1.234,56", "1234.56"),
            ("234,56", "234.56"),
            ("-234,56", "-234.56"),
            ("€-1.234,56", "-1234.56"),
        ]

        for input_amount, expected in test_cases:
            result = parser._normalize_amount(input_amount)
            assert result == expected, f"Failed for {input_amount}"

    def test_normalize_amount_us_format(self, parser):
        """Test amount normalization with US format (1,234.56)."""
        test_cases = [
            ("$1,234.56", "1234.56"),
            ("1,234.56", "1234.56"),
            ("234.56", "234.56"),
            ("-234.56", "-234.56"),
            ("$-1,234.56", "-1234.56"),
        ]

        for input_amount, expected in test_cases:
            result = parser._normalize_amount(input_amount)
            assert result == expected, f"Failed for {input_amount}"

    def test_normalize_amount_with_parentheses(self, parser):
        """Test amount normalization with parentheses for negatives."""
        test_cases = [
            ("(123.45)", "-123.45"),
            ("(€123.45)", "-123.45"),
            ("(1,234.56)", "-1234.56"),
        ]

        for input_amount, expected in test_cases:
            result = parser._normalize_amount(input_amount)
            assert result == expected, f"Failed for {input_amount}"

    def test_normalize_amount_brazilian_format(self, parser):
        """Test amount normalization with Brazilian format (R$ 1.234,56)."""
        test_cases = [
            ("R$ 1.234,56", "1234.56"),
            ("R$1.234,56", "1234.56"),
            ("R$ -1.234,56", "-1234.56"),
        ]

        for input_amount, expected in test_cases:
            result = parser._normalize_amount(input_amount)
            assert result == expected, f"Failed for {input_amount}"

    def test_normalize_amount_invalid(self, parser):
        """Test amount normalization with invalid amounts."""
        invalid_amounts = ["invalid", "abc.def", ""]

        for invalid_amount in invalid_amounts:
            result = parser._normalize_amount(invalid_amount)
            assert result is None

    def test_detect_columns_english(self, parser):
        """Test column detection with English headers."""
        header = ["Date", "Description", "Amount"]
        date_col, desc_col, amount_col = parser._detect_columns(header)

        assert date_col == 0
        assert desc_col == 1
        assert amount_col == 2

    def test_detect_columns_dutch(self, parser):
        """Test column detection with Dutch headers."""
        header = ["Datum", "Omschrijving", "Bedrag"]
        date_col, desc_col, amount_col = parser._detect_columns(header)

        assert date_col == 0
        assert desc_col == 1
        assert amount_col == 2

    def test_detect_columns_mixed_order(self, parser):
        """Test column detection with different column order."""
        header = ["Amount", "Date", "Name"]
        date_col, desc_col, amount_col = parser._detect_columns(header)

        assert date_col == 1
        assert desc_col == 2
        assert amount_col == 0

    def test_parse_table_valid_data(self, parser):
        """Test parsing valid table data."""
        table = [
            ["Date", "Description", "Amount"],
            ["2025-01-19", "Grocery Store", "-50.00"],
            ["2025-01-18", "Salary", "2500.00"],
        ]

        transactions = parser._parse_table(table)

        assert len(transactions) == 2
        assert transactions[0]["date"] == "2025-01-19"
        assert transactions[0]["description"] == "Grocery Store"
        assert transactions[0]["amount"] == "-50.00"
        assert transactions[1]["date"] == "2025-01-18"
        assert transactions[1]["description"] == "Salary"
        assert transactions[1]["amount"] == "2500.00"

    def test_parse_table_empty(self, parser):
        """Test parsing empty table."""
        table = []
        transactions = parser._parse_table(table)
        assert len(transactions) == 0

    def test_parse_table_header_only(self, parser):
        """Test parsing table with header only."""
        table = [["Date", "Description", "Amount"]]
        transactions = parser._parse_table(table)
        assert len(transactions) == 0

    def test_parse_table_invalid_rows(self, parser):
        """Test parsing table with some invalid rows."""
        table = [
            ["Date", "Description", "Amount"],
            ["2025-01-19", "Valid Transaction", "-50.00"],
            ["invalid-date", "Invalid Transaction", "-30.00"],  # Invalid date
            ["2025-01-18", "Missing Amount", None],  # Missing amount
            ["2025-01-17", "Valid Transaction 2", "100.00"],
        ]

        transactions = parser._parse_table(table)

        # Should only parse valid rows
        assert len(transactions) == 2
        assert transactions[0]["description"] == "Valid Transaction"
        assert transactions[1]["description"] == "Valid Transaction 2"

    def test_extract_transactions_nonexistent_file(self, parser):
        """Test extracting from non-existent file."""
        with pytest.raises(Exception):  # pdfplumber will raise an exception
            parser.extract_transactions(Path("/nonexistent/file.pdf"))

    def test_parse_text_with_transactions(self, parser):
        """Test parsing text with transactions."""
        text = """
        Bank Statement

        2025-01-19  Grocery Store Purchase     -50.00
        2025-01-18  Salary Deposit            2500.00
        2025-01-17  Restaurant Payment         -35.50

        Total: 2414.50
        """

        transactions = parser._parse_text(text)

        assert len(transactions) >= 3
        # Check first transaction
        assert transactions[0]["date"] == "2025-01-19"
        assert "Grocery" in transactions[0]["description"]
        assert "-50" in transactions[0]["amount"]

    def test_parse_text_no_transactions(self, parser):
        """Test parsing text with no transactions."""
        text = """
        This is a header with no transaction data.
        Just some random text.
        """

        transactions = parser._parse_text(text)
        assert len(transactions) == 0


class TestPDFParserIntegration:
    """Integration tests for PDFParser with actual PDF processing."""

    @pytest.fixture
    def parser(self):
        """Create PDFParser instance."""
        return PDFParser()

    @pytest.mark.skip(reason="Requires sample PDF file")
    def test_extract_from_real_pdf(self, parser):
        """Test extraction from real PDF file."""
        # This test requires a sample PDF file
        pdf_path = Path("tests/fixtures/pdfs/sample_statement.pdf")

        if not pdf_path.exists():
            pytest.skip("Sample PDF not available")

        transactions = parser.extract_transactions(pdf_path)

        assert len(transactions) > 0
        assert all("date" in txn for txn in transactions)
        assert all("description" in txn for txn in transactions)
        assert all("amount" in txn for txn in transactions)
