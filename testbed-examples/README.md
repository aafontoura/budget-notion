# LLM Testbed Examples

This directory contains example test suites for evaluating LLM performance on transaction categorization and summary generation.

## Overview

The LLM testbed allows you to:
- Test different prompt variations systematically
- Compare multiple LLM models (local and commercial)
- Evaluate categorization and summary quality
- Generate detailed reports and comparisons

## Files

- `categorization-test-suite.yaml` - Example test suite for categorization
- `README.md` - This file

## Test Suite Structure

A test suite YAML file contains:

### 1. Transactions
Test transactions with expected outcomes:
```yaml
transactions:
  - id: "txn-001"
    description: "Albert Heijn Amsterdam"
    amount: -42.50
    date: "2025-01-15"
    expected_category: "Food & Groceries"
    expected_subcategory: "Groceries"
    notes: "Common supermarket transaction"
```

### 2. Prompts
Different prompt variations to test:
```yaml
prompts:
  - id: "system-full-v1"
    name: "System Full Categorization (Current)"
    description: "Current production prompt"
    template: |
      Categorize this transaction...
      {description} | {amount} | {date}
    variables:
      custom_var: "value"
```

Template variables:
- `{description}` - Transaction description
- `{amount}` - Transaction amount
- `{date}` - Transaction date
- Any custom variables from `variables` field

### 3. Models
LLM models to test:
```yaml
models:
  - id: "llama-3.1-8b"
    provider: "ollama"  # ollama, openai, anthropic, google, groq
    model_name: "llama3.1:8b"
    temperature: 0.1
    max_tokens: 100
    base_url: "http://localhost:11434"  # Optional
    api_key: "sk-..."  # Optional, or use env vars
```

## Running Tests

### Via CLI (recommended)
```bash
# Run full test suite
python -m src.interfaces.cli.main llm-test \
  --suite testbed-examples/categorization-test-suite.yaml \
  --output results/test-run-001.json

# Run specific prompts only
python -m src.interfaces.cli.main llm-test \
  --suite testbed-examples/categorization-test-suite.yaml \
  --prompts system-full-v1,compact-v1 \
  --output results/test-run-002.json

# Run specific models only
python -m src.interfaces.cli.main llm-test \
  --suite testbed-examples/categorization-test-suite.yaml \
  --models llama-3.1-8b,mistral-7b \
  --output results/test-run-003.json

# Generate comparison report
python -m src.interfaces.cli.main llm-report \
  --results results/test-run-001.json \
  --format markdown \
  --output results/report.md
```

### Via Python
```python
from src.testbed.loader import TestSuiteLoader
from src.testbed.runner import TestRunner
from src.testbed.reporter import TestReporter

# Load test suite
suite = TestSuiteLoader.load_from_file("testbed-examples/categorization-test-suite.yaml")

# Run tests
runner = TestRunner()
test_run = runner.run_test_suite(suite)

# Save results
TestReporter.save_results(test_run, "results/test-run.json")

# Print summary
TestReporter.print_summary(test_run)

# Generate markdown report
TestReporter.generate_comparison_table(test_run, "results/report.md")
```

## Evaluation

After running tests, you can manually evaluate the results:

1. Load the results JSON file
2. For each result, set:
   - `category_correct`: true/false
   - `subcategory_correct`: true/false
   - `summary_acceptable`: true/false (if testing summaries)
   - `notes`: Any observations
3. Save the updated JSON file
4. Re-generate the report to see accuracy statistics

Example:
```python
from src.testbed.reporter import TestReporter

# Load results
test_run = TestReporter.load_results("results/test-run-001.json")

# Manually update a result
test_run.results[0].category_correct = True
test_run.results[0].subcategory_correct = False
test_run.results[0].notes = "Category correct but subcategory too specific"

# Save updated results
TestReporter.save_results(test_run, "results/test-run-001-evaluated.json")

# Generate new report with accuracy stats
TestReporter.print_summary(test_run)
```

## Best Practices

1. **Start small**: Test with 5-10 transactions first
2. **Use diverse examples**: Include edge cases and common patterns
3. **Test incrementally**: Add one prompt variant at a time
4. **Evaluate systematically**: Review all results, not just errors
5. **Document findings**: Use the `notes` field to capture insights
6. **Version your prompts**: Use descriptive IDs like "system-full-v1", "system-full-v2"
7. **Compare models**: Test the same prompts across different models
8. **Track over time**: Save all test runs to track improvements

## Example Workflow

1. **Baseline**: Run current production prompt with production model
2. **Variations**: Create 3-4 prompt variations
3. **Test**: Run all variations with the same model
4. **Evaluate**: Manually review and mark correct/incorrect
5. **Analyze**: Compare accuracy, confidence, and processing time
6. **Iterate**: Refine best-performing prompt and repeat
7. **Model comparison**: Test best prompt across different models
8. **Deploy**: Update production prompt with best-performing variant

## Tips

### For Better Categorization
- Include clear examples in prompts (few-shot learning)
- Limit category options to reduce confusion
- Use structured output format (JSON)
- Set low temperature (0.1) for consistency
- Test with real transaction descriptions from your data

### For Better Summaries
- Show examples of good vs. bad summaries
- Specify desired length/format
- Include context about what makes a good summary
- Test with transactions that have confusing descriptions

### For Faster Testing
- Use local Ollama models for quick iteration
- Reduce max_tokens to minimum needed
- Run commercial models only after local validation
- Use smaller test sets during development

## Troubleshooting

**Tests fail with connection errors**
- Verify Ollama is running: `ollama list`
- Check base_url is correct (default: http://localhost:11434)
- For commercial APIs, verify API keys are set

**Results show low accuracy**
- Review raw_response field to see what model actually returned
- Check if prompt is clear and unambiguous
- Try few-shot examples
- Test with a more capable model

**Tests are too slow**
- Reduce batch size for local models
- Use faster models (e.g., llama3.2:3b instead of llama3.1:8b)
- Reduce max_tokens
- Run fewer combinations (filter prompts/models)

## Advanced Usage

### Custom Evaluation Metrics
You can extend `TestResult` to track custom metrics and calculate them in `TestRun.get_accuracy_stats()`.

### Batch Testing
For large test sets, consider splitting into multiple YAML files and running them separately.

### A/B Testing
Run the same test suite at different times to track model performance over time or test model updates.

### CI/CD Integration
Automate testing in your CI/CD pipeline to catch regressions in categorization quality.
