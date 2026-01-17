"""
Auto-tagging service for transactions.

Automatically applies tags to transactions based on category,
sub-category, and other attributes.
"""

import logging
from typing import List

from src.domain.data.categories import get_tags_for_subcategory
from src.domain.entities.transaction import Transaction

logger = logging.getLogger(__name__)


class AutoTaggerService:
    """
    Service for automatically applying tags to transactions.
    
    Tags are applied based on:
    - Sub-category matching
    - Category patterns
    - Transaction attributes (reimbursable, etc.)
    """

    def apply_tags(self, transaction: Transaction, category: str, subcategory: str | None = None) -> Transaction:
        """
        Apply auto-tags to a transaction based on category/subcategory.
        
        Args:
            transaction: Transaction to tag.
            category: Main category.
            subcategory: Sub-category (if applicable).
            
        Returns:
            Transaction with auto-tags applied.
        """
        tags_to_add = self._determine_tags(transaction, category, subcategory)
        
        if not tags_to_add:
            return transaction
        
        # Add tags that aren't already present
        current_tags = set(transaction.tags)
        new_tags = [tag for tag in tags_to_add if tag not in current_tags]
        
        if not new_tags:
            return transaction
        
        logger.debug(f"Auto-tagging transaction with: {new_tags}")
        
        # Apply tags
        updated = transaction
        for tag in new_tags:
            updated = updated.add_tag(tag)
        
        return updated

    def _determine_tags(self, transaction: Transaction, category: str, subcategory: str | None) -> List[str]:
        """
        Determine which tags should be applied.
        
        Args:
            transaction: Transaction to analyze.
            category: Main category.
            subcategory: Sub-category.
            
        Returns:
            List of tags to apply.
        """
        tags = []
        
        # Get tags based on subcategory
        if subcategory:
            tags.extend(get_tags_for_subcategory(subcategory))
        
        # Add reimbursable tag if applicable
        if transaction.reimbursable:
            tags.append("reimbursable")
        
        # Add frequency tags based on category patterns
        frequency_tag = self._infer_frequency_tag(category, subcategory)
        if frequency_tag:
            tags.append(frequency_tag)
        
        return list(set(tags))  # Remove duplicates

    def _infer_frequency_tag(self, category: str, subcategory: str | None) -> str | None:
        """
        Infer frequency tag from category/subcategory name.
        
        Args:
            category: Main category.
            subcategory: Sub-category.
            
        Returns:
            Frequency tag or None.
        """
        if not subcategory:
            return None
        
        subcategory_lower = subcategory.lower()
        
        # Check for frequency indicators in name
        if "monthly" in subcategory_lower or "month" in subcategory_lower:
            return "monthly"
        elif "yearly" in subcategory_lower or "year" in subcategory_lower or "annual" in subcategory_lower:
            return "yearly"
        elif "quarterly" in subcategory_lower or "quarter" in subcategory_lower:
            return "quarterly"
        elif "weekly" in subcategory_lower or "week" in subcategory_lower:
            return "weekly"
        
        # Infer from specific subcategories
        recurring_subcategories = {
            "monthly": [
                "mortgage", "insurance", "subscription", "rent", "salary",
                "utilities", "internet", "mobile", "gym", "membership"
            ],
            "yearly": [
                "tax", "annual", "vakantiegeld", "bonus", "holiday allowance"
            ],
        }
        
        for freq, keywords in recurring_subcategories.items():
            if any(keyword in subcategory_lower for keyword in keywords):
                return freq
        
        return None


# Singleton instance
auto_tagger = AutoTaggerService()
