"""CSV bank statement parser."""

import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

import pandas as pd

from src.domain.entities import Transaction

logger = logging.getLogger(__name__)


class CSVParserConfig:
    """
    Configuration for CSV parsing.

    Different banks use different CSV formats. This config allows
    customization for various bank statement formats.
    """

    def __init__(
        self,
        date_column: str = "Date",
        description_column: str = "Description",
        amount_column: str = "Amount",
        account_column: Optional[str] = None,
        date_format: str = "%Y-%m-%d",
        decimal_separator: str = ".",
        thousands_separator: Optional[str] = None,
        skip_rows: int = 0,
        encoding: str = "utf-8",
    ):
        """
        Initialize CSV parser configuration.

        Args:
            date_column: Name of the date column.
            description_column: Name of the description column.
            amount_column: Name of the amount column.
            account_column: Name of the account column (optional).
            date_format: Date format string (e.g., "%Y-%m-%d", "%d/%m/%Y").
            decimal_separator: Decimal separator ("." or ",").
            thousands_separator: Thousands separator (optional).
            skip_rows: Number of rows to skip at the beginning.
            encoding: File encoding (default: utf-8).
        """
        self.date_column = date_column
        self.description_column = description_column
        self.amount_column = amount_column
        self.account_column = account_column
        self.date_format = date_format
        self.decimal_separator = decimal_separator
        self.thousands_separator = thousands_separator
        self.skip_rows = skip_rows
        self.encoding = encoding


class CSVParser:
    """
    Parser for bank statement CSV files.

    Converts CSV rows to Transaction entities with configurable column mapping.
    """

    def __init__(self, config: Optional[CSVParserConfig] = None):
        """
        Initialize CSV parser.

        Args:
            config: Parser configuration. Uses default if not provided.
        """
        self.config = config or CSVParserConfig()

    def parse(
        self,
        file_path: str | Path,
        default_category: str = "Uncategorized",
        account_name: Optional[str] = None,
    ) -> list[Transaction]:
        """
        Parse CSV file into list of Transaction entities.

        Args:
            file_path: Path to CSV file.
            default_category: Default category for transactions.
            account_name: Override account name (if not in CSV).

        Returns:
            List of Transaction entities.

        Raises:
            ValueError: If CSV is invalid or required columns are missing.
        """
        try:
            file_path = Path(file_path)

            # Read CSV file
            df = pd.read_csv(
                file_path,
                skiprows=self.config.skip_rows,
                encoding=self.config.encoding,
                thousands=self.config.thousands_separator,
                decimal=self.config.decimal_separator,
            )

            logger.info(f"Loaded CSV with {len(df)} rows from {file_path}")

            # Validate required columns
            self._validate_columns(df)

            # Parse each row into Transaction
            transactions = []
            for idx, row in df.iterrows():
                try:
                    transaction = self._parse_row(
                        row,
                        default_category=default_category,
                        account_name=account_name,
                    )
                    if transaction:
                        transactions.append(transaction)
                except Exception as e:
                    logger.warning(f"Skipping row {idx} due to error: {e}")
                    continue

            logger.info(f"Parsed {len(transactions)} transactions from CSV")
            return transactions

        except FileNotFoundError:
            raise ValueError(f"CSV file not found: {file_path}")
        except pd.errors.EmptyDataError:
            raise ValueError(f"CSV file is empty: {file_path}")
        except Exception as e:
            logger.error(f"Error parsing CSV: {e}")
            raise ValueError(f"Failed to parse CSV: {e}")

    def _validate_columns(self, df: pd.DataFrame) -> None:
        """Validate that required columns exist in DataFrame."""
        required_columns = [
            self.config.date_column,
            self.config.description_column,
            self.config.amount_column,
        ]

        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            available_columns = list(df.columns)
            raise ValueError(
                f"Missing required columns: {missing_columns}. "
                f"Available columns: {available_columns}"
            )

    def _parse_row(
        self,
        row: pd.Series,
        default_category: str,
        account_name: Optional[str],
    ) -> Optional[Transaction]:
        """
        Parse a single CSV row into a Transaction entity.

        Args:
            row: DataFrame row.
            default_category: Default category.
            account_name: Account name override.

        Returns:
            Transaction entity or None if row should be skipped.
        """
        # Extract and parse date
        date_str = str(row[self.config.date_column])
        if pd.isna(date_str) or date_str.strip() == "":
            return None

        try:
            date = datetime.strptime(date_str.strip(), self.config.date_format)
        except ValueError:
            # Try common date formats as fallback
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"]:
                try:
                    date = datetime.strptime(date_str.strip(), fmt)
                    break
                except ValueError:
                    continue
            else:
                logger.warning(f"Could not parse date: {date_str}")
                return None

        # Extract description
        description = str(row[self.config.description_column])
        if pd.isna(description) or description.strip() == "":
            description = "Unknown transaction"

        # Extract and parse amount
        amount_value = row[self.config.amount_column]
        if pd.isna(amount_value):
            return None
        
        # Extract account (from CSV or use override)
        account = None
        if "Account" in row.index and not pd.isna(row["Account"]):
            account = str(row["Account"]).strip()
        
        # Extract category from CSV if available
        category = default_category
        if "Category" in row.index and not pd.isna(row["Category"]):
            category = str(row["Category"]).strip()

        #extract subcategory from CSV if available
        subcategory = None
        if "Subcategory" in row.index and not pd.isna(row["Subcategory"]):
            subcategory = str(row["Subcategory"]).strip()
            logger.info(f"Extracted subcategory: {subcategory}")

        # Extract AI confidence if available
        ai_confidence = None
        if "AI Confidence" in row.index and not pd.isna(row["AI Confidence"]):
            try:
                ai_confidence = float(row["AI Confidence"])
            except (ValueError, TypeError):
                ai_confidence = None

        try:
            # Handle string amounts with currency symbols
            if isinstance(amount_value, str):
                # Remove currency symbols and spaces
                amount_str = amount_value.replace("$", "").replace("€", "").replace("£", "")
                amount_str = amount_str.replace(" ", "").strip()

                # Handle parentheses notation for negative numbers
                if amount_str.startswith("(") and amount_str.endswith(")"):
                    amount_str = "-" + amount_str[1:-1]

                amount = Decimal(amount_str)
            else:
                amount = Decimal(str(amount_value))

        except (ValueError, decimal.InvalidOperation):
            logger.warning(f"Could not parse amount: {amount_value}")
            return None

        # Extract account (from CSV or use override)
        # account = account_name
        # if not account and self.config.account_column:
        #     account_value = row.get(self.config.account_column)
        #     if not pd.isna(account_value):
        #         account = str(account_value)

        # Create transaction
        return Transaction(
            date=date,
            description=description.strip(),
            amount=amount,
            category=category,
            subcategory=subcategory,
            ai_confidence=ai_confidence,
            account=account,
        )


# Predefined configurations for common banks

def get_dutch_bank_configs() -> dict[str, CSVParserConfig]:
    """Get CSV parser configs for common Dutch banks."""
    return {
        "ing": CSVParserConfig(
            date_column="Datum",
            description_column="Naam / Omschrijving",
            amount_column="Bedrag (EUR)",
            date_format="%Y%m%d",
            decimal_separator=",",
        ),
        "rabobank": CSVParserConfig(
            date_column="Datum",
            description_column="Omschrijving",
            amount_column="Bedrag",
            account_column="Rekening",
            date_format="%Y-%m-%d",
            decimal_separator=",",
        ),
        "abn_amro": CSVParserConfig(
            date_column="Boekingsdatum",
            description_column="Omschrijving",
            amount_column="Bedrag",
            date_format="%d-%m-%Y",
            decimal_separator=",",
        ),
    }


def get_international_bank_configs() -> dict[str, CSVParserConfig]:
    """Get CSV parser configs for international banks."""
    return {
        "generic_us": CSVParserConfig(
            date_column="Date",
            description_column="Description",
            amount_column="Amount",
            date_format="%m/%d/%Y",
            decimal_separator=".",
        ),
        "generic_uk": CSVParserConfig(
            date_column="Date",
            description_column="Description",
            amount_column="Amount",
            date_format="%d/%m/%Y",
            decimal_separator=".",
        ),
    }
