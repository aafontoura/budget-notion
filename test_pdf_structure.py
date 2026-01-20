"""Debug script to inspect PDF structure."""

import pdfplumber
from pathlib import Path

pdf_path = Path("tests/fixtures/pdfs/Account statement Trade Republic 12:25.pdf")

with pdfplumber.open(pdf_path) as pdf:
    print(f"Total pages: {len(pdf.pages)}\n")

    for page_num, page in enumerate(pdf.pages, 1):
        print(f"=== PAGE {page_num} ===")

        # Try to extract tables
        tables = page.extract_tables()
        print(f"Tables found: {len(tables)}")

        if tables:
            for i, table in enumerate(tables):
                print(f"\nTable {i+1}:")
                print(f"Rows: {len(table)}")
                if table:
                    print(f"Header: {table[0]}")

        # Extract text to see what's there
        text = page.extract_text()
        if text:
            lines = text.split("\n")
            print(f"\nText lines: {len(lines)}")
            print("First 30 lines:")
            for i, line in enumerate(lines[:30], 1):
                print(f"{i:3d}: {line}")

        print("\n" + "="*60 + "\n")

        # Only print first page details
        if page_num == 2:
            break
