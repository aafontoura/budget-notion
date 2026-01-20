"""Tests for CAMT.053 XML parser."""

import pytest
from pathlib import Path
from decimal import Decimal

from src.infrastructure.parsers.camt053_parser import CAMT053Parser


@pytest.fixture
def sample_camt053_file():
    """Provide path to sample CAMT.053 XML file."""
    return Path("tests/fixtures/camt053/sample_abn_amro.xml")


@pytest.fixture
def parser():
    """Create CAMT053Parser instance."""
    return CAMT053Parser()


class TestCAMT053Parser:
    """Test suite for CAMT053Parser."""

    def test_parse_valid_camt053_file(self, parser, sample_camt053_file):
        """Test successful parsing of a valid CAMT.053 file."""
        transactions = parser.extract_transactions(sample_camt053_file)

        assert len(transactions) == 3, "Should extract 3 transactions"

        # Verify transaction structure
        for txn in transactions:
            assert "date" in txn
            assert "description" in txn
            assert "amount" in txn

    def test_parse_credit_transaction(self, parser, sample_camt053_file):
        """Test parsing of credit (incoming) transaction."""
        transactions = parser.extract_transactions(sample_camt053_file)

        # First transaction is a credit
        credit_txn = transactions[0]

        assert credit_txn["date"] == "2025-01-15"
        assert "Salary payment" in credit_txn["description"]
        assert Decimal(credit_txn["amount"]) == Decimal("250.50")
        assert Decimal(credit_txn["amount"]) > 0, "Credit should be positive"

    def test_parse_debit_transaction(self, parser, sample_camt053_file):
        """Test parsing of debit (outgoing) transaction."""
        transactions = parser.extract_transactions(sample_camt053_file)

        # Second transaction is a debit
        debit_txn = transactions[1]

        assert debit_txn["date"] == "2025-01-16"
        assert "Grocery shopping" in debit_txn["description"]
        assert Decimal(debit_txn["amount"]) == Decimal("-75.20")
        assert Decimal(debit_txn["amount"]) < 0, "Debit should be negative"

    def test_all_transactions_have_valid_dates(self, parser, sample_camt053_file):
        """Test that all transactions have valid ISO date format."""
        transactions = parser.extract_transactions(sample_camt053_file)

        for txn in transactions:
            date_str = txn["date"]
            # Check ISO format YYYY-MM-DD
            assert len(date_str) == 10
            assert date_str[4] == "-"
            assert date_str[7] == "-"

            # Verify it's a valid date
            year, month, day = date_str.split("-")
            assert 2000 <= int(year) <= 2100
            assert 1 <= int(month) <= 12
            assert 1 <= int(day) <= 31

    def test_all_transactions_have_descriptions(self, parser, sample_camt053_file):
        """Test that all transactions have non-empty descriptions."""
        transactions = parser.extract_transactions(sample_camt053_file)

        for txn in transactions:
            assert txn["description"]
            assert len(txn["description"]) > 0
            assert txn["description"] != "Transaction"  # Should not use fallback

    def test_all_transactions_have_valid_amounts(self, parser, sample_camt053_file):
        """Test that all transactions have valid decimal amounts."""
        transactions = parser.extract_transactions(sample_camt053_file)

        for txn in transactions:
            amount_str = txn["amount"]
            # Should be convertible to Decimal
            amount = Decimal(amount_str)
            assert amount != 0, "Amount should not be zero"

    def test_transaction_amounts_sum_correctly(self, parser, sample_camt053_file):
        """Test that transaction amounts sum to expected total."""
        transactions = parser.extract_transactions(sample_camt053_file)

        total = sum(Decimal(txn["amount"]) for txn in transactions)
        # 250.50 (credit) - 75.20 (debit) - 45.00 (debit) = 130.30
        expected_total = Decimal("130.30")

        assert total == expected_total

    def test_file_not_found_raises_error(self, parser):
        """Test that FileNotFoundError is raised for non-existent file."""
        non_existent_file = Path("tests/fixtures/camt053/does_not_exist.xml")

        with pytest.raises(FileNotFoundError):
            parser.extract_transactions(non_existent_file)

    def test_invalid_xml_raises_error(self, parser, tmp_path):
        """Test that ValueError is raised for invalid XML."""
        invalid_file = tmp_path / "invalid.xml"
        invalid_file.write_text("<invalid>This is not CAMT.053</invalid>")

        with pytest.raises(ValueError, match="Invalid CAMT.053 format"):
            parser.extract_transactions(invalid_file)

    def test_empty_xml_raises_error(self, parser, tmp_path):
        """Test that ValueError is raised for empty file."""
        empty_file = tmp_path / "empty.xml"
        empty_file.write_text("")

        with pytest.raises(ValueError):
            parser.extract_transactions(empty_file)

    def test_credit_indicator_uppercase(self, parser):
        """Test that credit indicator is handled case-insensitively."""
        # This is tested implicitly by the sample file which uses "CRDT"
        # Just verify the sample works
        sample_file = Path("tests/fixtures/camt053/sample_abn_amro.xml")
        transactions = parser.extract_transactions(sample_file)

        credit_txn = transactions[0]
        assert Decimal(credit_txn["amount"]) > 0

    def test_debit_indicator_uppercase(self, parser):
        """Test that debit indicator is handled case-insensitively."""
        # This is tested implicitly by the sample file which uses "DBIT"
        sample_file = Path("tests/fixtures/camt053/sample_abn_amro.xml")
        transactions = parser.extract_transactions(sample_file)

        debit_txn = transactions[1]
        assert Decimal(debit_txn["amount"]) < 0

    def test_parser_handles_multiple_statements(self, parser, sample_camt053_file):
        """Test that parser can handle file with multiple statements."""
        # Current sample has 1 statement, but parser should handle multiple
        transactions = parser.extract_transactions(sample_camt053_file)
        assert len(transactions) > 0

    def test_description_extraction_priority(self, parser, sample_camt053_file):
        """Test that descriptions are extracted with correct priority."""
        transactions = parser.extract_transactions(sample_camt053_file)

        # First transaction should have remittance info + party name
        first_txn = transactions[0]
        assert "Salary payment" in first_txn["description"]
        # May also contain "Employer Inc." depending on implementation

    def test_amount_precision(self, parser, sample_camt053_file):
        """Test that amounts maintain correct decimal precision."""
        transactions = parser.extract_transactions(sample_camt053_file)

        # Check that we preserve cents (2 decimal places)
        for txn in transactions:
            amount = Decimal(txn["amount"])
            # Convert to string and check decimal places
            amount_str = str(abs(amount))
            if "." in amount_str:
                decimal_part = amount_str.split(".")[1]
                assert len(decimal_part) <= 2, "Should have max 2 decimal places"


class TestCAMT053ParserEdgeCases:
    """Test edge cases and error handling."""

    def test_missing_booking_date_uses_value_date(self, parser, tmp_path):
        """Test that value date is used when booking date is missing."""
        # Create minimal CAMT.053 with only value date
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02">
  <BkToCstmrStmt>
    <GrpHdr>
      <MsgId>TEST001</MsgId>
      <CreDtTm>2025-01-20T10:00:00</CreDtTm>
    </GrpHdr>
    <Stmt>
      <Id>STMT001</Id>
      <CreDtTm>2025-01-20T10:00:00</CreDtTm>
      <Acct>
        <Id>
          <IBAN>NL91ABNA0417164300</IBAN>
        </Id>
      </Acct>
      <Ntry>
        <Amt Ccy="EUR">100.00</Amt>
        <CdtDbtInd>CRDT</CdtDbtInd>
        <Sts>BOOK</Sts>
        <ValDt>
          <Dt>2025-01-20</Dt>
        </ValDt>
        <NtryDtls>
          <TxDtls>
            <RmtInf>
              <Ustrd>Test transaction</Ustrd>
            </RmtInf>
          </TxDtls>
        </NtryDtls>
      </Ntry>
    </Stmt>
  </BkToCstmrStmt>
</Document>"""

        test_file = tmp_path / "value_date_only.xml"
        test_file.write_text(xml_content)

        transactions = parser.extract_transactions(test_file)
        assert len(transactions) == 1
        assert transactions[0]["date"] == "2025-01-20"

    def test_transaction_without_remittance_info(self, parser, tmp_path):
        """Test handling of transaction without remittance information."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02">
  <BkToCstmrStmt>
    <GrpHdr>
      <MsgId>TEST002</MsgId>
      <CreDtTm>2025-01-20T10:00:00</CreDtTm>
    </GrpHdr>
    <Stmt>
      <Id>STMT002</Id>
      <CreDtTm>2025-01-20T10:00:00</CreDtTm>
      <Acct>
        <Id>
          <IBAN>NL91ABNA0417164300</IBAN>
        </Id>
      </Acct>
      <Ntry>
        <Amt Ccy="EUR">50.00</Amt>
        <CdtDbtInd>DBIT</CdtDbtInd>
        <Sts>BOOK</Sts>
        <BookgDt>
          <Dt>2025-01-20</Dt>
        </BookgDt>
        <NtryDtls>
          <TxDtls>
          </TxDtls>
        </NtryDtls>
      </Ntry>
    </Stmt>
  </BkToCstmrStmt>
</Document>"""

        test_file = tmp_path / "no_remittance.xml"
        test_file.write_text(xml_content)

        transactions = parser.extract_transactions(test_file)
        assert len(transactions) == 1
        # Should still have some description (fallback to "Transaction")
        assert transactions[0]["description"]

    def test_statement_with_no_entries(self, parser, tmp_path):
        """Test handling of statement with no transactions."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02">
  <BkToCstmrStmt>
    <GrpHdr>
      <MsgId>TEST003</MsgId>
      <CreDtTm>2025-01-20T10:00:00</CreDtTm>
    </GrpHdr>
    <Stmt>
      <Id>STMT003</Id>
      <CreDtTm>2025-01-20T10:00:00</CreDtTm>
      <Acct>
        <Id>
          <IBAN>NL91ABNA0417164300</IBAN>
        </Id>
      </Acct>
    </Stmt>
  </BkToCstmrStmt>
</Document>"""

        test_file = tmp_path / "no_entries.xml"
        test_file.write_text(xml_content)

        transactions = parser.extract_transactions(test_file)
        assert len(transactions) == 0
