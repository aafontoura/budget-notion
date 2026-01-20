#!/usr/bin/env python3
import re
import csv
from datetime import date
from typing import List, Dict, Optional

import pdfplumber

MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
}

DATE_RE = re.compile(r"^(0[1-9]|[12]\d|3[01])\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$")
YEAR_RE = re.compile(r"^(19|20)\d{2}$")
EUR_RE = re.compile(r"^€\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)$")

KNOWN_TYPES = ["Reward", "Interest", "Trade", "Card", "Transfer", "Earnings"]

# Lines to drop (you can extend this set if you see more noise)
DROP_EXACT = {
    "DATE", "TYPE", "DESCRIPTION", "MONEY IN", "MONEY OUT", "BALANCE",
    "MONEY", "OUT",  # sometimes split across lines in extraction
    "DATE TYPE DESCRIPTION MONEY IN M OU O T NEY BALANCE",  # Full header line
}

DROP_SUBSTRINGS = [
    "TRADE REPUBLIC BANK GMBH",
    "KRAANSPOOR 50",
    "Generated on",
    "Page",
    "www.traderepublic.nl",
    "Seat of the Company:",
    "Directors",
    "VAT ID No.",
    "CCI number:",
    "AG Charlottenburg",
    "Brunnenstrasse",
]


def clean_line(s: str) -> str:
    s = s.replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    if s.endswith("null"):
        s = s[:-4].strip()
    return s


def parse_eur(s: str) -> Optional[float]:
    m = EUR_RE.match(s.strip())
    if not m:
        return None
    amount_str = m.group(1).replace(",", "")
    # If the string doesn't contain a dot, add .00
    if "." not in amount_str:
        amount_str = amount_str + ".00"
    return float(amount_str)


def pdf_to_lines(pdf_path: str) -> List[str]:
    lines: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            txt = page.extract_text() or ""
            for raw in txt.splitlines():
                line = clean_line(raw)
                if line:
                    lines.append(line)
    return lines


def slice_transactions(lines: List[str]) -> List[str]:
    start = None
    end = None
    for i, l in enumerate(lines):
        if l == "ACCOUNT TRANSACTIONS":
            start = i + 1
            continue
        if start is not None and (l == "BALANCE OVERVIEW" or l == "TRANSACTION OVERVIEW"):
            end = i
            break
    if start is None:
        raise ValueError("ACCOUNT TRANSACTIONS not found")
    return lines[start:end] if end is not None else lines[start:]


def filter_noise(lines: List[str]) -> List[str]:
    out = []
    for l in lines:
        if l in DROP_EXACT:
            continue
        if any(sub in l for sub in DROP_SUBSTRINGS):
            continue
        out.append(l)
    return out


def split_into_blocks(lines: List[str]) -> List[List[str]]:
    """
    Each transaction starts with a date line like "03 Dec".
    However, the year comes later, sometimes on a separate line like "2025".
    We need to detect when a new transaction begins by looking for lines like "03 Dec Card" or "03 Dec" followed by type.
    """
    blocks: List[List[str]] = []
    cur: List[str] = []

    i = 0
    while i < len(lines):
        l = lines[i]
        
        # Check if this line starts with a date (DD MMM format)
        if DATE_RE.match(l):
            # This is the start of a new transaction
            if cur:
                blocks.append(cur)
            cur = [l]
        # Check if this line starts with "DD MMM TYPE" format (date + transaction type on same line)
        elif re.match(r"^(0[1-9]|[12]\d|3[01])\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\w+", l):
            # This is also the start of a new transaction
            if cur:
                blocks.append(cur)
            cur = [l]
        else:
            # This line belongs to the current transaction
            if cur:  # ignore anything before first date
                cur.append(l)
        i += 1

    if cur:
        blocks.append(cur)
    return blocks


def find_type(tokens: List[str]) -> Optional[str]:
    # type might appear as standalone line or alongside other words (rare)
    for t in tokens:
        if t in KNOWN_TYPES:
            return t
    return None


def parse_block(block: List[str]) -> Dict:
    # Flatten block into tokens but keep original lines for description reconstruction.
    tokens = []
    for l in block:
        tokens.extend(l.split())

    # date is always first line in this block
    parts = block[0].split()
    day = int(parts[0])
    mon = MONTHS[parts[1]]

    # year can appear anywhere in the block in your extraction.
    year = None
    for t in tokens:
        if YEAR_RE.match(t):
            year = int(t)
            break
    if year is None:
        raise ValueError(f"No year found in block starting {block[0]!r}")

    tx_type = find_type(tokens)

    # amounts: collect all € amounts, they appear in lines like "€9.31 €857.76"
    amounts = []
    for line in block:
        # Search for all € amounts in the line
        for token in line.split():
            if token.startswith("€"):
                v = parse_eur(token)
                if v is not None:
                    amounts.append(v)

    money_in = money_out = balance = None
    if amounts:
        balance = amounts[-1]
    if len(amounts) >= 2:
        amt = amounts[-2]
        # Heuristic by type based on your statement content.
        if tx_type in ("Reward", "Interest", "Earnings", "Transfer"):
            money_in = amt
        else:
            money_out = amt

    # Build description: remove known structural lines/tokens and amounts.
    # Keep line order, drop lines that are only year/type/amount markers.
    desc_lines = []
    for l in block[1:]:  # skip date line
        if l in KNOWN_TYPES:
            continue
        if YEAR_RE.match(l):
            continue
        if l == "Transaction":
            continue
        if l in DROP_EXACT or any(sub in l for sub in DROP_SUBSTRINGS):
            continue
        # Remove all € amounts and year from the line for cleaner description
        clean = l
        for token in l.split():
            if token.startswith("€") or YEAR_RE.match(token):
                clean = clean.replace(token, "").strip()
        if clean:
            desc_lines.append(clean)

    description = " ".join(desc_lines).strip()

    return {
        "date": date(year, mon, day).isoformat(),
        "type": tx_type or "",
        "description": description,
        "money_in": money_in,
        "money_out": money_out,
        "balance": balance,
    }


def parse_pdf(pdf_path: str) -> List[Dict]:
    lines = pdf_to_lines(pdf_path)
    tx_lines = slice_transactions(lines)
    tx_lines = filter_noise(tx_lines)
    blocks = split_into_blocks(tx_lines)
    return [parse_block(b) for b in blocks]


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf")
    parser.add_argument("--out", default="out.csv")
    args = parser.parse_args()

    rows = parse_pdf(args.pdf)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "type", "description", "money_in", "money_out", "balance"])
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} transactions to {args.out}")


if __name__ == "__main__":
    main()
