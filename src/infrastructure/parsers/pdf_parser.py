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

                # Extract all text first to detect bank format
                all_text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        all_text += page_text + "\n"

                # Try Trade Republic format first (specific pattern)
                if "TRADE REPUBLIC" in all_text.upper() or "ACCOUNT TRANSACTIONS" in all_text:
                    logger.info("Detected Trade Republic format")
                    transactions = self._parse_trade_republic(pdf)
                    if transactions:
                        logger.info(f"Extracted {len(transactions)} transactions using Trade Republic parser")
                        return transactions

                # Fallback: Try table and text extraction
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

    # Trade Republic text-based parsing helpers
    # Regex patterns
    DATE_START_RE = re.compile(
        r"^(0[1-9]|[12]\d|3[01])\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b"
    )
    YEAR_ANYWHERE_RE = re.compile(r"\b(19|20)\d{2}\b")
    EUR_ANY_RE = re.compile(r"€\s*[\d.,]+")

    # Month name to number mapping
    MONTHS = {
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
        "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
    }

    # Known transaction types
    KNOWN_TYPES = {"Reward", "Interest", "Trade", "Card", "Transfer", "Earnings"}

    # Lines to drop (headers, footers, legal text)
    DROP_EXACT = {
        "DATE", "TYPE", "DESCRIPTION", "MONEY IN", "MONEY OUT", "BALANCE",
        "MONEY", "OUT", "IN",
        "DATE TYPE DESCRIPTION MONEY IN M OU O T NEY BALANCE",
    }

    DROP_SUBSTRINGS = [
        "TRADE REPUBLIC BANK GMBH",
        "KRAANSPOOR",
        "Generated on",
        "Page",
        "www.traderepublic",
        "Seat of the Company",
        "Directors",
        "VAT ID No",
        "CCI number",
        "AG Charlottenburg",
        "Brunnenstrasse",
    ]

    def _clean_line(self, s: str) -> str:
        """Clean a text line (normalize whitespace, remove null artifacts)."""
        s = s.replace("\u00a0", " ")
        s = re.sub(r"\s+", " ", s).strip()
        if s.endswith("null"):
            s = s[:-4].strip()
        return s

    def _extract_text_lines(self, pdf) -> list[str]:
        """Extract text lines from all pages with tolerances."""
        lines = []
        for page in pdf.pages:
            txt = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            for raw in txt.splitlines():
                line = self._clean_line(raw)
                if line:
                    lines.append(line)
        return lines

    def _slice_transactions(self, lines: list[str]) -> list[str]:
        """Extract lines between 'ACCOUNT TRANSACTIONS' and 'BALANCE OVERVIEW'."""
        start = None
        end = None
        for i, l in enumerate(lines):
            if l == "ACCOUNT TRANSACTIONS":
                start = i + 1
                continue
            if start is not None and l in ("BALANCE OVERVIEW", "TRANSACTION OVERVIEW"):
                end = i
                break
        if start is None:
            # If no marker found, return all lines (fallback)
            logger.warning("'ACCOUNT TRANSACTIONS' marker not found, parsing all lines")
            return lines
        return lines[start:end] if end is not None else lines[start:]

    def _filter_noise(self, lines: list[str]) -> list[str]:
        """Filter out headers, footers, and legal text."""
        out = []
        for l in lines:
            if l in self.DROP_EXACT:
                continue
            if any(sub in l for sub in self.DROP_SUBSTRINGS):
                continue
            out.append(l)
        return out

    def _split_into_blocks(self, lines: list[str]) -> list[list[str]]:
        """Split lines into transaction blocks (starts with date pattern)."""
        blocks = []
        cur = []
        for l in lines:
            if self.DATE_START_RE.match(l):
                if cur:
                    blocks.append(cur)
                cur = [l]
            else:
                if cur:  # Ignore preamble before first date
                    cur.append(l)
        if cur:
            blocks.append(cur)
        return blocks

    def _detect_type(self, tokens: list[str]) -> str:
        """Detect transaction type from tokens."""
        for t in tokens:
            if t in self.KNOWN_TYPES:
                return t
        return ""

    def _build_description(self, block: list[str]) -> str:
        """Build description by removing structural markers and amounts."""
        desc_parts = []
        for l in block[1:]:  # Skip date line
            # Skip transaction type keywords
            if l in self.KNOWN_TYPES:
                continue
            if l == "Transaction":
                continue
            # Skip noise
            if l in self.DROP_EXACT or any(sub in l for sub in self.DROP_SUBSTRINGS):
                continue

            # Remove year and amounts
            clean = l
            clean = self.YEAR_ANYWHERE_RE.sub("", clean)
            clean = self.EUR_ANY_RE.sub("", clean)
            clean = re.sub(r"\s+", " ", clean).strip()

            # Remove "null" artifacts
            clean = clean.replace("null", "").strip()

            if clean:
                desc_parts.append(clean)

        description = " ".join(desc_parts).strip(" -")

        # Remove leading transaction type words that might have been part of description
        for typ in self.KNOWN_TYPES:
            if description.startswith(typ + " "):
                description = description[len(typ):].strip()
                break

        return description

    def _parse_eur_amount(self, euro_text: str) -> Decimal | None:
        """Parse € amount string to Decimal."""
        m = re.search(r"€\s*([\d.,]+)", euro_text)
        if not m:
            return None
        amount_str = m.group(1).replace(",", "")
        if "." not in amount_str:
            amount_str += ".00"
        try:
            return Decimal(amount_str)
        except (InvalidOperation, ValueError):
            return None

    def _parse_trade_republic_block(self, block: list[str]) -> dict | None:
        """
        Parse a single transaction block.

        Expected format:
        - First line: "DD Mon [Type] ..." (e.g., "03 Dec Card ...")
        - Following lines: description, amounts, year
        - Year can be anywhere in the block
        - Last € amount is balance, second-to-last is transaction amount

        Returns:
            Transaction dict or None if parsing fails.
        """
        if not block:
            return None

        raw = " ".join(block)

        # Parse date
        m = self.DATE_START_RE.match(block[0])
        if not m:
            logger.debug(f"Cannot parse date from: {block[0]}")
            return None

        day = int(m.group(1))
        mon = self.MONTHS[m.group(2)]

        # Find year anywhere in block
        y = self.YEAR_ANYWHERE_RE.search(raw)
        if not y:
            logger.debug(f"No year found in block: {block[0]}")
            return None
        year = int(y.group(0))

        # Build date string
        try:
            from datetime import date as dt_date
            tx_date = dt_date(year, mon, day).isoformat()
        except ValueError:
            logger.debug(f"Invalid date: {year}-{mon}-{day}")
            return None

        # Detect type
        tokens = []
        for l in block:
            tokens.extend(l.split())
        tx_type = self._detect_type(tokens)

        # Extract amounts (last € is balance, second-to-last is transaction)
        euros = self.EUR_ANY_RE.findall(raw)
        amounts = [self._parse_eur_amount(e) for e in euros]
        amounts = [a for a in amounts if a is not None]

        if len(amounts) < 2:
            # Need at least transaction amount + balance
            logger.debug(f"Not enough amounts in block: {block[0]}")
            return None

        # Transaction amount is second-to-last
        amt = amounts[-2]

        # Determine if income or expense based on type
        # Reward, Interest, Earnings, Transfer (incoming) = income
        # Card, Trade, Transfer (outgoing) = expense
        is_income = tx_type in ("Reward", "Interest", "Earnings")

        # For transfers, check if incoming
        if tx_type == "Transfer" and "Incoming transfer" in raw:
            is_income = True

        # Build description
        description = self._build_description(block)
        if not description:
            logger.debug(f"Empty description for block: {block[0]}")
            return None

        # Normalize amount (income is positive, expense is negative)
        if not is_income:
            amt = -abs(amt)

        return {
            "date": tx_date,
            "description": description,
            "amount": str(amt),
        }

    def _parse_trade_republic(self, pdf) -> list[dict]:
        """
        Parse Trade Republic bank statement format using text extraction.

        Uses robust text-based parsing instead of table extraction:
        - Extract text with tolerances to reduce splitting issues
        - Filter noise (headers, footers, legal text)
        - Split into transaction blocks (starting with date pattern)
        - Parse each block for date, description, and amounts

        Args:
            pdf: pdfplumber PDF object.

        Returns:
            List of transaction dictionaries.
        """
        # Extract all text lines from PDF
        lines = self._extract_text_lines(pdf)

        # Slice to transaction section
        tx_lines = self._slice_transactions(lines)

        # Filter out noise (headers, footers, legal text)
        tx_lines = self._filter_noise(tx_lines)

        # Split into transaction blocks
        blocks = self._split_into_blocks(tx_lines)

        # Parse each block
        transactions = []
        for block in blocks:
            try:
                txn = self._parse_trade_republic_block(block)
                if txn:
                    transactions.append(txn)
            except Exception as e:
                logger.debug(f"Failed to parse block: {e}")
                continue

        logger.info(f"Extracted {len(transactions)} Trade Republic transactions")
        return transactions
