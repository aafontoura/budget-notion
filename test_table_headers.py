"""Debug script to inspect table headers."""

import pdfplumber
from pathlib import Path

pdf_path = Path("tests/fixtures/pdfs/Account statement Trade Republic 12:25.pdf")

table_settings = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
    "explicit_vertical_lines": [],
    "explicit_horizontal_lines": [],
    "snap_tolerance": 3,
    "join_tolerance": 3,
    "edge_min_length": 3,
    "min_words_vertical": 3,
    "min_words_horizontal": 1,
}

with pdfplumber.open(pdf_path) as pdf:
    for page_num, page in enumerate(pdf.pages[:2], 1):  # First 2 pages
        print(f"=== PAGE {page_num} ===")

        tables = page.extract_tables(table_settings)
        print(f"Tables found: {len(tables)}\n")

        for table_idx, table in enumerate(tables):
            print(f"Table {table_idx}: {len(table)} rows")

            # Print first 10 rows
            for i, row in enumerate(table[:10]):
                print(f"Row {i}: {row}")

            print()
