# Budget Notion - Test Suite

This directory contains comprehensive tests for the Budget Notion application, designed for both local development and CI/CD pipelines.

## Test Structure

```
tests/
├── test_domain/              # Domain entity tests (24 tests)
│   └── test_transaction.py   # Transaction entity with tags & reimbursement
├── test_application/         # Application layer tests (12 tests)
│   └── test_auto_tagger.py   # Auto-tagging service tests
└── test_integration/         # Integration tests (22 tests)
    └── test_cli_integration.py  # End-to-end CLI tests
```

## Running Tests

### Quick Start

```bash
# Install dependencies
make install-dev

# Run all tests (excluding Notion)
make test

# Run unit tests only (fast)
make test-unit

# Run integration tests only
make test-integration

# Run with coverage report
make coverage
```

### Pytest Commands

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_domain/test_transaction.py

# Run specific test class
pytest tests/test_integration/test_cli_integration.py::TestAddTransaction

# Run specific test
pytest tests/test_integration/test_cli_integration.py::TestAddTransaction::test_add_basic_transaction

# Run with verbose output
pytest -v

# Run without coverage (faster)
pytest --no-cov

# Run tests matching pattern
pytest -k "tag" -v

# Run with coverage report
pytest --cov=src --cov-report=html
```

### Test Markers

Tests are organized with markers for selective execution:

```bash
# Exclude Notion tests (requires credentials)
pytest -m "not notion"

# Run only integration tests
pytest -m "integration"

# Exclude slow tests
pytest -m "not slow"

# Run only Notion tests
pytest -m "notion"
```

## Test Categories

### 1. Unit Tests (36 tests)

**Domain Tests** (`test_domain/`)
- Transaction entity validation (24 tests)
  - Basic CRUD operations
  - Tag management (normalization, add, remove)
  - Reimbursement tracking (status calculation, partial payments)
  - Immutable pattern verification

**Application Tests** (`test_application/`)
- Auto-tagging service (12 tests)
  - Asset tags (car, bike, baby)
  - Flexibility tags (fixed-expense, variable-expense, discretionary)
  - Frequency tags (monthly, quarterly, yearly)
  - Tag preservation and deduplication

**Coverage:** 92% for domain entities, 91% for auto-tagger

### 2. Integration Tests (22 tests)

**CLI Integration Tests** (`test_integration/`)
- Configuration management
- Transaction creation (basic, with all fields, reimbursable)
- Transaction listing and filtering (category, tags, reimbursement status)
- Pending reimbursements tracking
- Reimbursement recording (full, partial)
- Tag totals calculation
- Statistics reporting
- Auto-tagging verification
- End-to-end workflows

**Test Database:** Each test uses an isolated temporary SQLite database

### 3. Notion Integration Tests (3 tests, requires credentials)

Tests marked with `@pytest.mark.notion` require:
- `NOTION_TOKEN` environment variable
- `NOTION_DATABASE_ID` environment variable

**Tests included:**
- Basic transaction creation
- Transaction with tags and auto-tagging
- Reimbursable transaction creation

**Note:** Ensure your Notion database has the required properties: Tags (multi-select), Reimbursable (checkbox), Expected Reimbursement (number), Actual Reimbursement (number), and Reimbursement Status (select).

## CI/CD Integration

### GitHub Actions Workflow

The repository includes a comprehensive CI/CD pipeline (`.github/workflows/ci.yml`):

**Jobs:**
1. **lint** - Code quality checks (black, ruff, mypy)
2. **unit-tests** - Run on Python 3.12 & 3.13
3. **integration-tests** - SQLite integration tests
4. **notion-tests** - Notion integration (main branch only)
5. **docker-build** - Build and test Docker image
6. **all-tests-passed** - Gate for merge requirements

**Triggers:**
- Push to `main` or `develop`
- Pull requests to `main` or `develop`
- Manual workflow dispatch

**Coverage Reporting:**
- Codecov integration for coverage tracking
- HTML and XML reports generated

### Local CI Simulation

```bash
# Run all CI checks locally
make ci-test
```

This runs:
1. Code formatting check
2. Linting
3. Unit tests
4. Integration tests
5. Docker build

## Test Fixtures

### Common Fixtures

```python
@pytest.fixture
def test_db():
    """Temporary SQLite database for each test"""

@pytest.fixture
def repository(test_db):
    """SQLite repository instance"""
```

### Example Usage

```python
def test_something(test_db, repository):
    # test_db is path to temporary database
    # repository is SQLiteTransactionRepository instance
    # Both are automatically cleaned up after test
```

## Writing New Tests

### Unit Test Example

```python
def test_transaction_feature():
    """Test description."""
    transaction = Transaction(
        date=datetime.now(),
        description="Test",
        amount=Decimal("-50.00"),
        category="Test Category",
    )

    assert transaction.amount == Decimal("-50.00")
```

### Integration Test Example

```python
def test_cli_command(test_db, repository):
    """Test CLI command."""
    result = run_cli_command(
        ["command", "--arg", "value"],
        env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
    )

    assert result.returncode == 0
    assert "expected output" in result.stdout

    # Verify in database
    transactions = repository.list()
    assert len(transactions) == 1
```

## Coverage Goals

| Component | Current | Target |
|-----------|---------|--------|
| Domain Entities | 92% | 95% |
| Auto-Tagger | 91% | 95% |
| Use Cases | 100% | 100% |
| Repositories | 27% | 80% |
| CLI | 35% | 70% |
| **Overall** | **37%** | **80%** |

## Troubleshooting

### Tests Failing

```bash
# Clean up test artifacts
make clean

# Reinstall dependencies
make install-dev

# Run specific failing test with verbose output
pytest tests/path/to/test.py::test_name -vv
```

### Coverage Not Generating

```bash
# Ensure pytest-cov is installed
pip install pytest-cov

# Run with explicit coverage flags
pytest --cov=src --cov-report=term-missing
```

### Integration Tests Timeout

```bash
# Increase timeout in pytest
pytest --timeout=300

# Or run without integration tests
pytest tests/test_domain/ tests/test_application/
```

## Test Data

### Sample Transactions

Tests use realistic data:
- Categories: Food & Dining, Transportation, Income, etc.
- Amounts: Various expense and income amounts
- Tags: car, bike, baby, fixed-expense, discretionary, etc.
- Reimbursements: Group dinners with partial/full payments

### Database Schema

Integration tests verify:
- Schema migration (SQLite)
- Property mapping (Notion)
- Data type conversions
- Index creation
- Constraint enforcement

## Performance

**Benchmark (MacBook M2):**
- Unit tests: ~0.11s (36 tests)
- Integration tests: ~10.3s (21 tests)
- Total: ~10.4s (57 tests)

**Tips for Faster Tests:**
```bash
# Skip coverage calculation
pytest --no-cov

# Run in parallel (with pytest-xdist)
pytest -n auto

# Run only fast tests
pytest -m "not slow"
```

## Next Steps

1. **Increase Coverage**
   - Add repository integration tests
   - Add CLI command tests
   - Add error handling tests

2. **Add Performance Tests**
   - Benchmark bulk imports
   - Test large dataset queries
   - Measure auto-tagging performance

3. **Add End-to-End Tests**
   - CSV import workflow
   - Budget analysis workflow
   - Multi-month reporting

4. **Notion Schema Tests**
   - Update Notion database schema
   - Enable Notion integration tests
   - Test cross-platform sync

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Codecov Documentation](https://docs.codecov.com/)

---

**Last Updated:** 2026-01-18
**Test Suite Version:** 2.1
**Total Tests:** 60 (60 passing - 36 unit, 21 integration, 3 Notion)
