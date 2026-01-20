"""Test the new text-based Trade Republic parser."""

import logging
from pathlib import Path

from src.infrastructure.parsers.pdf_parser import PDFParser

# Enable debug logging
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

# Create parser
parser = PDFParser()

# Parse PDF
pdf_path = Path("tests/fixtures/pdfs/Account statement Trade Republic 12:25.pdf")

print(f"\n{'='*80}")
print(f"Testing new text-based Trade Republic parser")
print(f"{'='*80}\n")

try:
    transactions = parser.extract_transactions(pdf_path)

    print(f"✓ Extracted {len(transactions)} transactions\n")

    if transactions:
        print("First 5 transactions:")
        for i, txn in enumerate(transactions[:5], 1):
            print(f"{i}. {txn['date']} | {txn['description'][:50]:<50} | €{txn['amount']:>10}")

        print(f"\n... ({len(transactions) - 5} more transactions)")

        # Summary
        print(f"\n{'='*80}")
        print("Summary:")
        print(f"{'='*80}")
        print(f"Total transactions: {len(transactions)}")

        from decimal import Decimal
        total_income = sum(Decimal(t['amount']) for t in transactions if Decimal(t['amount']) > 0)
        total_expense = sum(Decimal(t['amount']) for t in transactions if Decimal(t['amount']) < 0)

        print(f"Total income: €{total_income}")
        print(f"Total expense: €{total_expense}")
        print(f"Net: €{total_income + total_expense}")
    else:
        print("✗ No transactions extracted!")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
