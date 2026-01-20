"""Prompt builder for transaction categorization."""

import logging
from typing import Optional

from src.domain.data.categories import CATEGORY_STRUCTURE

logger = logging.getLogger(__name__)


class CategorizationPromptBuilder:
    """
    Build prompts for LLM transaction categorization.

    Optimized for small models (8B parameters) with minimal token usage.
    Uses two-step approach: category first, then subcategory.
    """

    def __init__(self):
        """Initialize prompt builder with category structure."""
        self.categories = list(CATEGORY_STRUCTURE.keys())
        self.category_subcategories = {
            cat: list(subcats.keys())
            for cat, subcats in CATEGORY_STRUCTURE.items()
        }

    def build_category_prompt(self, transaction: dict) -> str:
        """
        Build prompt for categorizing transaction (step 1: category only).

        Args:
            transaction: Dict with keys: date, description, amount.

        Returns:
            Prompt string for LLM.
        """
        description = transaction.get("description", "")
        amount = transaction.get("amount", "0")
        date = transaction.get("date", "")

        prompt = f"""Categorize this transaction. Reply ONLY with JSON.

Categories: {", ".join(self.categories)}

Transaction:
- Date: {date}
- Description: "{description}"
- Amount: €{amount}

JSON format (no explanation):
{{"category": "CATEGORY_NAME", "confidence": 0.95}}

Example: {{"category": "FOOD & GROCERIES", "confidence": 0.90}}"""

        return prompt

    def build_subcategory_prompt(
        self, transaction: dict, category: str
    ) -> str:
        """
        Build prompt for determining subcategory (step 2).

        Args:
            transaction: Dict with keys: date, description, amount.
            category: Already determined category.

        Returns:
            Prompt string for LLM.
        """
        description = transaction.get("description", "")
        amount = transaction.get("amount", "0")

        subcategories = self.category_subcategories.get(category, [])
        subcats_str = ", ".join(subcategories[:15])  # Limit to avoid token overflow

        prompt = f"""Choose subcategory for this {category} transaction. Reply ONLY with JSON.

Subcategories: {subcats_str}

Transaction: "{description}" | Amount: €{amount}

JSON format (no explanation):
{{"subcategory": "Subcategory Name", "confidence": 0.90}}

Example: {{"subcategory": "Groceries", "confidence": 0.92}}"""

        return prompt

    def build_batch_category_prompt(self, transactions: list[dict]) -> str:
        """
        Build prompt for batch categorization (multiple transactions).

        DEPRECATED: Use build_optimized_batch_prompt for better performance.

        Args:
            transactions: List of transaction dicts.

        Returns:
            Prompt string for batch processing.
        """
        transactions_text = ""
        for i, txn in enumerate(transactions, 1):
            desc = txn.get("description", "")
            amount = txn.get("amount", "0")
            transactions_text += f"{i}. \"{desc}\" | €{amount}\n"

        prompt = f"""Categorize these transactions. Reply ONLY with JSON array.

Categories: {", ".join(self.categories)}

Transactions:
{transactions_text}

JSON format (no explanation, array of objects):
[
  {{"id": 1, "category": "FOOD & GROCERIES", "confidence": 0.95}},
  {{"id": 2, "category": "TRANSPORTATION", "confidence": 0.88}}
]"""

        return prompt

    def _clean_description(self, desc: str, max_length: int = 100) -> str:
        """
        Clean and truncate transaction description for LLM processing.

        Removes technical bank data (IBAN, BIC, reference codes) and keeps
        only the meaningful merchant/transaction information.

        Args:
            desc: Original transaction description.
            max_length: Maximum length to return (default: 100 chars).

        Returns:
            Cleaned description.
        """
        import re

        # Remove common technical patterns
        # Split on common separators that indicate technical data
        parts = desc.split(" - /")  # Split before technical SEPA data
        if len(parts) > 1:
            desc = parts[0]  # Take only the meaningful part before technical data

        # Remove IBAN/BIC patterns
        desc = desc.split("/TRTP/")[0]
        desc = desc.split("/IBAN/")[0]
        desc = desc.split("/BIC/")[0]
        desc = desc.split("/REMI/")[0]
        desc = desc.split("/EREF/")[0]
        desc = desc.split("/CSID/")[0]
        desc = desc.split("/NAME/")[0]
        desc = desc.split("/MARF/")[0]

        # Remove " - from" and " - to" patterns (keeps text before these)
        desc = desc.split(" - from ")[0]
        desc = desc.split(" - to ")[0]

        # Remove Tikkie ID patterns: "Tikkie ID 001151040331, " -> extract only the meaningful part
        tikkie_match = re.search(r'Tikkie ID \d+,\s*(.+)', desc)
        if tikkie_match:
            # Extract just the description part (e.g., "Christmas dinner")
            desc = tikkie_match.group(1)

        # Remove IBAN patterns within text: NL\d{2}[A-Z]{4}\d+
        desc = re.sub(r'\bNL\d{2}[A-Z]{4}\d+\b', '', desc)

        # Remove payment method prefixes: "BEA, Google Pay " or "BEA, Apple Pay "
        desc = re.sub(r'^BEA,\s*(?:Google Pay|Apple Pay)\s+', '', desc)

        # Remove transaction reference codes like "PAS223 NR:18061315"
        desc = re.sub(r',?\s*PAS\d+\s+NR:[A-Z0-9]+', '', desc)

        # Remove date/time patterns like "31.12.25/12:38"
        desc = re.sub(r',?\s*\d{2}\.\d{2}\.\d{2}/\d{2}:\d{2}', '', desc)

        # Remove location patterns like ", Rumst, Land: BEL"
        desc = re.sub(r',\s*Land:\s*[A-Z]{3}', '', desc)

        # Remove "Van" (from) in Tikkie descriptions if followed by name
        desc = re.sub(r',?\s*Van\s+[A-Z][a-z]+.*$', '', desc)

        # Clean up multiple spaces and commas
        desc = re.sub(r'\s{2,}', ' ', desc)
        desc = re.sub(r',\s*,', ',', desc)
        desc = desc.strip(' ,')

        # Truncate to max length
        if len(desc) > max_length:
            desc = desc[:max_length] + "..."

        return desc.strip()

    def build_optimized_batch_prompt(self, transactions: list[dict]) -> str:
        """
        Build optimized batch prompt for full categorization (category + subcategory).

        Optimizations:
        - No currency symbols (saves tokens)
        - Compact format with IDs
        - Single-shot categorization (category + subcategory together)
        - Minimal category list
        - Clean descriptions (removes technical bank data)

        Args:
            transactions: List of transaction dicts with 'id', 'description', 'amount'.

        Returns:
            Compact prompt string for batch processing.
        """
        # Build compact transaction list
        txn_lines = []
        for txn in transactions:
            txn_id = txn.get("id", "")
            desc = txn.get("description", "")
            amount = txn.get("amount", "0")
            # Clean description to remove technical bank data and truncate
            desc_clean = self._clean_description(desc, max_length=100)
            # Remove currency symbol, compact format
            txn_lines.append(f'{{"id":"{txn_id}","desc":"{desc_clean}","amt":{amount}}}')

        txn_block = ",\n".join(txn_lines)

        # Compact category list (top-level only for brevity)
        categories_compact = ", ".join(self.categories[:12])  # Limit to 12 main categories

        num_txns = len(transactions)

        prompt = f"""Categorize these {num_txns} transactions and return ONLY a JSON array with EXACTLY {num_txns} results. No other text.

Categories: {categories_compact}

Transactions ({num_txns} total):
[
{txn_block}
]

IMPORTANT: Return array with EXACTLY {num_txns} objects (IDs 0 to {num_txns-1}), each with:
- "id": transaction ID (string)
- "category": one of the categories above
- "subcategory": specific subcategory name
- "confidence": number between 0.0 and 1.0 (e.g., 0.85 for 85% confident)

Output (JSON array only):"""

        return prompt

    def build_full_categorization_prompt(self, transaction: dict) -> str:
        """
        Build single-step full categorization prompt (category + subcategory).

        Use this for single transactions when two-step is not needed.

        Args:
            transaction: Dict with keys: date, description, amount.

        Returns:
            Prompt string for LLM.
        """
        description = transaction.get("description", "")
        amount = transaction.get("amount", "0")
        date = transaction.get("date", "")

        # Build category -> subcategory mapping
        cat_subcat_text = ""
        for cat, subcats in list(self.category_subcategories.items())[:12]:
            subcats_short = subcats[:5]  # First 5 subcategories
            cat_subcat_text += f"- {cat}: {', '.join(subcats_short)}\n"

        prompt = f"""Categorize this transaction. Reply ONLY with JSON.

Categories and Subcategories:
{cat_subcat_text}

Transaction:
- Date: {date}
- Description: "{description}"
- Amount: €{amount}

JSON format (no explanation):
{{"category": "CATEGORY", "subcategory": "Subcategory", "confidence": 0.90}}

Example: {{"category": "FOOD & GROCERIES", "subcategory": "Groceries", "confidence": 0.95}}"""

        return prompt

    def get_category_subcategories(self, category: str) -> list[str]:
        """
        Get subcategories for a specific category.

        Args:
            category: Category name.

        Returns:
            List of subcategory names.
        """
        return self.category_subcategories.get(category, [])
