"""
CAMT.053 Parser for ISO 20022 XML Bank Statements.

This module provides parsing capabilities for CAMT.053 (Cash Management - Account Report)
format, which is the ISO 20022 standard for electronic bank statements. This format is
becoming mandatory for many European banks, including ABN AMRO (mandatory from Nov 2025).

Supported versions:
- CAMT.053.001.02
- CAMT.053.001.04
- CAMT.053.001.08
- CAMT.053.001.09 (latest)

Features:
- Extracts transaction date, description, and amount
- Handles both debit and credit transactions
- Supports EUR and other currencies
- Robust error handling
- Comprehensive logging

Example usage:
    from pathlib import Path
    from src.infrastructure.parsers.camt053_parser import CAMT053Parser

    parser = CAMT053Parser()
    transactions = parser.extract_transactions(Path("statement.xml"))
"""

import logging
import zipfile
import tempfile
import hashlib
from pathlib import Path
from decimal import Decimal, InvalidOperation
from typing import Optional

from pycamt.parser import Camt053Parser as PycamtParser

logger = logging.getLogger(__name__)


class CAMT053Parser:
    """
    Parser for CAMT.053 (ISO 20022 XML) bank statement format.

    This parser extracts transaction data from CAMT.053 XML files and converts
    them into a standardized format compatible with the budget application.

    Attributes:
        None

    Methods:
        extract_transactions: Parse CAMT.053 file and extract transactions.
    """

    def extract_transactions(self, file_path: Path) -> list[dict]:
        """
        Extract transactions from a CAMT.053 XML file.

        Args:
            file_path: Path to the CAMT.053 XML file.

        Returns:
            List of transaction dictionaries with keys:
                - date (str): Transaction date in ISO format (YYYY-MM-DD)
                - description (str): Transaction description
                - amount (str): Transaction amount as decimal string
                              (positive for credits, negative for debits)

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file is not valid CAMT.053 XML.
            Exception: For other parsing errors.

        Example:
            >>> parser = CAMT053Parser()
            >>> transactions = parser.extract_transactions(Path("statement.xml"))
            >>> print(transactions[0])
            {'date': '2025-12-01', 'description': 'Payment from customer', 'amount': '123.45'}
        """
        logger.info(f"Parsing CAMT.053 file: {file_path}")

        # Check file exists
        if not file_path.exists():
            raise FileNotFoundError(f"CAMT.053 file not found: {file_path}")

        # Read XML content
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                xml_content = f.read()
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            raise ValueError(f"Cannot read file: {e}") from e

        # Parse CAMT.053 XML
        try:
            pycamt_parser = PycamtParser(xml_content)
        except Exception as e:
            logger.error(f"Failed to parse CAMT.053 XML: {e}")
            raise ValueError(f"Invalid CAMT.053 format: {e}") from e

        # Extract transactions using pycamt
        transactions = []
        try:
            pycamt_transactions = pycamt_parser.get_transactions()
            transaction_count = len(pycamt_transactions)
            logger.debug(f"Found {transaction_count} transaction(s) in file")

            for txn_idx, pycamt_txn in enumerate(pycamt_transactions, 1):
                try:
                    txn = self._parse_pycamt_transaction(pycamt_txn, txn_idx)
                    if txn:
                        transactions.append(txn)
                except Exception as e:
                    logger.warning(f"Failed to parse transaction {txn_idx}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Failed to extract transactions: {e}")
            raise ValueError(f"Cannot extract transactions: {e}") from e

        logger.info(f"Extracted {len(transactions)} transactions from CAMT.053 file")
        return transactions

    def _parse_pycamt_transaction(self, pycamt_txn: dict, txn_idx: int) -> Optional[dict]:
        """
        Parse a transaction dictionary from pycamt.

        Args:
            pycamt_txn: Transaction dictionary from pycamt.get_transactions().
            txn_idx: Transaction index (for logging).

        Returns:
            Transaction dictionary or None if parsing fails.
        """
        # Extract date (booking date preferred)
        date_str = pycamt_txn.get("BookingDate") or pycamt_txn.get("ValueDate")
        if not date_str:
            logger.debug(f"Transaction {txn_idx}: No date found")
            return None

        # Extract amount
        amount_raw = pycamt_txn.get("Amount")
        if not amount_raw:
            logger.debug(f"Transaction {txn_idx}: No amount found")
            return None

        # Convert amount to Decimal
        try:
            amount_decimal = Decimal(str(amount_raw))
        except (InvalidOperation, ValueError) as e:
            logger.debug(f"Transaction {txn_idx}: Cannot parse amount '{amount_raw}': {e}")
            return None

        # Apply debit/credit indicator
        credit_debit = pycamt_txn.get("CreditDebitIndicator", "").upper()
        if credit_debit == "DBIT":
            # Debit = expense = negative
            amount_decimal = -abs(amount_decimal)
        else:
            # Credit = income = positive
            amount_decimal = abs(amount_decimal)

        # Extract description
        desc_parts = []

        # Remittance information (most important)
        remit_info = pycamt_txn.get("RemittanceInformation")
        if remit_info:
            desc_parts.append(str(remit_info))

        # Party name (debtor for credits, creditor for debits)
        if credit_debit == "CRDT":
            # For credits, show who sent the money (debtor)
            debtor_name = pycamt_txn.get("DebtorName")
            if debtor_name:
                desc_parts.append(f"from {debtor_name}")
        else:
            # For debits, show who received the money (creditor)
            creditor_name = pycamt_txn.get("CreditorName")
            if creditor_name:
                desc_parts.append(f"to {creditor_name}")

        # Additional entry information
        additional_info = pycamt_txn.get("AdditionalEntryInformation")
        if additional_info:
            desc_parts.append(str(additional_info))

        # Build description
        if desc_parts:
            description = " - ".join(desc_parts)
            # Clean up excessive whitespace
            description = " ".join(description.split())
        else:
            # Fallback to generic description
            description = "Transaction"

        logger.debug(
            f"Transaction {txn_idx}: date={date_str}, amount={amount_decimal}, "
            f"desc={description[:50]}..."
        )

        return {
            "date": date_str,
            "description": description,
            "amount": str(amount_decimal),
        }

    def extract_from_zip(self, zip_path: Path) -> list[dict]:
        """
        Extract and parse all CAMT.053 XML files from a ZIP archive.

        Args:
            zip_path: Path to ZIP file containing CAMT.053 XML files.

        Returns:
            List of all transactions from all XML files in the ZIP.

        Raises:
            FileNotFoundError: If ZIP file doesn't exist.
            ValueError: If ZIP is invalid or contains no XML files.
        """
        logger.info(f"Extracting CAMT.053 files from ZIP: {zip_path}")

        if not zip_path.exists():
            raise FileNotFoundError(f"ZIP file not found: {zip_path}")

        if not zipfile.is_zipfile(zip_path):
            raise ValueError(f"File is not a valid ZIP archive: {zip_path}")

        # Create temporary directory for extraction
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Extract ZIP
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    # Find all XML files
                    xml_files = [f for f in zip_ref.namelist() if f.lower().endswith('.xml')]

                    if not xml_files:
                        logger.warning(f"No XML files found in ZIP: {zip_path}")
                        return []

                    logger.info(f"Found {len(xml_files)} XML file(s) in ZIP")

                    # Extract all XML files
                    for xml_file in xml_files:
                        zip_ref.extract(xml_file, temp_path)

            except Exception as e:
                logger.error(f"Failed to extract ZIP: {e}")
                raise ValueError(f"Cannot extract ZIP file: {e}") from e

            # Process all extracted XML files
            all_transactions = []
            for xml_file in xml_files:
                xml_path = temp_path / xml_file
                logger.info(f"Processing {xml_file}...")

                try:
                    transactions = self.extract_transactions(xml_path)
                    all_transactions.extend(transactions)
                    logger.info(f"  → Extracted {len(transactions)} transactions")
                except Exception as e:
                    logger.error(f"  → Failed to parse {xml_file}: {e}")
                    # Continue processing other files
                    continue

        logger.info(f"Total transactions from ZIP: {len(all_transactions)}")
        return all_transactions

    def extract_from_directory(self, dir_path: Path, recursive: bool = False) -> list[dict]:
        """
        Extract and parse all CAMT.053 XML files from a directory.

        Args:
            dir_path: Path to directory containing CAMT.053 XML files.
            recursive: If True, search subdirectories recursively.

        Returns:
            List of all transactions from all XML files in the directory.

        Raises:
            FileNotFoundError: If directory doesn't exist.
            ValueError: If directory contains no XML files.
        """
        logger.info(f"Processing CAMT.053 files from directory: {dir_path}")

        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {dir_path}")

        if not dir_path.is_dir():
            raise ValueError(f"Path is not a directory: {dir_path}")

        # Find all XML files
        if recursive:
            xml_files = list(dir_path.rglob("*.xml"))
        else:
            xml_files = list(dir_path.glob("*.xml"))

        if not xml_files:
            logger.warning(f"No XML files found in directory: {dir_path}")
            return []

        logger.info(f"Found {len(xml_files)} XML file(s) in directory")

        # Process all XML files
        all_transactions = []
        for xml_file in xml_files:
            logger.info(f"Processing {xml_file.name}...")

            try:
                transactions = self.extract_transactions(xml_file)
                all_transactions.extend(transactions)
                logger.info(f"  → Extracted {len(transactions)} transactions")
            except Exception as e:
                logger.error(f"  → Failed to parse {xml_file.name}: {e}")
                # Continue processing other files
                continue

        logger.info(f"Total transactions from directory: {len(all_transactions)}")
        return all_transactions

    def extract_smart(
        self,
        path: Path,
        skip_duplicates: bool = True,
        existing_transactions: Optional[list[dict]] = None
    ) -> dict:
        """
        Smart extraction that auto-detects file type (ZIP, XML, or directory).

        Args:
            path: Path to ZIP file, XML file, or directory.
            skip_duplicates: If True, skip duplicate transactions.
            existing_transactions: List of existing transactions for duplicate detection.

        Returns:
            Dictionary with:
                - transactions: List of extracted transactions
                - total_files: Number of files processed
                - duplicates_skipped: Number of duplicates skipped
                - errors: List of error messages

        Raises:
            FileNotFoundError: If path doesn't exist.
            ValueError: If path type cannot be determined.
        """
        logger.info(f"Smart extraction from: {path}")

        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")

        # Detect file type and extract
        if path.is_dir():
            logger.info("Detected: Directory")
            transactions = self.extract_from_directory(path)
            file_count = len(list(path.glob("*.xml")))
        elif zipfile.is_zipfile(path):
            logger.info("Detected: ZIP archive")
            transactions = self.extract_from_zip(path)
            with zipfile.ZipFile(path, 'r') as zf:
                file_count = len([f for f in zf.namelist() if f.lower().endswith('.xml')])
        elif path.suffix.lower() == '.xml':
            logger.info("Detected: Single XML file")
            transactions = self.extract_transactions(path)
            file_count = 1
        else:
            raise ValueError(f"Unsupported file type: {path.suffix}")

        # Remove duplicates if requested
        duplicates_skipped = 0
        if skip_duplicates and existing_transactions:
            transactions, duplicates_skipped = self._remove_duplicates(
                transactions, existing_transactions
            )

        return {
            "transactions": transactions,
            "total_files": file_count,
            "duplicates_skipped": duplicates_skipped,
            "total_extracted": len(transactions) + duplicates_skipped,
        }

    def _remove_duplicates(
        self,
        new_transactions: list[dict],
        existing_transactions: list[dict]
    ) -> tuple[list[dict], int]:
        """
        Remove duplicate transactions based on fingerprint.

        A transaction is considered duplicate if it has the same:
        - Date
        - Amount
        - Description (first 50 chars)

        Args:
            new_transactions: List of newly extracted transactions.
            existing_transactions: List of already imported transactions.

        Returns:
            Tuple of (unique_transactions, duplicate_count)
        """
        # Create fingerprints for existing transactions
        existing_fingerprints = set()
        for txn in existing_transactions:
            fingerprint = self._create_fingerprint(txn)
            existing_fingerprints.add(fingerprint)

        # Filter new transactions
        unique_transactions = []
        duplicate_count = 0

        for txn in new_transactions:
            fingerprint = self._create_fingerprint(txn)
            if fingerprint in existing_fingerprints:
                duplicate_count += 1
                logger.debug(f"Skipping duplicate: {txn['date']} | {txn['description'][:30]}...")
            else:
                unique_transactions.append(txn)
                # Add to set to avoid duplicates within the new batch
                existing_fingerprints.add(fingerprint)

        if duplicate_count > 0:
            logger.info(f"Skipped {duplicate_count} duplicate transaction(s)")

        return unique_transactions, duplicate_count

    def _create_fingerprint(self, transaction: dict) -> str:
        """
        Create a unique fingerprint for a transaction.

        The fingerprint is a hash of:
        - Date
        - Amount (normalized to Decimal for consistent comparison)
        - Description (first 50 chars, normalized)

        Args:
            transaction: Transaction dictionary.

        Returns:
            SHA256 hash string.
        """
        # Normalize description (lowercase, strip, first 50 chars)
        desc = transaction.get("description", "")[:50].lower().strip()

        # Normalize amount to Decimal to avoid "250.5" vs "250.50" issues
        # Use normalize() to remove trailing zeros
        amount = str(Decimal(str(transaction["amount"])).normalize())

        # Create string to hash
        fingerprint_str = f"{transaction['date']}|{amount}|{desc}"

        # Return SHA256 hash
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()
