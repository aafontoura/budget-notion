"""Test header detection logic."""

header = ['DATE TYPE', 'DESCRIPTION', '', '', '', '', '', 'MONEY I', 'N M OUO TNEY BALANCE']

header_str = " ".join(str(cell or "").replace("\n", " ").upper() for cell in header)

print(f"Header string: '{header_str}'")
print()

print(f'"DATE" in header_str: {"DATE" in header_str}')
print(f'"MONEY" in header_str: {"MONEY" in header_str}')
print(f'"BALANCE" in header_str: {"BALANCE" in header_str}')
print(f'"OPENING BALANCE" not in header_str: {"OPENING BALANCE" not in header_str}')
print(f'"PRODUCT" not in header_str: {"PRODUCT" not in header_str}')
print()

is_tr_header = (
    "DATE" in header_str
    and ("MONEY" in header_str or "GELD" in header_str)
    and "BALANCE" in header_str
    # Additional check: exclude summary rows (have "OPENING BALANCE" or "PRODUCT")
    and "OPENING BALANCE" not in header_str
    and "PRODUCT" not in header_str
)

print(f"is_tr_header: {is_tr_header}")
