"""Debug page 1 specifically."""

import logging
from pathlib import Path

from src.infrastructure.parsers.pdf_parser import PDFParser

# Enable debug logging
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

# Create parser
parser = PDFParser()

# Parse PDF
pdf_path = Path("tests/fixtures/pdfs/Account statement Trade Republic 12:25.pdf")

import pdfplumber

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
    page = pdf.pages[0]  # Page 1
    tables = page.extract_tables(table_settings)

    if tables:
        table = tables[0]
        print(f"Page 1 table has {len(table)} rows\n")

        print("Rows 0-15:")
        for i, row in enumerate(table[:16]):
            print(f"Row {i}: {row}")

        print("\n\nChecking for Trade Republic header...")
        for row_idx in range(min(15, len(table))):
            header = table[row_idx]
            if not header:
                continue

            header_str = " ".join(
                str(cell or "").replace("\n", " ").upper() for cell in header
            )

            is_tr = (
                "DATE" in header_str
                and ("MONEY" in header_str or "GELD" in header_str)
                and "BALANCE" in header_str
                and "OPENING BALANCE" not in header_str
                and "PRODUCT" not in header_str
            )

            print(f"Row {row_idx}: is_TR={is_tr}")
            if is_tr:
                print(f"  FOUND! Header: {header_str}")
                break
