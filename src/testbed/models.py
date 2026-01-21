"""Data models for LLM testbed."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TestTransaction:
    """A test transaction with expected output."""

    id: str
    description: str
    amount: float
    date: str
    expected_category: Optional[str] = None
    expected_subcategory: Optional[str] = None
    expected_summary: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class PromptConfig:
    """Configuration for a prompt variant."""

    id: str
    name: str
    description: str
    template: str
    variables: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelConfig:
    """Configuration for an LLM model."""

    id: str
    provider: str  # "ollama", "openai", "anthropic", "google", "groq"
    model_name: str
    temperature: float = 0.1
    max_tokens: int = 100
    base_url: Optional[str] = None
    api_key: Optional[str] = None


@dataclass
class TestResult:
    """Result of a single test run."""

    transaction_id: str
    prompt_id: str
    model_id: str

    # Actual outputs
    actual_category: Optional[str] = None
    actual_subcategory: Optional[str] = None
    actual_summary: Optional[str] = None
    confidence: float = 0.0

    # Expected outputs (for comparison)
    expected_category: Optional[str] = None
    expected_subcategory: Optional[str] = None
    expected_summary: Optional[str] = None

    # Metadata
    raw_response: str = ""
    processing_time: float = 0.0
    error: Optional[str] = None

    # Manual evaluation fields
    category_correct: Optional[bool] = None
    subcategory_correct: Optional[bool] = None
    summary_acceptable: Optional[bool] = None
    notes: str = ""


@dataclass
class TestSuite:
    """A collection of test transactions, prompts, and models."""

    name: str
    description: str
    transactions: list[TestTransaction] = field(default_factory=list)
    prompts: list[PromptConfig] = field(default_factory=list)
    models: list[ModelConfig] = field(default_factory=list)

    def add_transaction(self, transaction: TestTransaction) -> None:
        """Add a transaction to the test suite."""
        self.transactions.append(transaction)

    def add_prompt(self, prompt: PromptConfig) -> None:
        """Add a prompt configuration to the test suite."""
        self.prompts.append(prompt)

    def add_model(self, model: ModelConfig) -> None:
        """Add a model configuration to the test suite."""
        self.models.append(model)


@dataclass
class TestRun:
    """A complete test run with all results."""

    suite_name: str
    timestamp: str
    results: list[TestResult] = field(default_factory=list)

    def add_result(self, result: TestResult) -> None:
        """Add a test result to the run."""
        self.results.append(result)

    def get_results_for_model(self, model_id: str) -> list[TestResult]:
        """Get all results for a specific model."""
        return [r for r in self.results if r.model_id == model_id]

    def get_results_for_prompt(self, prompt_id: str) -> list[TestResult]:
        """Get all results for a specific prompt."""
        return [r for r in self.results if r.prompt_id == prompt_id]

    def get_accuracy_stats(self) -> dict[str, Any]:
        """Calculate accuracy statistics across all results."""
        total = len(self.results)
        if total == 0:
            return {}

        # Only count results that have manual evaluation
        evaluated = [r for r in self.results if r.category_correct is not None]

        if not evaluated:
            return {
                "total_tests": total,
                "evaluated": 0,
                "category_accuracy": None,
                "subcategory_accuracy": None,
                "summary_acceptable_rate": None,
            }

        category_correct = sum(1 for r in evaluated if r.category_correct)
        subcategory_correct = sum(
            1 for r in evaluated
            if r.subcategory_correct is not None and r.subcategory_correct
        )
        summary_acceptable = sum(
            1 for r in evaluated
            if r.summary_acceptable is not None and r.summary_acceptable
        )

        return {
            "total_tests": total,
            "evaluated": len(evaluated),
            "category_accuracy": category_correct / len(evaluated) if evaluated else 0,
            "subcategory_accuracy": (
                subcategory_correct / len([r for r in evaluated if r.subcategory_correct is not None])
                if any(r.subcategory_correct is not None for r in evaluated)
                else None
            ),
            "summary_acceptable_rate": (
                summary_acceptable / len([r for r in evaluated if r.summary_acceptable is not None])
                if any(r.summary_acceptable is not None for r in evaluated)
                else None
            ),
            "avg_confidence": sum(r.confidence for r in evaluated) / len(evaluated),
            "avg_processing_time": sum(r.processing_time for r in evaluated) / len(evaluated),
        }
