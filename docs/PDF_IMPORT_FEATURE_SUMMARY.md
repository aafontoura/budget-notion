# PDF Import & AI Categorization - Feature Summary

## Overview

This document summarizes the automated PDF bank statement processing system with AI-powered categorization using a local Ollama LLM.

## Features Implemented

### 1. PDF Extraction
- **Component:** [PDFParser](../src/infrastructure/parsers/pdf_parser.py)
- **Capabilities:**
  - Table extraction from PDF statements
  - Text parsing fallback for non-table PDFs
  - Multi-format date normalization (YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY, etc.)
  - Multi-currency amount parsing (€, $, R$)
  - European (1.234,56) and US (1,234.56) number formats
  - Parentheses negatives handling: `($50.00)` → `-50.00`
- **Supported Banks:** ABN AMRO, Trade Republic, Nubank, Generic formats

### 2. AI Categorization
- **Components:**
  - [OllamaClient](../src/infrastructure/ai/ollama_client.py) - Connection to local LLM
  - [PromptBuilder](../src/infrastructure/ai/prompt_builder.py) - Optimized prompts
  - [ResponseParser](../src/infrastructure/ai/response_parser.py) - Response validation
  - [CategorizationService](../src/application/services/categorization_service.py) - Orchestration

- **Strategy:** Two-step categorization for efficiency
  1. **Step 1:** Determine main category (12 options)
  2. **Step 2:** Determine subcategory (5-15 options per category)

- **Optimizations for 8B Model:**
  - Minimal token usage
  - Batch processing (5 transactions at once)
  - Deterministic settings (temperature=0.1)
  - Small context window (2048 tokens)
  - CPU-optimized (6 threads for i5-8400)

- **Confidence Scoring:**
  - All AI categorizations include confidence score (0.0-1.0)
  - Default threshold: 0.7
  - Transactions below threshold flagged for review

### 3. Import Workflow
- **Component:** [ImportPDFUseCase](../src/application/use_cases/import_pdf.py)
- **Workflow:**
  1. Extract transactions from PDF
  2. Categorize using AI (optional)
  3. Validate data (dates, amounts)
  4. Save to repository
  5. Return statistics (imported, failed, needs review)

- **Error Handling:**
  - Graceful fallback to "Miscellaneous" if AI fails
  - Continue import even if some transactions fail
  - Detailed error logging

### 4. CLI Commands

#### `import-pdf`
Import transactions from PDF bank statement.

```bash
budget-notion import-pdf <file.pdf> [OPTIONS]

Options:
  --account, -a TEXT           Account name
  --no-ai                      Disable AI categorization
  --confidence-threshold, -t   Threshold for review (default: 0.7)
```

**Example:**
```bash
python -m src.interfaces.cli.main import-pdf \
  ~/Downloads/statement_jan2025.pdf \
  --account "ABN AMRO Checking"
```

**Output:**
```
✓ Connected to Ollama
Extracting transactions from PDF...
Processing  [####################################]  100%

✓ Import complete!
  Total parsed: 45
  Successful imports: 44
  Failed imports: 1

⚠ 8 transactions need review (low confidence)
  Run 'budget-notion review-transactions' to review them

Sample transactions:
  • 2025-01-19 | Albert Heijn                      | €-50.00 | FOOD & GROCERIES/Groceries [95%]
  • 2025-01-18 | Shell Gas Station                 | €-60.00 | TRANSPORTATION/Car Fuel [88%]
  ...
```

#### `review-transactions`
Interactive review of low-confidence transactions.

```bash
budget-notion review-transactions [OPTIONS]

Options:
  --threshold, -t FLOAT  Show transactions below this confidence (default: 0.7)
  --limit, -l INTEGER    Maximum transactions to review (default: 50)
  --account, -a TEXT     Filter by account
```

**Example:**
```bash
python -m src.interfaces.cli.main review-transactions --threshold 0.8
```

**Interaction:**
```
Found 8 transactions that need review:

Transaction 1/8
  ID: txn-abc123
  Date: 2025-01-14
  Description: Bol.com Online Purchase
  Amount: €-29.99
  AI Category: PERSONAL & LIFESTYLE/Hobbies (confidence: 65%)

Action [accept/edit/skip/quit] (accept): accept
✓ Accepted and marked as reviewed
```

### 5. Configuration

All settings configurable via environment variables or `.env` file:

```bash
# Ollama Configuration
OLLAMA_BASE_URL=http://supermicro:11434
OLLAMA_MODEL=llama3.1:8b
OLLAMA_TIMEOUT=60
OLLAMA_BATCH_SIZE=5

# AI Settings
AI_CONFIDENCE_THRESHOLD=0.7

# Repository
REPOSITORY_TYPE=sqlite
SQLITE_DB_PATH=data/transactions.db
```

See [config/settings.py](../config/settings.py:37-42) for all options.

## Architecture

### Clean Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│ Interface Layer (CLI)                                   │
│ - import_pdf command                                     │
│ - review_transactions command                            │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ Application Layer (Use Cases)                           │
│ - ImportPDFUseCase: Orchestrate full workflow           │
│ - CategorizationService: AI orchestration               │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ Infrastructure Layer (External Systems)                 │
│ - PDFParser: Extract from PDF                           │
│ - OllamaClient: Connect to LLM                          │
│ - PromptBuilder: Generate prompts                       │
│ - ResponseParser: Parse & validate                      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ Domain Layer (Business Logic)                           │
│ - Transaction entity (with ai_confidence, reviewed)     │
│ - Category structure (12 categories + subcategories)    │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

```
PDF File
  ↓
PDFParser (pdfplumber)
  ↓
Raw Transactions [{date, description, amount}, ...]
  ↓
CategorizationService
  ↓ (batch of 5)
OllamaClient → Prompt → LLM → Response → Parser
  ↓
Categorized Transactions (with confidence)
  ↓
ImportPDFUseCase
  ↓
Transaction Repository (SQLite/Notion)
  ↓
Database
```

## Testing

### Test Coverage

| Component | Unit Tests | Integration Tests |
|-----------|-----------|-------------------|
| PDFParser | ✅ 20 tests | ✅ 3 real PDFs |
| OllamaClient | ✅ 15 tests | ✅ Mock & real |
| PromptBuilder | ✅ 12 tests | N/A |
| ResponseParser | ✅ 25 tests | N/A |
| CategorizationService | ✅ 10 tests | ✅ End-to-end |
| ImportPDFUseCase | ✅ 12 tests | ✅ Full workflow |
| **Total** | **94 unit tests** | **Multiple integration tests** |

### Sample PDFs

Three sample PDFs generated for testing:
1. **simple_statement.pdf** - Basic format
2. **abn_amro_statement.pdf** - Dutch format
3. **mixed_format_statement.pdf** - Multiple formats

```bash
# Generate samples
python3 tests/fixtures/generate_sample_pdfs.py

# Run tests
pytest tests/ -v
```

### Documentation

- **Unit Tests:** [tests/README.md](../tests/README.md)
- **Manual Testing:** [docs/MANUAL_TESTING_PDF_IMPORT.md](../docs/MANUAL_TESTING_PDF_IMPORT.md)

## Performance

Based on testing with i5-8400 CPU (supermicro):

| Operation | Time |
|-----------|------|
| PDF extraction (5 txns) | ~1-2 seconds |
| AI categorization (batch of 5) | ~5-8 seconds |
| Single transaction | ~3-4 seconds |
| **Full import (5 txns)** | **~10-15 seconds** |

**Scaling:**
- 50 transactions: ~1-2 minutes
- 100 transactions: ~3-4 minutes

## Future Enhancements

Potential improvements identified:

1. **Rule-based shortcuts:** Skip AI for obvious merchants (e.g., "Albert Heijn" → always groceries)
2. **Learning from corrections:** Track user corrections to improve prompts
3. **OCR support:** Handle scanned/image PDFs (currently only text-based)
4. **Faster models:** Try smaller models (e.g., Llama 3.2 3B) for speed
5. **GPU acceleration:** If GPU available, could be 3-5x faster
6. **Subcategory in UpdateDTO:** Allow editing subcategory in review workflow
7. **Batch review:** Review multiple transactions at once
8. **Export functionality:** Export categorized transactions to CSV/Excel

## Deployment

### Local Development

```bash
# 1. Setup Ollama on supermicro
ssh supermicro
ollama serve

# 2. Setup Python environment
source venv/bin/activate
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit OLLAMA_BASE_URL=http://supermicro:11434

# 4. Test
python -m src.interfaces.cli.main import-pdf tests/fixtures/pdfs/simple_statement.pdf
```

### Docker (Future)

```yaml
# docker-compose.yml (future)
services:
  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_models:/root/.ollama

  budget-notion:
    build: .
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
    depends_on:
      - ollama
```

## Dependencies Added

```txt
# PDF parsing
pdfplumber==0.11.0

# HTTP client for Ollama
httpx==0.27.0

# Already existing (used by new features)
tenacity==9.0.0  # Retry logic
```

## Files Created/Modified

### New Files (Total: 13)

**Infrastructure:**
1. `src/infrastructure/parsers/pdf_parser.py` (335 lines)
2. `src/infrastructure/ai/ollama_client.py` (167 lines)
3. `src/infrastructure/ai/prompt_builder.py` (155 lines)
4. `src/infrastructure/ai/response_parser.py` (327 lines)

**Application:**
5. `src/application/services/categorization_service.py` (220 lines)
6. `src/application/use_cases/import_pdf.py` (212 lines)

**Tests:**
7. `tests/test_infrastructure/test_parsers/test_pdf_parser.py` (220 lines)
8. `tests/test_infrastructure/test_ai/test_ollama_client.py` (200 lines)
9. `tests/test_infrastructure/test_ai/test_prompt_builder.py` (170 lines)
10. `tests/test_infrastructure/test_ai/test_response_parser.py` (280 lines)
11. `tests/test_application/test_categorization_service.py` (200 lines)
12. `tests/test_application/test_import_pdf_use_case.py` (250 lines)
13. `tests/test_integration/test_pdf_import_integration.py` (300 lines)

**Fixtures:**
14. `tests/fixtures/generate_sample_pdfs.py` (180 lines)
15. `tests/fixtures/pdfs/` (3 sample PDFs)

**Documentation:**
16. `docs/MANUAL_TESTING_PDF_IMPORT.md` (comprehensive guide)
17. `docs/PDF_IMPORT_FEATURE_SUMMARY.md` (this file)
18. `tests/README.md` (test suite documentation)

### Modified Files (Total: 5)

1. `requirements.txt` - Added pdfplumber, httpx
2. `config/settings.py` - Added Ollama configuration
3. `src/application/dtos/transaction_dto.py` - Added ImportPDFDTO
4. `src/application/dtos/__init__.py` - Export ImportPDFDTO
5. `src/container.py` - Wire up new providers
6. `src/interfaces/cli/main.py` - Added import-pdf and review-transactions commands

**Total Lines Added:** ~3,500 lines (code + tests + docs)

## Quick Reference

### Import PDF with AI
```bash
python -m src.interfaces.cli.main import-pdf statement.pdf --account "My Account"
```

### Import Without AI
```bash
python -m src.interfaces.cli.main import-pdf statement.pdf --no-ai
```

### Review Transactions
```bash
python -m src.interfaces.cli.main review-transactions
```

### Run Tests
```bash
pytest tests/ -v --cov=src
```

### Generate Sample PDFs
```bash
python3 tests/fixtures/generate_sample_pdfs.py
```

## Support

For issues or questions:
- Review [MANUAL_TESTING_PDF_IMPORT.md](MANUAL_TESTING_PDF_IMPORT.md) for detailed procedures
- Check test output with `LOG_LEVEL=DEBUG`
- Verify Ollama connection: `curl http://supermicro:11434/api/tags`
- Run unit tests to verify installation: `pytest tests/test_infrastructure/ -v`

## Credits

- **LLM:** Llama 3.1 8B (via Ollama)
- **PDF Library:** pdfplumber
- **HTTP Client:** httpx
- **Testing:** pytest, pytest-cov
- **Architecture:** Clean Architecture pattern

---

**Status:** ✅ Fully implemented and tested
**Version:** 1.0.0
**Date:** January 2025
