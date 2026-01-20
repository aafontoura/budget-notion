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

    def build_optimized_batch_prompt(self, transactions: list[dict]) -> str:
        """
        Build optimized batch prompt for full categorization (category + subcategory).

        Optimizations:
        - No currency symbols (saves tokens)
        - Compact format with IDs
        - Single-shot categorization (category + subcategory together)
        - Minimal category list

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
            # Remove currency symbol, compact format
            txn_lines.append(f'{{"id":"{txn_id}","desc":"{desc}","amt":{amount}}}')

        txn_block = ",\n".join(txn_lines)

        # Compact category list (top-level only for brevity)
        categories_compact = ", ".join(self.categories[:12])  # Limit to 12 main categories

        prompt = f"""Categorize these transactions and return ONLY a JSON array. No other text.

Categories: {categories_compact}

Transactions:
[
{txn_block}
]

Return JSON array with format:
[{{"id":"1","category":"FOOD & GROCERIES","subcategory":"Groceries","confidence":0.95}},{{"id":"2","category":"TRANSPORTATION","subcategory":"Public Transit","confidence":0.88}}]

Output (JSON only):"""

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
