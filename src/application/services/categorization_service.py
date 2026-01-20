"""Transaction categorization service using Ollama LLM."""

import logging
from typing import Optional

from src.infrastructure.ai.ollama_client import OllamaClient, OllamaError
from src.infrastructure.ai.prompt_builder import CategorizationPromptBuilder
from src.infrastructure.ai.response_parser import (
    CategorizationResponseParser,
    CategorizationResult,
)

logger = logging.getLogger(__name__)


class CategorizationService:
    """
    Service for categorizing transactions using LLM.

    Uses a two-step approach:
    1. Determine category (fast, 12 options)
    2. Determine subcategory (focused, 5-15 options per category)

    Includes batching and rule-based shortcuts for efficiency.
    """

    def __init__(
        self,
        ollama_client: OllamaClient,
        prompt_builder: CategorizationPromptBuilder,
        response_parser: CategorizationResponseParser,
        batch_size: int = 35,
        confidence_threshold: float = 0.9,
    ):
        """
        Initialize categorization service.

        Args:
            ollama_client: Ollama LLM client.
            prompt_builder: Prompt builder for LLM.
            response_parser: Parser for LLM responses.
            batch_size: Number of transactions to process in one batch (default: 35).
                       Optimized for CPU inference - 30-40 transactions per batch.
            confidence_threshold: Confidence threshold for skipping subcategory step (default: 0.9).
        """
        self.ollama_client = ollama_client
        self.prompt_builder = prompt_builder
        self.response_parser = response_parser
        self.batch_size = batch_size
        self.confidence_threshold = confidence_threshold

        logger.info(
            f"Initialized CategorizationService (batch_size={batch_size}, "
            f"threshold={confidence_threshold})"
        )

    def categorize_single(self, transaction: dict) -> CategorizationResult:
        """
        Categorize a single transaction using two-step approach.

        Args:
            transaction: Dict with keys: date, description, amount.

        Returns:
            CategorizationResult with category, subcategory, and confidence.
        """
        try:
            # Step 1: Determine category
            category_prompt = self.prompt_builder.build_category_prompt(transaction)
            category_response = self.ollama_client.generate(category_prompt)
            category_result = self.response_parser.parse_category_response(
                category_response
            )

            logger.debug(
                f"Category: {category_result.category} "
                f"(confidence: {category_result.confidence:.2f})"
            )

            # Step 2: Determine subcategory
            # If confidence is very high, use rule-based subcategory inference
            if category_result.confidence >= self.confidence_threshold:
                # For now, use LLM. Later we can add rule-based shortcuts.
                pass

            subcategory_prompt = self.prompt_builder.build_subcategory_prompt(
                transaction, category_result.category
            )
            subcategory_response = self.ollama_client.generate(subcategory_prompt)
            final_result = self.response_parser.parse_subcategory_response(
                subcategory_response, category_result.category
            )

            logger.debug(
                f"Subcategory: {final_result.subcategory} "
                f"(confidence: {final_result.confidence:.2f})"
            )

            return final_result

        except OllamaError as e:
            logger.error(f"Ollama error during categorization: {e}")
            # Return fallback result
            return CategorizationResult(
                category="Miscellaneous",
                subcategory="Uncategorized",
                confidence=0.0,
                raw_response=str(e),
            )

    def categorize_batch(self, transactions: list[dict]) -> list[CategorizationResult]:
        """
        Categorize multiple transactions efficiently using batching.

        DEPRECATED: Use categorize_batch_optimized for better performance.

        Args:
            transactions: List of transaction dicts.

        Returns:
            List of CategorizationResult objects (same order as input).
        """
        if not transactions:
            return []

        results = []

        # Process in batches for Step 1 (category determination)
        for i in range(0, len(transactions), self.batch_size):
            batch = transactions[i : i + self.batch_size]

            try:
                # Step 1: Batch category determination
                batch_prompt = self.prompt_builder.build_batch_category_prompt(batch)
                batch_response = self.ollama_client.generate(batch_prompt)
                batch_results = self.response_parser.parse_batch_response(
                    batch_response, len(batch)
                )

                logger.info(
                    f"Categorized batch {i // self.batch_size + 1} "
                    f"({len(batch)} transactions)"
                )

                results.extend(batch_results)

            except OllamaError as e:
                logger.error(f"Batch categorization failed: {e}")
                # Fallback to individual processing for this batch
                for txn in batch:
                    results.append(self.categorize_single(txn))

        # Step 2: Determine subcategories individually
        # (Subcategories are context-specific, so we process one by one)
        for i, (txn, result) in enumerate(zip(transactions, results)):
            try:
                subcategory_prompt = self.prompt_builder.build_subcategory_prompt(
                    txn, result.category
                )
                subcategory_response = self.ollama_client.generate(subcategory_prompt)
                subcategory_result = self.response_parser.parse_subcategory_response(
                    subcategory_response, result.category
                )

                # Update result with subcategory
                results[i] = subcategory_result

                logger.debug(
                    f"Transaction {i + 1}: {result.category} > "
                    f"{subcategory_result.subcategory} "
                    f"(confidence: {subcategory_result.confidence:.2f})"
                )

            except OllamaError as e:
                logger.warning(f"Subcategory determination failed for txn {i + 1}: {e}")
                # Keep category-only result with fallback subcategory
                fallback_subcat = self.response_parser._get_fallback_subcategory(
                    result.category
                )
                results[i] = CategorizationResult(
                    category=result.category,
                    subcategory=fallback_subcat,
                    confidence=0.3,
                    raw_response=str(e),
                )

        return results

    def categorize_batch_optimized(
        self, transactions: list[dict]
    ) -> dict[str, CategorizationResult]:
        """
        Optimized batch categorization (category + subcategory in one call).

        Performance optimizations:
        - Single LLM call per batch (30-40 transactions)
        - No currency symbols (fewer tokens)
        - Compact JSON format
        - keep_alive to prevent model reload
        - Reduced num_predict for faster generation

        Args:
            transactions: List of transaction dicts with 'id', 'description', 'amount'.

        Returns:
            Dict mapping transaction ID to CategorizationResult.
        """
        if not transactions:
            return {}

        all_results = {}
        total_batches = (len(transactions) + self.batch_size - 1) // self.batch_size

        # Process in optimized batches
        for batch_num, i in enumerate(
            range(0, len(transactions), self.batch_size), start=1
        ):
            batch = transactions[i : i + self.batch_size]
            batch_ids = [str(txn.get("id", "")) for txn in batch]

            try:
                logger.info(
                    f"Processing batch {batch_num}/{total_batches} "
                    f"({len(batch)} transactions)..."
                )

                # Build optimized batch prompt
                batch_prompt = self.prompt_builder.build_optimized_batch_prompt(batch)

                # Generate with batch mode (optimized parameters)
                batch_response = self.ollama_client.generate(
                    batch_prompt, is_batch=True
                )

                # Parse response
                batch_results = self.response_parser.parse_optimized_batch_response(
                    batch_response, batch_ids
                )

                all_results.update(batch_results)

                logger.info(
                    f"Batch {batch_num}/{total_batches} complete "
                    f"({len(batch_results)} results)"
                )

            except OllamaError as e:
                logger.error(f"Batch {batch_num} categorization failed: {e}")
                logger.info(f"Falling back to individual processing for batch {batch_num}")

                # Fallback: process individually
                for txn in batch:
                    txn_id = str(txn.get("id", ""))
                    try:
                        result = self.categorize_full(txn)
                        all_results[txn_id] = result
                    except Exception as fallback_error:
                        logger.error(
                            f"Individual categorization failed for {txn_id}: {fallback_error}"
                        )
                        all_results[txn_id] = CategorizationResult(
                            category="Miscellaneous",
                            subcategory="Uncategorized",
                            confidence=0.0,
                            raw_response=str(fallback_error),
                        )

        return all_results

    def categorize_full(self, transaction: dict) -> CategorizationResult:
        """
        Categorize using single-step full prompt (category + subcategory).

        This is less efficient than two-step but can be useful for single transactions
        when you want to minimize LLM calls.

        Args:
            transaction: Dict with keys: date, description, amount.

        Returns:
            CategorizationResult with category, subcategory, and confidence.
        """
        try:
            full_prompt = self.prompt_builder.build_full_categorization_prompt(
                transaction
            )
            response = self.ollama_client.generate(full_prompt)
            result = self.response_parser.parse_full_response(response)

            logger.debug(
                f"Full categorization: {result.category} > {result.subcategory} "
                f"(confidence: {result.confidence:.2f})"
            )

            return result

        except OllamaError as e:
            logger.error(f"Full categorization failed: {e}")
            return CategorizationResult(
                category="Miscellaneous",
                subcategory="Uncategorized",
                confidence=0.0,
                raw_response=str(e),
            )

    def test_connection(self) -> bool:
        """
        Test connection to Ollama server.

        Returns:
            True if connection successful, False otherwise.
        """
        return self.ollama_client.test_connection()
