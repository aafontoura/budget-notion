#!/usr/bin/env python3
"""
Trade Republic account statement parser (PDF -> CSV)

Merged “best of both”:
- Robust PDF text extraction (x/y tolerances)
- Noise filtering (headers/footers/legal blocks)
- Stable transaction block splitting (starts at lines beginning with "DD Mon")
- Robust € amount extraction (regex anywhere in the line; not only tokenized)
- Year detection anywhere in the block
- Clean description reconstruction
- Configurable ignore rules (e.g., ignore incoming transfers from your own bank account IBAN)
- Reward handling: classified as an investment gain (still a valid transaction)

Typical usage:
  python parse_tr_statement.py "/path/to/statement.pdf" --out out.csv

To ignore incoming transfers from your own bank account (default IBAN below):
  python parse_tr_statement.py statement.pdf --out out.csv

To keep Trade lines (default is to exclude them):
  python parse_tr_statement.py statement.pdf --keep-trade

To assert an expected row count (after filters):
  python parse_tr_statement.py statement.pdf --expected-count 63
"""

import re
import csv
import argparse
from dataclasses import dataclass
from datetime import date
from typing import List, Dict, Optional, Set, Tuple

import pdfplumber


MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
}

# Start of a transaction line in extracted text (covers "03 Dec" and "03 Dec Card ...")
DATE_START_RE = re.compile(
    r"^(0[1-9]|[12]\d|3[01])\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b"
)

YEAR_ANYWHERE_RE = re.compile(r"\b(19|20)\d{2}\b")

# Finds € amounts anywhere in a line (robust even if extraction merges tokens oddly)
EUR_ANY_RE = re.compile(r"€\s*[\d.,]+")

KNOWN_TYPES = {"Reward", "Interest", "Trade", "Card", "Transfer", "Earnings"}

# Lines to drop (extend if you see more noise)
DROP_EXACT = {
    "DATE", "TYPE", "DESCRIPTION", "MONEY IN", "MONEY OUT", "BALANCE",
    "MONEY", "OUT",  # sometimes split across lines
    "DATE TYPE DESCRIPTION MONEY IN M OU O T NEY BALANCE",
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


@dataclass
class Txn:
    tx_date: str
    tx_type: str
    category: str
    description: str
    money_in: Optional[float]
    money_out: Optional[float]
    balance: Optional[float]
    raw: str


def clean_line(s: str) -> str:
    s = s.replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    # Some extractions end lines with "null"
    if s.endswith("null"):
        s = s[:-4].strip()
    return s


def parse_eur_amount(euro_text: str) -> Optional[float]:
    """
    Accepts strings like "€9.31", "€ 1,500.00", "€1,226.89" and returns float.
    """
    m = re.search(r"€\s*([\d.,]+)", euro_text)
    if not m:
        return None
    amount_str = m.group(1).replace(",", "")
    if "." not in amount_str:
        amount_str += ".00"
    try:
        return float(amount_str)
    except ValueError:
        return None


def pdf_to_lines(pdf_path: str) -> List[str]:
    """
    Extract text lines from all pages with tolerances to reduce weird splitting.
    """
    lines: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            txt = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
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
        if start is not None and l in ("BALANCE OVERVIEW", "TRANSACTION OVERVIEW"):
            end = i
            break
    if start is None:
        raise ValueError("ACCOUNT TRANSACTIONS not found")
    return lines[start:end] if end is not None else lines[start:]


def filter_noise(lines: List[str]) -> List[str]:
    out: List[str] = []
    for l in lines:
        if l in DROP_EXACT:
            continue
        if any(sub in l for sub in DROP_SUBSTRINGS):
            continue
        out.append(l)
    return out


def split_into_blocks(lines: List[str]) -> List[List[str]]:
    """
    New transaction whenever a line begins with "DD Mon".
    Works for:
      - "03 Dec"
      - "03 Dec Card"
      - "03 Dec Transfer Incoming transfer ..."
    """
    blocks: List[List[str]] = []
    cur: List[str] = []
    for l in lines:
        if DATE_START_RE.match(l):
            if cur:
                blocks.append(cur)
            cur = [l]
        else:
            if cur:  # ignore any preamble before first date
                cur.append(l)
    if cur:
        blocks.append(cur)
    return blocks


def detect_type(tokens: List[str]) -> str:
    for t in tokens:
        if t in KNOWN_TYPES:
            return t
    return ""


def build_description(block: List[str]) -> str:
    """
    Reconstruct description by keeping line order and removing structural markers and amounts.
    """
    desc_parts: List[str] = []
    for l in block[1:]:  # skip date line
        if l in KNOWN_TYPES:
            continue
        if l == "Transaction":
            continue
        if l in DROP_EXACT or any(sub in l for sub in DROP_SUBSTRINGS):
            continue

        clean = l
        clean = YEAR_ANYWHERE_RE.sub("", clean)
        clean = EUR_ANY_RE.sub("", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        if clean:
            desc_parts.append(clean)

    description = " ".join(desc_parts).strip(" -")
    return description


def parse_block(block: List[str]) -> Txn:
    raw = " ".join(block)

    # Tokens
    tokens: List[str] = []
    for l in block:
        tokens.extend(l.split())

    # Date
    m = DATE_START_RE.match(block[0])
    if not m:
        raise ValueError(f"Cannot parse date from block start: {block[0]!r}")
    day = int(m.group(1))
    mon = MONTHS[m.group(2)]

    y = YEAR_ANYWHERE_RE.search(raw)
    if not y:
        raise ValueError(f"No year found in block starting {block[0]!r}")
    year = int(y.group(0))
    tx_date = date(year, mon, day).isoformat()

    # Type
    tx_type = detect_type(tokens)

    # Amounts: last € is balance; previous € is txn amount
    euros = EUR_ANY_RE.findall(raw)
    amounts = [parse_eur_amount(e) for e in euros]
    amounts = [a for a in amounts if a is not None]

    balance = amounts[-1] if amounts else None
    money_in = None
    money_out = None
    if len(amounts) >= 2:
        amt = amounts[-2]
        # Reward is valid and treated as investment gain (money in)
        if tx_type in ("Reward", "Interest", "Earnings", "Transfer"):
            money_in = amt
        else:
            money_out = amt

    description = build_description(block)

    # Categorization: reward as investment gain
    category = "Investment Gain" if tx_type == "Reward" else ""

    return Txn(
        tx_date=tx_date,
        tx_type=tx_type,
        category=category,
        description=description,
        money_in=money_in,
        money_out=money_out,
        balance=balance,
        raw=raw,
    )


def should_ignore_incoming_transfer(tx: Txn, ignore_ibans: Set[str]) -> bool:
    """
    Ignore incoming transfers from configured bank account(s).

    Matches your example:
      "Incoming transfer from AA DA FONTOURA CJ (NL70ABNA0842740635)"
    """
    if tx.tx_type != "Transfer":
        return False
    if "Incoming transfer from" not in tx.description:
        return False
    return any(iban in tx.description for iban in ignore_ibans)


def parse_pdf(pdf_path: str) -> List[Txn]:
    lines = pdf_to_lines(pdf_path)
    tx_lines = filter_noise(slice_transactions(lines))
    blocks = split_into_blocks(tx_lines)
    return [parse_block(b) for b in blocks]


def to_dict(tx: Txn) -> Dict[str, Optional[str]]:
    return {
        "date": tx.tx_date,
        "type": tx.tx_type,
        "category": tx.category,
        "description": tx.description,
        "money_in": tx.money_in,
        "money_out": tx.money_out,
        "balance": tx.balance,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", help="Path to Trade Republic statement PDF")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--out", default="out.csv", help="Output CSV file")
    parser.add_argument(
        "--ignore-iban",
        action="append",
        default=["NL70ABNA0842740635"],  # default as requested
        help="IBAN to ignore for 'Incoming transfer from ... (IBAN)'. Can be repeated.",
    )
    parser.add_argument(
        "--keep-trade",
        action="store_true",
        help="Keep Trade lines (default: exclude Trade lines).",
    )
    parser.add_argument(
        "--expected-count",
        type=int,
        default=None,
        help="If set, exits with error if final filtered count != expected.",
    )
    args = parser.parse_args()

    # Parse
    all_tx = parse_pdf(args.pdf)

    # Apply filters
    ignore_ibans = set(args.ignore_iban)

    filtered: List[Txn] = []
    for tx in all_tx:
        if not args.keep_trade and tx.tx_type == "Trade":
            continue
        if should_ignore_incoming_transfer(tx, ignore_ibans):
            continue
        filtered.append(tx)

    # Write CSV
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["date", "type", "category", "description", "money_in", "money_out", "balance"],
        )
        w.writeheader()
        for tx in filtered:
            w.writerow(to_dict(tx))

    # Summary
    def count_by_type(txs: List[Txn]) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for t in txs:
            out[t.tx_type] = out.get(t.tx_type, 0) + 1
        return out

    print(f"Parsed blocks (raw): {len(all_tx)}")
    print(f"Parsed blocks by type (raw): {count_by_type(all_tx)}")
    print(f"Filtered transactions: {len(filtered)}")
    print(f"Filtered transactions by type: {count_by_type(filtered)}")
    print(f"Wrote CSV: {args.out}")

    if args.debug:
        print("\nDEBUG OUTPUT:")
        for tx in filtered:
            print(f"- {tx.tx_date} | {tx.tx_type} | In: {tx.money_in} | Out: {tx.money_out}")
            print(f"  Desc: {tx.description}")
            print(f"  Raw: {tx.raw}")
            print("")

    if args.expected_count is not None and len(filtered) != args.expected_count:
        raise SystemExit(
            f"Expected {args.expected_count} transactions after filtering, got {len(filtered)}."
        )


if __name__ == "__main__":
    main()