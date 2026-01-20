# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Budget Notion is a personal finance aggregator with AI-powered categorization and Notion integration. It follows **clean architecture** principles with strict separation of concerns, enabling easy swapping of UI/storage layers without modifying core business logic.

**Key Architectural Principle**: The domain layer has ZERO dependencies on external services. Infrastructure adapters implement domain interfaces, allowing Notion to be swapped for SQLite, PostgreSQL, Obsidian, or any other storage/UI without touching core code.

## Development Commands

### Environment Setup
```bash
# Activate virtual environment (required for all commands)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Testing
```bash
# Run all tests (unit + integration, excluding Notion)
make test
# OR: REPOSITORY_TYPE=sqlite pytest tests/ -v -m "not notion"

# Run unit tests only (fast)
make test-unit
# OR: pytest tests/test_domain/ tests/test_application/ -v

# Run integration tests (SQLite only)
make test-integration
# OR: REPOSITORY_TYPE=sqlite pytest tests/test_integration/ -v -m "not notion"

# Run with coverage
make coverage

# Run Notion integration tests (requires credentials)
make test-notion
# OR: REPOSITORY_TYPE=notion pytest tests/test_integration/ -v -m "notion"

# Run all tests including Notion
make test-all
# OR: pytest tests/ -v

# Run tests without coverage (faster)
make test-fast
```

### Code Quality
```bash
# Run linters (black + ruff + mypy)
make lint

# Format code
make format

# Auto-fix linting issues
make fix

# Type checking only
make type-check
```

### Running the Application
```bash
# CLI entry point
python -m src.interfaces.cli.main --help

# Add transaction
python -m src.interfaces.cli.main add \
  --description "Coffee" \
  --amount -5.50 \
  --category "Food & Dining"

# Import CSV
python -m src.interfaces.cli.main import-csv \
  path/to/statement.csv \
  --bank ing \
  --account "Checking"

# Import PDF with AI categorization (requires Ollama)
python -m src.interfaces.cli.main import-pdf \
  path/to/statement.pdf \
  --account "Checking"

# Review low-confidence AI categorizations
python -m src.interfaces.cli.main review-transactions --threshold 0.7

# List transactions
python -m src.interfaces.cli.main list-transactions --limit 20

# View statistics (SQLite only)
python -m src.interfaces.cli.main stats
```

### Docker
```bash
# Build Docker image
make docker-build

# Test Docker image
make docker-test

# Run container interactively
make docker-run
```

## Architecture Guide

### Layer Structure
```
interfaces/       → CLI, API, UI (easily swappable)
application/      → Use Cases, Services, DTOs
domain/           → Entities, Repository Interfaces (core business logic)
infrastructure/   → Repository Implementations, Parsers, External APIs
```

### Dependency Flow
- **Interfaces** depend on **Application**
- **Application** depends on **Domain**
- **Infrastructure** implements **Domain** interfaces
- **Domain** has NO dependencies (pure business logic)

### Key Components

**Domain Layer** ([src/domain/](src/domain/)):
- `entities/transaction.py` - Transaction entity with reimbursement tracking
- `entities/category.py` - Category and subcategory entities
- `repositories/transaction_repository.py` - Abstract repository interface

**Application Layer** ([src/application/](src/application/)):
- `use_cases/create_transaction.py` - Create single transaction
- `use_cases/import_csv.py` - Import CSV bank statements
- `use_cases/import_pdf.py` - Import PDF statements with AI categorization
- `use_cases/update_reimbursement.py` - Track reimbursements (Tikkie/group expenses)
- `services/categorization_service.py` - AI categorization orchestration

**Infrastructure Layer** ([src/infrastructure/](src/infrastructure/)):
- `repositories/notion_repository.py` - Notion API adapter (26K LOC)
- `repositories/sqlite_repository.py` - SQLite adapter (20K LOC)
- `parsers/csv_parser.py` - Multi-bank CSV parser
- `parsers/pdf_parser.py` - PDF bank statement extraction
- `ai/ollama_client.py` - Local LLM integration (Ollama)
- `ai/prompt_builder.py` - Categorization prompt generation
- `ai/response_parser.py` - LLM response parsing

**Dependency Injection** ([src/container.py](src/container.py)):
- Uses `dependency-injector` library
- Repository selection via `REPOSITORY_TYPE` environment variable
- Enables easy swapping: `notion` ↔ `sqlite`

## Configuration

**Environment Variables** (`.env` file):
```bash
REPOSITORY_TYPE=sqlite           # "notion" or "sqlite"
NOTION_TOKEN=secret_abc...       # For Notion mode
NOTION_DATABASE_ID=1a2b3c...     # For Notion mode
SQLITE_DB_PATH=data/transactions.db

# Ollama LLM (for AI categorization)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
OLLAMA_TIMEOUT=120
OLLAMA_BATCH_SIZE=35             # Optimized: 30-40 transactions per batch
AI_CONFIDENCE_THRESHOLD=0.7      # Below this → needs review

LOG_LEVEL=INFO
ENVIRONMENT=development
```

**Testing with Different Repositories**:
- SQLite: `REPOSITORY_TYPE=sqlite pytest`
- Notion: `REPOSITORY_TYPE=notion pytest -m "notion"`

## Important Development Notes

### When Adding New Features

1. **Start in Domain Layer**: Define entities and repository methods first
2. **Add Use Case**: Create application/use_cases/*.py
3. **Update Container**: Wire dependencies in [src/container.py](src/container.py)
4. **Implement Repository Methods**: Add to BOTH [notion_repository.py](src/infrastructure/repositories/notion_repository.py) and [sqlite_repository.py](src/infrastructure/repositories/sqlite_repository.py)
5. **Add CLI Command**: Update [src/interfaces/cli/main.py](src/interfaces/cli/main.py)

### Testing Strategy

- **Unit tests** mock dependencies (repository, external APIs)
- **Integration tests** use real SQLite database
- **Notion tests** marked with `@pytest.mark.notion` (optional)
- Test markers:
  - `@pytest.mark.notion` - Requires Notion credentials
  - `@pytest.mark.integration` - Integration tests
  - `@pytest.mark.slow` - Slow-running tests

### Repository Pattern

Both repositories implement `TransactionRepository` interface:
```python
class TransactionRepository(ABC):
    def create(self, transaction: Transaction) -> Transaction
    def get_by_id(self, transaction_id: UUID) -> Transaction | None
    def list(...) -> List[Transaction]
    def update(self, transaction_id: UUID, dto: UpdateTransactionDTO) -> Transaction
    # ... etc
```

**When adding repository methods**:
1. Add to abstract base ([src/domain/repositories/transaction_repository.py](src/domain/repositories/transaction_repository.py))
2. Implement in [NotionTransactionRepository](src/infrastructure/repositories/notion_repository.py)
3. Implement in [SQLiteTransactionRepository](src/infrastructure/repositories/sqlite_repository.py)
4. Write tests for both implementations

### AI Categorization Flow (Optimized for CPU Inference)

The system uses **optimized batch processing** to categorize 70-150 transactions in 2-6 minutes (instead of 30+ minutes with sequential processing):

1. **PDF Import** → `import_pdf.py` use case
2. **Extract Transactions** → `PDFParser.parse_pdf()`
3. **Optimized Batch Categorization** → `CategorizationService.categorize_batch_optimized()`
   - **Batch size: 30-40 transactions** (configurable via `OLLAMA_BATCH_SIZE`, default: 35)
   - **Single LLM call per batch** (category + subcategory together)
   - **Compact prompts**: No currency symbols, minimal tokens
   - **Optimized parameters**: `num_predict=60`, `num_ctx=1536`, `keep_alive=30m`
4. **Prompt Building** → `CategorizationPromptBuilder.build_optimized_batch_prompt()`
   - Uses transaction IDs for mapping results
   - Removes € symbols to reduce tokens
   - Compact JSON input/output format
5. **LLM Call** → `OllamaClient.generate(is_batch=True)`
   - Automatically sets optimized parameters for batch mode
   - Keeps model loaded with `keep_alive` to avoid reload overhead
6. **Parse Response** → `CategorizationResponseParser.parse_optimized_batch_response()`
   - Returns dict mapping transaction ID → CategorizationResult
   - Handles missing results with fallback
7. **Set Confidence** → Transactions with confidence < threshold marked for review

**Performance Improvements (on i5-8400 CPU with llama3.1:8b):**
- **Before**: ~47 seconds per transaction (sequential) = 55+ minutes for 70 transactions
- **After**: ~3-5 seconds per transaction (batched) = 2-6 minutes for 70-150 transactions
- **Speedup**: 10-20x faster
- **70 transactions**: 2-3 batches × ~1 minute = 2-3 minutes total
- **150 transactions**: 4-5 batches × ~1.2 minutes = 4-6 minutes total

**Key Optimizations:**
- Batch processing reduces prompt evaluation overhead (biggest win on CPU)
- `num_predict=60` instead of 200 (cuts generation time)
- No € symbols (fewer tokens to process)
- `keep_alive=30m` prevents model reload between batches
- Compact JSON reduces both input and output token count

### Notion Schema

See [docs/NOTION_SCHEMA.md](docs/NOTION_SCHEMA.md) for required Notion database properties:
- Description (Title)
- Date (Date)
- Amount (Number, $ format)
- Category (Select)
- Subcategory (Select)
- Account (Select)
- Tags (Multi-select)
- Reviewed (Checkbox)
- Transaction ID (Text, UUID)
- AI Confidence (Number, 0-100)
- Reimbursable (Checkbox)
- Reimbursement Status (Select: pending/partial/complete)

### Bank CSV Formats

Supported banks ([src/infrastructure/parsers/csv_parser.py](src/infrastructure/parsers/csv_parser.py)):
- ING Bank (Netherlands)
- Rabobank (Netherlands)
- ABN AMRO (Netherlands)
- Generic US format
- Generic UK format

Add new bank configs in `csv_parser.py` with column mappings.

### Reimbursement Tracking

Transactions can be marked as `reimbursable=True` for group expenses (Tikkie, Splitwise):
- `expected_reimbursement`: Amount you expect to receive back
- `actual_reimbursement`: Amount actually received
- `pending_reimbursement`: Calculated (expected - actual)
- `reimbursement_status`: pending/partial/complete (auto-calculated)

CLI commands:
- `--reimbursable` flag when adding transactions
- `pending-reimbursements` - List pending reimbursements
- `record-reimbursement <id> <amount>` - Record payment received

## Common Patterns

### Adding a New Use Case
```python
# 1. Define DTO in src/application/dtos/
@dataclass
class MyFeatureDTO:
    field: str

# 2. Create use case in src/application/use_cases/
class MyFeatureUseCase:
    def __init__(self, repository: TransactionRepository):
        self._repository = repository

    def execute(self, dto: MyFeatureDTO) -> Result:
        # Business logic here
        pass

# 3. Wire in src/container.py
my_feature_use_case = providers.Factory(
    MyFeatureUseCase,
    repository=transaction_repository,
)

# 4. Add CLI command in src/interfaces/cli/main.py
@cli.command()
def my_feature():
    use_case = container.my_feature_use_case()
    result = use_case.execute(dto)
```

### Running Single Test
```bash
# By file
pytest tests/test_domain/test_transaction.py -v

# By test name
pytest tests/ -k "test_create_transaction" -v

# By marker
pytest tests/ -m "not notion" -v
```

## Files to Reference

- [README.md](README.md) - Full project documentation
- [docs/NOTION_SCHEMA.md](docs/NOTION_SCHEMA.md) - Notion database setup
- [docs/QUICK_START.md](docs/QUICK_START.md) - Quick start guide
- [Makefile](Makefile) - All available make commands
- [pyproject.toml](pyproject.toml) - Dependencies and tool configuration
- [.env.example](.env.example) - Environment variable template

## Technology Stack

- **Python**: 3.12-3.13 (3.14+ not yet supported by dependencies)
- **CLI**: Click
- **DI**: dependency-injector
- **Database**: SQLAlchemy (for SQLite), notion-client (for Notion)
- **AI/LLM**: Ollama (local LLM inference)
- **Parsing**: pandas, pdfplumber, tabula-py
- **Testing**: pytest, pytest-cov
- **Linting**: black, ruff, mypy
- **Settings**: pydantic-settings
