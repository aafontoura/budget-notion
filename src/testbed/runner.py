"""Test runner for LLM testbed."""

import logging
import time
from datetime import datetime
from typing import Optional

from src.infrastructure.ai.base_llm_client import BaseLLMClient
from src.infrastructure.ai.litellm_client import LiteLLMClient
from src.infrastructure.ai.ollama_client import OllamaClient
from src.infrastructure.ai.response_parser import CategorizationResponseParser

from .models import (
    ModelConfig,
    PromptConfig,
    TestResult,
    TestRun,
    TestSuite,
    TestTransaction,
)

logger = logging.getLogger(__name__)


class TestRunner:
    """
    Run LLM tests systematically.

    Tests different prompt variations and model configurations
    against a set of test transactions.
    """

    def __init__(self):
        """Initialize test runner."""
        self.response_parser = CategorizationResponseParser()

    def run_test_suite(
        self,
        suite: TestSuite,
        prompt_ids: Optional[list[str]] = None,
        model_ids: Optional[list[str]] = None,
        transaction_ids: Optional[list[str]] = None,
    ) -> TestRun:
        """
        Run a test suite.

        Args:
            suite: TestSuite to run.
            prompt_ids: List of prompt IDs to test (None = all).
            model_ids: List of model IDs to test (None = all).
            transaction_ids: List of transaction IDs to test (None = all).

        Returns:
            TestRun with all results.
        """
        # Filter test items
        prompts = (
            [p for p in suite.prompts if p.id in prompt_ids]
            if prompt_ids
            else suite.prompts
        )
        models = (
            [m for m in suite.models if m.id in model_ids]
            if model_ids
            else suite.models
        )
        transactions = (
            [t for t in suite.transactions if t.id in transaction_ids]
            if transaction_ids
            else suite.transactions
        )

        logger.info("=" * 80)
        logger.info(f"🧪 Running Test Suite: {suite.name}")
        logger.info(f"   {len(transactions)} transactions × {len(prompts)} prompts × {len(models)} models")
        logger.info(f"   Total tests: {len(transactions) * len(prompts) * len(models)}")
        logger.info("=" * 80)

        # Create test run
        test_run = TestRun(
            suite_name=suite.name,
            timestamp=datetime.now().isoformat(),
        )

        # Run tests for each combination
        test_count = 0
        total_tests = len(transactions) * len(prompts) * len(models)

        for model_config in models:
            logger.info("─" * 80)
            logger.info(f"🤖 Testing Model: {model_config.id} ({model_config.provider}/{model_config.model_name})")
            logger.info("─" * 80)

            # Create LLM client for this model
            client = self._create_llm_client(model_config)

            for prompt_config in prompts:
                logger.info(f"📝 Testing Prompt: {prompt_config.name}")

                for transaction in transactions:
                    test_count += 1
                    logger.info(
                        f"   [{test_count}/{total_tests}] Testing transaction: {transaction.id}"
                    )

                    result = self._run_single_test(
                        transaction, prompt_config, model_config, client
                    )
                    test_run.add_result(result)

        logger.info("=" * 80)
        logger.info(f"✅ Test Suite Complete: {test_count} tests run")
        logger.info("=" * 80)

        return test_run

    def _create_llm_client(self, model_config: ModelConfig) -> BaseLLMClient:
        """Create an LLM client from model configuration."""
        if model_config.provider == "ollama":
            return OllamaClient(
                base_url=model_config.base_url or "http://localhost:11434",
                model=model_config.model_name,
                timeout=120,
            )
        else:
            # Use LiteLLM for all other providers
            return LiteLLMClient(
                model=model_config.model_name,
                api_key=model_config.api_key,
                base_url=model_config.base_url,
                temperature=model_config.temperature,
                timeout=120,
            )

    def _run_single_test(
        self,
        transaction: TestTransaction,
        prompt_config: PromptConfig,
        model_config: ModelConfig,
        client: BaseLLMClient,
    ) -> TestResult:
        """Run a single test."""
        # Build prompt from template
        prompt = self._build_prompt(transaction, prompt_config)

        # Run test
        start_time = time.time()
        error = None
        actual_category = None
        actual_subcategory = None
        actual_summary = None
        confidence = 0.0
        raw_response = ""

        try:
            # Generate response
            raw_response = client.generate(
                prompt,
                is_batch=False,
                max_tokens=model_config.max_tokens,
                temperature=model_config.temperature,
            )

            # Parse response
            # Try to parse as full categorization response
            parsed = self.response_parser.parse_full_response(raw_response)
            actual_category = parsed.category
            actual_subcategory = parsed.subcategory
            confidence = parsed.confidence

            # If the prompt was for summary generation, extract summary
            if "summary" in prompt_config.id.lower():
                # For summary prompts, the response is the summary itself
                actual_summary = raw_response.strip()

        except Exception as e:
            error = str(e)
            logger.error(f"      Error: {error}")

        processing_time = time.time() - start_time

        # Create result
        result = TestResult(
            transaction_id=transaction.id,
            prompt_id=prompt_config.id,
            model_id=model_config.id,
            actual_category=actual_category,
            actual_subcategory=actual_subcategory,
            actual_summary=actual_summary,
            confidence=confidence,
            expected_category=transaction.expected_category,
            expected_subcategory=transaction.expected_subcategory,
            expected_summary=transaction.expected_summary,
            raw_response=raw_response,
            processing_time=processing_time,
            error=error,
        )

        # Log result
        if error:
            logger.error(f"      ❌ Test failed: {error}")
        else:
            logger.info(
                f"      ✓ Category: {actual_category} | Subcategory: {actual_subcategory} | "
                f"Confidence: {confidence:.2f} | Time: {processing_time:.2f}s"
            )

        return result

    def _build_prompt(
        self, transaction: TestTransaction, prompt_config: PromptConfig
    ) -> str:
        """
        Build a prompt from template and transaction data.

        Template variables:
        - {description}: Transaction description
        - {amount}: Transaction amount
        - {date}: Transaction date
        - Any custom variables from prompt_config.variables
        """
        template = prompt_config.template

        # Build variable mapping
        variables = {
            "description": transaction.description,
            "amount": transaction.amount,
            "date": transaction.date,
            **prompt_config.variables,
        }

        # Replace variables in template
        prompt = template
        for key, value in variables.items():
            prompt = prompt.replace(f"{{{key}}}", str(value))

        return prompt
