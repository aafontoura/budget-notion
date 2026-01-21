"""Load test suites from YAML/JSON files."""

import json
import logging
from pathlib import Path
from typing import Any

import yaml

from .models import ModelConfig, PromptConfig, TestSuite, TestTransaction

logger = logging.getLogger(__name__)


class TestSuiteLoader:
    """Load test suites from YAML or JSON files."""

    @staticmethod
    def load_from_file(file_path: str | Path) -> TestSuite:
        """
        Load a test suite from a YAML or JSON file.

        Args:
            file_path: Path to the test suite file.

        Returns:
            TestSuite object.

        Raises:
            ValueError: If the file format is not supported.
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Test suite file not found: {file_path}")

        logger.info(f"Loading test suite from: {file_path}")

        # Determine file format and load
        if file_path.suffix in [".yaml", ".yml"]:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        elif file_path.suffix == ".json":
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            raise ValueError(
                f"Unsupported file format: {file_path.suffix}. "
                "Use .yaml, .yml, or .json"
            )

        return TestSuiteLoader._parse_test_suite(data)

    @staticmethod
    def _parse_test_suite(data: dict[str, Any]) -> TestSuite:
        """Parse test suite data from dict."""
        suite = TestSuite(
            name=data.get("name", "Unnamed Test Suite"),
            description=data.get("description", ""),
        )

        # Parse transactions
        for txn_data in data.get("transactions", []):
            transaction = TestTransaction(
                id=txn_data["id"],
                description=txn_data["description"],
                amount=float(txn_data["amount"]),
                date=txn_data["date"],
                expected_category=txn_data.get("expected_category"),
                expected_subcategory=txn_data.get("expected_subcategory"),
                expected_summary=txn_data.get("expected_summary"),
                notes=txn_data.get("notes"),
            )
            suite.add_transaction(transaction)

        # Parse prompts
        for prompt_data in data.get("prompts", []):
            prompt = PromptConfig(
                id=prompt_data["id"],
                name=prompt_data["name"],
                description=prompt_data.get("description", ""),
                template=prompt_data["template"],
                variables=prompt_data.get("variables", {}),
            )
            suite.add_prompt(prompt)

        # Parse models
        for model_data in data.get("models", []):
            model = ModelConfig(
                id=model_data["id"],
                provider=model_data["provider"],
                model_name=model_data["model_name"],
                temperature=model_data.get("temperature", 0.1),
                max_tokens=model_data.get("max_tokens", 100),
                base_url=model_data.get("base_url"),
                api_key=model_data.get("api_key"),
            )
            suite.add_model(model)

        logger.info(
            f"Loaded test suite '{suite.name}': "
            f"{len(suite.transactions)} transactions, "
            f"{len(suite.prompts)} prompts, "
            f"{len(suite.models)} models"
        )

        return suite

    @staticmethod
    def save_to_file(suite: TestSuite, file_path: str | Path) -> None:
        """
        Save a test suite to a YAML or JSON file.

        Args:
            suite: TestSuite object to save.
            file_path: Path to save the file.
        """
        file_path = Path(file_path)

        data = {
            "name": suite.name,
            "description": suite.description,
            "transactions": [
                {
                    "id": txn.id,
                    "description": txn.description,
                    "amount": txn.amount,
                    "date": txn.date,
                    "expected_category": txn.expected_category,
                    "expected_subcategory": txn.expected_subcategory,
                    "expected_summary": txn.expected_summary,
                    "notes": txn.notes,
                }
                for txn in suite.transactions
            ],
            "prompts": [
                {
                    "id": prompt.id,
                    "name": prompt.name,
                    "description": prompt.description,
                    "template": prompt.template,
                    "variables": prompt.variables,
                }
                for prompt in suite.prompts
            ],
            "models": [
                {
                    "id": model.id,
                    "provider": model.provider,
                    "model_name": model.model_name,
                    "temperature": model.temperature,
                    "max_tokens": model.max_tokens,
                    "base_url": model.base_url,
                    "api_key": model.api_key,
                }
                for model in suite.models
            ],
        }

        # Save based on file extension
        if file_path.suffix in [".yaml", ".yml"]:
            with open(file_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        elif file_path.suffix == ".json":
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        else:
            raise ValueError(
                f"Unsupported file format: {file_path.suffix}. "
                "Use .yaml, .yml, or .json"
            )

        logger.info(f"Saved test suite to: {file_path}")
