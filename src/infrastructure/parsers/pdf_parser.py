"""PDF parser for extracting transactions from bank statements."""

import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

import pdfplumber

logger = logging.getLogger(__name__)


class PDFParserError(Exception):
    """Exception raised for PDF parsing errors."""

    pass


class PDFParser:
    """
    Extract transactions from PDF bank statements.

    Supports common bank formats:
    - ABN AMRO (Netherlands)
    - Trade Republic (Netherlands/Germany)
    - Nubank (Brazil)
    - Generic table-based statements
    """

    def __init__(self):
        """Initialize PDF parser."""
        self.date_patterns = [
            r"\d{4}-\d{2}-\d{2}",  # YYYY-MM-DD
            r"\d{2}-\d{2}-\d{4}",  # DD-MM-YYYY
            r"\d{2}/\d{2}/\d{4}",  # DD/MM/YYYY
            r"\d{1,2}\s+\w{3}\s+\d{4}",  # 15 Jan 2025
        ]

        self.amount_patterns = [
            r"[-+]?\s*€?\s*\d{1,3}(?:[.,]\d{3})*[.,]\d{2}",  # €1,234.56 or 1.234,56
            r"[-+]?\s*R?\$?\s*\d{1,3}(?:[.,]\d{3})*[.,]\d{2}",  # R$1,234.56
        ]

    def extract_transactions(self, file_path: Path) -> list[dict]:
        """
        Extract transactions from PDF.

        Args:
            file_path: Path to PDF file.

        Returns:
            List of transaction dictionaries with keys:
                - date: str (YYYY-MM-DD format)
                - description: str
                - amount: str (will be parsed to Decimal later)

        Raises:
            PDFParserError: If PDF cannot be read or parsed.
        """
        try:
            with pdfplumber.open(file_path) as pdf:
                logger.info(f"Opened PDF with {len(pdf.pages)} pages")

                transactions = []

                # Try table extraction first (most structured)
                for page_num, page in enumerate(pdf.pages, 1):
                    logger.debug(f"Processing page {page_num}")

                    # Extract tables
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            page_transactions = self._parse_table(table)
                            transactions.extend(page_transactions)
                            logger.debug(
                                f"Found {len(page_transactions)} transactions in table on page {page_num}"
                            )

                    # Fallback: Extract text and parse line by line
                    if not transactions:
                        text = page.extract_text()
                        if text:
                            page_transactions = self._parse_text(text)
                            transactions.extend(page_transactions)
                            logger.debug(
                                f"Found {len(page_transactions)} transactions in text on page {page_num}"
                            )

                logger.info(f"Extracted {len(transactions)} total transactions")
                return transactions

        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
            raise PDFParserError(f"Failed to parse PDF: {e}") from e

    def _parse_table(self, table: list[list]) -> list[dict]:
        """
        Parse transactions from extracted table.

        Args:
            table: List of rows, where each row is a list of cells.

        Returns:
            List of transaction dictionaries.
        """
        transactions = []

        if not table or len(table) < 2:
            return transactions

        # Detect header row and column indices
        header = table[0] if table[0] else []
        date_col, desc_col, amount_col = self._detect_columns(header)

        # Parse data rows
        for row in table[1:]:
            if not row or len(row) < 2:
                continue

            try:
                # Extract fields
                date_str = row[date_col] if date_col < len(row) else None
                description = row[desc_col] if desc_col < len(row) else None
                amount_str = row[amount_col] if amount_col < len(row) else None

                if not all([date_str, description, amount_str]):
                    continue

                # Parse and normalize
                date_normalized = self._normalize_date(date_str)
                amount_normalized = self._normalize_amount(amount_str)

                if date_normalized and amount_normalized:
                    transactions.append(
                        {
                            "date": date_normalized,
                            "description": description.strip(),
                            "amount": amount_normalized,
                        }
                    )

            except Exception as e:
                logger.debug(f"Skipping row due to error: {e}")
                continue

        return transactions

    def _parse_text(self, text: str) -> list[dict]:
        """
        Parse transactions from plain text.

        Args:
            text: Raw text extracted from PDF.

        Returns:
            List of transaction dictionaries.
        """
        transactions = []
        lines = text.split("\n")

        for line in lines:
            if not line.strip():
                continue

            # Try to find date and amount in the line
            date_match = None
            for pattern in self.date_patterns:
                date_match = re.search(pattern, line)
                if date_match:
                    break

            amount_match = None
            for pattern in self.amount_patterns:
                amount_match = re.search(pattern, line)
                if amount_match:
                    break

            if date_match and amount_match:
                try:
                    date_str = date_match.group()
                    amount_str = amount_match.group()

                    # Extract description (everything between date and amount)
                    desc_start = date_match.end()
                    desc_end = amount_match.start()
                    description = line[desc_start:desc_end].strip()

                    # Normalize
                    date_normalized = self._normalize_date(date_str)
                    amount_normalized = self._normalize_amount(amount_str)

                    if date_normalized and amount_normalized and description:
                        transactions.append(
                            {
                                "date": date_normalized,
                                "description": description,
                                "amount": amount_normalized,
                            }
                        )
                except Exception as e:
                    logger.debug(f"Skipping line due to error: {e}")
                    continue

        return transactions

    def _detect_columns(self, header: list[str]) -> tuple[int, int, int]:
        """
        Detect column indices for date, description, and amount.

        Args:
            header: List of column names from table header.

        Returns:
            Tuple of (date_col_index, description_col_index, amount_col_index).
        """
        date_col, desc_col, amount_col = 0, 1, 2  # Defaults

        for i, col in enumerate(header):
            if not col:
                continue

            col_lower = col.lower()

            # Date column
            if any(
                keyword in col_lower
                for keyword in ["date", "datum", "data", "fecha"]
            ):
                date_col = i

            # Description column
            elif any(
                keyword in col_lower
                for keyword in [
                    "description",
                    "omschrijving",
                    "descrição",
                    "descripción",
                    "naam",
                    "name",
                ]
            ):
                desc_col = i

            # Amount column
            elif any(
                keyword in col_lower
                for keyword in ["amount", "bedrag", "valor", "monto", "saldo"]
            ):
                amount_col = i

        return date_col, desc_col, amount_col

    def _normalize_date(self, date_str: str) -> Optional[str]:
        """
        Normalize date string to YYYY-MM-DD format.

        Args:
            date_str: Date string in various formats.

        Returns:
            Normalized date string (YYYY-MM-DD) or None if parsing fails.
        """
        date_formats = [
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d %b %Y",
            "%d %B %Y",
            "%Y%m%d",
        ]

        date_str = date_str.strip()

        for fmt in date_formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        logger.debug(f"Could not parse date: {date_str}")
        return None

    def _normalize_amount(self, amount_str: str) -> Optional[str]:
        """
        Normalize amount string to decimal format.

        Args:
            amount_str: Amount string with currency symbols, separators, etc.

        Returns:
            Normalized amount string (e.g., "-123.45") or None if parsing fails.
        """
        # Remove currency symbols and whitespace
        amount_str = re.sub(r"[€$R£]\s*", "", amount_str).strip()

        # Handle parentheses for negative amounts (e.g., "(123.45)")
        is_negative = False
        if amount_str.startswith("(") and amount_str.endswith(")"):
            is_negative = True
            amount_str = amount_str[1:-1]

        # Handle explicit negative sign
        if amount_str.startswith("-") or amount_str.startswith("+"):
            is_negative = amount_str.startswith("-")
            amount_str = amount_str[1:]

        # Determine decimal separator (last . or ,)
        # European format: 1.234,56  (. = thousands, , = decimal)
        # US/UK format: 1,234.56   (, = thousands, . = decimal)
        if "," in amount_str and "." in amount_str:
            # Both present - last one is decimal separator
            last_comma_pos = amount_str.rfind(",")
            last_dot_pos = amount_str.rfind(".")

            if last_comma_pos > last_dot_pos:
                # European format
                amount_str = amount_str.replace(".", "").replace(",", ".")
            else:
                # US format
                amount_str = amount_str.replace(",", "")
        elif "," in amount_str:
            # Only comma - assume decimal separator (European)
            amount_str = amount_str.replace(",", ".")
        # If only dot, assume it's already correct

        # Parse to Decimal to validate
        try:
            amount_decimal = Decimal(amount_str)
            if is_negative:
                amount_decimal = -amount_decimal
            return str(amount_decimal)
        except (InvalidOperation, ValueError):
            logger.debug(f"Could not parse amount: {amount_str}")
            return None
