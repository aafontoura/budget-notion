"""Result reporting and analysis for LLM testbed."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .models import TestResult, TestRun

logger = logging.getLogger(__name__)


class TestReporter:
    """Generate reports from test runs."""

    @staticmethod
    def save_results(test_run: TestRun, output_path: str | Path) -> None:
        """
        Save test results to JSON file.

        Args:
            test_run: TestRun object with results.
            output_path: Path to save the results.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "suite_name": test_run.suite_name,
            "timestamp": test_run.timestamp,
            "total_tests": len(test_run.results),
            "stats": test_run.get_accuracy_stats(),
            "results": [
                {
                    "transaction_id": r.transaction_id,
                    "prompt_id": r.prompt_id,
                    "model_id": r.model_id,
                    "actual_category": r.actual_category,
                    "actual_subcategory": r.actual_subcategory,
                    "actual_summary": r.actual_summary,
                    "confidence": r.confidence,
                    "expected_category": r.expected_category,
                    "expected_subcategory": r.expected_subcategory,
                    "expected_summary": r.expected_summary,
                    "raw_response": r.raw_response,
                    "processing_time": r.processing_time,
                    "error": r.error,
                    "category_correct": r.category_correct,
                    "subcategory_correct": r.subcategory_correct,
                    "summary_acceptable": r.summary_acceptable,
                    "notes": r.notes,
                }
                for r in test_run.results
            ],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Results saved to: {output_path}")

    @staticmethod
    def load_results(input_path: str | Path) -> TestRun:
        """
        Load test results from JSON file.

        Args:
            input_path: Path to the results file.

        Returns:
            TestRun object.
        """
        input_path = Path(input_path)

        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        test_run = TestRun(
            suite_name=data["suite_name"],
            timestamp=data["timestamp"],
        )

        for result_data in data["results"]:
            result = TestResult(
                transaction_id=result_data["transaction_id"],
                prompt_id=result_data["prompt_id"],
                model_id=result_data["model_id"],
                actual_category=result_data.get("actual_category"),
                actual_subcategory=result_data.get("actual_subcategory"),
                actual_summary=result_data.get("actual_summary"),
                confidence=result_data.get("confidence", 0.0),
                expected_category=result_data.get("expected_category"),
                expected_subcategory=result_data.get("expected_subcategory"),
                expected_summary=result_data.get("expected_summary"),
                raw_response=result_data.get("raw_response", ""),
                processing_time=result_data.get("processing_time", 0.0),
                error=result_data.get("error"),
                category_correct=result_data.get("category_correct"),
                subcategory_correct=result_data.get("subcategory_correct"),
                summary_acceptable=result_data.get("summary_acceptable"),
                notes=result_data.get("notes", ""),
            )
            test_run.add_result(result)

        logger.info(f"Loaded results from: {input_path}")
        return test_run

    @staticmethod
    def print_summary(test_run: TestRun) -> None:
        """Print a summary of test results to console."""
        print("\n" + "=" * 80)
        print(f"📊 Test Results Summary: {test_run.suite_name}")
        print(f"   Timestamp: {test_run.timestamp}")
        print("=" * 80)

        stats = test_run.get_accuracy_stats()

        print(f"\n📈 Overall Statistics:")
        print(f"   Total tests: {stats.get('total_tests', 0)}")
        print(f"   Evaluated: {stats.get('evaluated', 0)}")

        if stats.get("category_accuracy") is not None:
            print(f"   Category accuracy: {stats['category_accuracy']:.1%}")

        if stats.get("subcategory_accuracy") is not None:
            print(f"   Subcategory accuracy: {stats['subcategory_accuracy']:.1%}")

        if stats.get("summary_acceptable_rate") is not None:
            print(f"   Summary acceptable rate: {stats['summary_acceptable_rate']:.1%}")

        print(f"   Avg confidence: {stats.get('avg_confidence', 0):.2f}")
        print(f"   Avg processing time: {stats.get('avg_processing_time', 0):.2f}s")

        # Per-model statistics
        model_ids = set(r.model_id for r in test_run.results)
        if len(model_ids) > 1:
            print(f"\n🤖 Per-Model Statistics:")
            for model_id in sorted(model_ids):
                model_results = test_run.get_results_for_model(model_id)
                evaluated = [r for r in model_results if r.category_correct is not None]

                if evaluated:
                    cat_correct = sum(1 for r in evaluated if r.category_correct)
                    avg_time = sum(r.processing_time for r in evaluated) / len(evaluated)

                    print(f"\n   {model_id}:")
                    print(f"      Tests: {len(model_results)} ({len(evaluated)} evaluated)")
                    print(f"      Category accuracy: {cat_correct / len(evaluated):.1%}")
                    print(f"      Avg time: {avg_time:.2f}s")

        # Per-prompt statistics
        prompt_ids = set(r.prompt_id for r in test_run.results)
        if len(prompt_ids) > 1:
            print(f"\n📝 Per-Prompt Statistics:")
            for prompt_id in sorted(prompt_ids):
                prompt_results = test_run.get_results_for_prompt(prompt_id)
                evaluated = [r for r in prompt_results if r.category_correct is not None]

                if evaluated:
                    cat_correct = sum(1 for r in evaluated if r.category_correct)

                    print(f"\n   {prompt_id}:")
                    print(f"      Tests: {len(prompt_results)} ({len(evaluated)} evaluated)")
                    print(f"      Category accuracy: {cat_correct / len(evaluated):.1%}")

        # Errors
        errors = [r for r in test_run.results if r.error]
        if errors:
            print(f"\n❌ Errors ({len(errors)}):")
            for result in errors[:5]:  # Show first 5 errors
                print(f"   {result.transaction_id} | {result.model_id} | {result.error}")
            if len(errors) > 5:
                print(f"   ... and {len(errors) - 5} more")

        print("\n" + "=" * 80 + "\n")

    @staticmethod
    def generate_comparison_table(
        test_run: TestRun,
        output_path: Optional[str | Path] = None,
    ) -> str:
        """
        Generate a markdown comparison table.

        Args:
            test_run: TestRun object with results.
            output_path: Optional path to save the markdown file.

        Returns:
            Markdown table as string.
        """
        lines = [
            f"# Test Results: {test_run.suite_name}",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Test Run:** {test_run.timestamp}",
            "",
            "## Summary",
            "",
        ]

        stats = test_run.get_accuracy_stats()
        lines.append(f"- Total tests: {stats.get('total_tests', 0)}")
        lines.append(f"- Evaluated: {stats.get('evaluated', 0)}")

        if stats.get("category_accuracy") is not None:
            lines.append(f"- Category accuracy: {stats['category_accuracy']:.1%}")

        lines.append("")
        lines.append("## Results by Transaction")
        lines.append("")
        lines.append("| Transaction | Model | Prompt | Category | Subcategory | Confidence | Time (s) | Error |")
        lines.append("|-------------|-------|--------|----------|-------------|------------|----------|-------|")

        for result in test_run.results:
            category = result.actual_category or "-"
            subcategory = result.actual_subcategory or "-"
            confidence = f"{result.confidence:.2f}" if result.confidence else "-"
            time_str = f"{result.processing_time:.2f}" if result.processing_time else "-"
            error = result.error[:30] + "..." if result.error and len(result.error) > 30 else (result.error or "-")

            # Add checkmark/cross for correctness
            if result.category_correct is True:
                category = f"✅ {category}"
            elif result.category_correct is False:
                category = f"❌ {category}"

            lines.append(
                f"| {result.transaction_id} | {result.model_id} | {result.prompt_id} | "
                f"{category} | {subcategory} | {confidence} | {time_str} | {error} |"
            )

        markdown = "\n".join(lines)

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown)
            logger.info(f"Comparison table saved to: {output_path}")

        return markdown
