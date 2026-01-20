"""Response parser for LLM categorization output."""

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

from src.domain.data.categories import CATEGORY_STRUCTURE

logger = logging.getLogger(__name__)


@dataclass
class CategorizationResult:
    """Result of AI categorization."""

    category: str
    subcategory: Optional[str]
    confidence: float
    raw_response: str  # For debugging
    error_type: Optional[str] = None  # Type of error if categorization failed (e.g., "rate_limit", "timeout")
    retry_after: Optional[int] = None  # Seconds to wait before retrying (for rate limit errors)
    retriable: bool = True  # Whether the error is retriable


class ResponseParserError(Exception):
    """Exception raised for response parsing errors."""

    pass


class CategorizationResponseParser:
    """
    Parse and validate LLM categorization responses.

    Handles malformed JSON, invalid categories, and confidence scores.
    """

    def __init__(self):
        """Initialize response parser with valid categories."""
        self.valid_categories = set(CATEGORY_STRUCTURE.keys())
        self.category_subcategories = {
            cat: set(subcats.keys())
            for cat, subcats in CATEGORY_STRUCTURE.items()
        }

    def parse_category_response(self, response: str) -> CategorizationResult:
        """
        Parse category-only response (step 1).

        Expected format: {"category": "CATEGORY_NAME", "confidence": 0.95}

        Args:
            response: LLM response string.

        Returns:
            CategorizationResult with category and confidence.

        Raises:
            ResponseParserError: If parsing fails.
        """
        try:
            # Extract JSON from response (handle extra text)
            json_data = self._extract_json(response)

            category = json_data.get("category", "").strip()
            confidence = float(json_data.get("confidence", 0.5))

            # Validate category
            category = self._validate_category(category)

            # Clamp confidence
            confidence = max(0.0, min(1.0, confidence))

            return CategorizationResult(
                category=category,
                subcategory=None,
                confidence=confidence,
                raw_response=response,
            )

        except Exception as e:
            logger.warning(f"Failed to parse category response: {e}")
            logger.debug(f"Raw response: {response}")

            # Fallback
            return CategorizationResult(
                category="Miscellaneous",
                subcategory=None,
                confidence=0.0,
                raw_response=response,
            )

    def parse_subcategory_response(
        self, response: str, category: str
    ) -> CategorizationResult:
        """
        Parse subcategory response (step 2).

        Expected format: {"subcategory": "Subcategory Name", "confidence": 0.90}

        Args:
            response: LLM response string.
            category: Already determined category.

        Returns:
            CategorizationResult with subcategory and confidence.

        Raises:
            ResponseParserError: If parsing fails.
        """
        try:
            # Extract JSON from response
            json_data = self._extract_json(response)

            subcategory = json_data.get("subcategory", "").strip()
            confidence = float(json_data.get("confidence", 0.5))

            # Validate subcategory
            subcategory = self._validate_subcategory(category, subcategory)

            # Clamp confidence
            confidence = max(0.0, min(1.0, confidence))

            return CategorizationResult(
                category=category,
                subcategory=subcategory,
                confidence=confidence,
                raw_response=response,
            )

        except Exception as e:
            logger.warning(f"Failed to parse subcategory response: {e}")
            logger.debug(f"Raw response: {response}")

            # Fallback to first subcategory of category
            fallback_subcat = self._get_fallback_subcategory(category)

            return CategorizationResult(
                category=category,
                subcategory=fallback_subcat,
                confidence=0.3,  # Low confidence due to fallback
                raw_response=response,
            )

    def parse_full_response(self, response: str) -> CategorizationResult:
        """
        Parse full categorization response (category + subcategory).

        Expected format: {
            "category": "CATEGORY",
            "subcategory": "Subcategory",
            "confidence": 0.90
        }

        Args:
            response: LLM response string.

        Returns:
            CategorizationResult with all fields.
        """
        try:
            # Extract JSON from response
            json_data = self._extract_json(response)

            category = json_data.get("category", "").strip()
            subcategory = json_data.get("subcategory", "").strip()
            confidence = float(json_data.get("confidence", 0.5))

            # Validate
            category = self._validate_category(category)
            subcategory = self._validate_subcategory(category, subcategory)

            # Clamp confidence
            confidence = max(0.0, min(1.0, confidence))

            return CategorizationResult(
                category=category,
                subcategory=subcategory,
                confidence=confidence,
                raw_response=response,
            )

        except Exception as e:
            logger.warning(f"Failed to parse full response: {e}")
            logger.debug(f"Raw response: {response}")

            # Complete fallback
            return CategorizationResult(
                category="Miscellaneous",
                subcategory="Uncategorized",
                confidence=0.0,
                raw_response=response,
            )

    def parse_batch_response(
        self, response: str, transaction_count: int
    ) -> list[CategorizationResult]:
        """
        Parse batch categorization response (category only).

        Expected format: [
            {"id": 1, "category": "FOOD & GROCERIES", "confidence": 0.95},
            {"id": 2, "category": "TRANSPORTATION", "confidence": 0.88}
        ]

        Args:
            response: LLM response string.
            transaction_count: Expected number of transactions.

        Returns:
            List of CategorizationResult objects.
        """
        try:
            # Extract JSON array
            json_data = self._extract_json(response)

            if not isinstance(json_data, list):
                raise ValueError("Response is not a JSON array")

            results = []
            for item in json_data:
                category = item.get("category", "").strip()
                confidence = float(item.get("confidence", 0.5))

                # Validate
                category = self._validate_category(category)
                confidence = max(0.0, min(1.0, confidence))

                results.append(
                    CategorizationResult(
                        category=category,
                        subcategory=None,
                        confidence=confidence,
                        raw_response=json.dumps(item),
                    )
                )

            return results

        except Exception as e:
            logger.warning(f"Failed to parse batch response: {e}")
            logger.debug(f"Raw response: {response}")

            # Fallback: return generic results for all transactions
            return [
                CategorizationResult(
                    category="Miscellaneous",
                    subcategory=None,
                    confidence=0.0,
                    raw_response=response,
                )
                for _ in range(transaction_count)
            ]

    def parse_optimized_batch_response(
        self, response: str, transaction_ids: list[str]
    ) -> dict[str, CategorizationResult]:
        """
        Parse optimized batch response (category + subcategory).

        Expected format: [
            {"id": "uuid-1", "category": "FOOD & GROCERIES", "subcategory": "Groceries", "confidence": 0.95},
            {"id": "uuid-2", "category": "TRANSPORTATION", "subcategory": "Public Transit", "confidence": 0.88}
        ]

        Args:
            response: LLM response string.
            transaction_ids: List of expected transaction IDs.

        Returns:
            Dict mapping transaction ID to CategorizationResult.
        """
        try:
            # Extract JSON array
            json_data = self._extract_json(response)

            if not isinstance(json_data, list):
                raise ValueError("Response is not a JSON array")

            results = {}
            for item in json_data:
                txn_id = str(item.get("id", "")).strip()
                category = item.get("category", "").strip()
                subcategory = item.get("subcategory", "").strip()
                confidence = float(item.get("confidence", 0.5))

                # Validate
                category = self._validate_category(category)
                subcategory = self._validate_subcategory(category, subcategory)
                confidence = max(0.0, min(1.0, confidence))

                results[txn_id] = CategorizationResult(
                    category=category,
                    subcategory=subcategory,
                    confidence=confidence,
                    raw_response=json.dumps(item),
                )

            # Fill missing IDs with fallback
            for txn_id in transaction_ids:
                if txn_id not in results:
                    logger.warning(f"Missing result for transaction ID: {txn_id}")
                    results[txn_id] = CategorizationResult(
                        category="Miscellaneous",
                        subcategory="Uncategorized",
                        confidence=0.0,
                        raw_response="Missing from batch response",
                    )

            return results

        except Exception as e:
            logger.warning(f"Failed to parse optimized batch response: {e}")
            logger.debug(f"Raw response: {response}")

            # Fallback: return generic results for all transaction IDs
            return {
                txn_id: CategorizationResult(
                    category="Miscellaneous",
                    subcategory="Uncategorized",
                    confidence=0.0,
                    raw_response=response,
                )
                for txn_id in transaction_ids
            }

    def _extract_json(self, response: str) -> dict | list:
        """
        Extract JSON from response (handles extra text before/after).

        Args:
            response: Raw LLM response.

        Returns:
            Parsed JSON object or array.

        Raises:
            json.JSONDecodeError: If no valid JSON found.
        """
        # Try direct parsing first
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try to find JSON in response
        # Look for {...} or [...]
        json_match = re.search(r"(\{.*\}|\[.*\])", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # If all fails, raise error
        raise json.JSONDecodeError("No valid JSON found", response, 0)

    def _validate_category(self, category: str) -> str:
        """
        Validate and correct category name.

        Args:
            category: Category from LLM.

        Returns:
            Valid category name.
        """
        # Exact match
        if category in self.valid_categories:
            return category

        # Case-insensitive match
        for valid_cat in self.valid_categories:
            if category.lower() == valid_cat.lower():
                return valid_cat

        # Partial match
        for valid_cat in self.valid_categories:
            if category.lower() in valid_cat.lower():
                return valid_cat
            if valid_cat.lower() in category.lower():
                return valid_cat

        # No match - fallback
        logger.warning(f"Invalid category '{category}', using Miscellaneous")
        return "Miscellaneous"

    def _validate_subcategory(
        self, category: str, subcategory: str
    ) -> Optional[str]:
        """
        Validate subcategory for given category.

        Args:
            category: Category name.
            subcategory: Subcategory from LLM.

        Returns:
            Valid subcategory name or None.
        """
        valid_subcats = self.category_subcategories.get(category, set())

        if not subcategory:
            return None

        # Exact match
        if subcategory in valid_subcats:
            return subcategory

        # Case-insensitive match
        for valid_subcat in valid_subcats:
            if subcategory.lower() == valid_subcat.lower():
                return valid_subcat

        # Partial match
        for valid_subcat in valid_subcats:
            if subcategory.lower() in valid_subcat.lower():
                return valid_subcat
            if valid_subcat.lower() in subcategory.lower():
                return valid_subcat

        # No match - return first subcategory as fallback
        logger.warning(
            f"Invalid subcategory '{subcategory}' for category '{category}'"
        )
        return self._get_fallback_subcategory(category)

    def _get_fallback_subcategory(self, category: str) -> Optional[str]:
        """
        Get fallback subcategory for a category.

        Args:
            category: Category name.

        Returns:
            First subcategory or None.
        """
        subcats = self.category_subcategories.get(category, set())
        return next(iter(subcats), None) if subcats else None
