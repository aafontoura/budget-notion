"""Debug script for Trade Republic PDF parsing."""

import logging
from pathlib import Path

from src.infrastructure.parsers.pdf_parser import PDFParser

# Enable debug logging
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

# Create parser
parser = PDFParser()

# Parse PDF
pdf_path = Path("tests/fixtures/pdfs/Account statement Trade Republic 12:25.pdf")
print(f"Parsing: {pdf_path}")
print()

transactions = parser.extract_transactions(pdf_path)

print(f"\nTotal transactions extracted: {len(transactions)}")
print()

# Print first few transactions
for i, txn in enumerate(transactions[:10], 1):
    print(f"{i}. {txn['date']} | {txn['description'][:50]} | {txn['amount']}")
