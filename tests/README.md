# Test Suite - PDF Import & AI Categorization

This directory contains comprehensive tests for the PDF import and AI categorization features.

## Test Structure

```
tests/
├── fixtures/
│   ├── pdfs/                          # Sample PDF bank statements
│   │   ├── simple_statement.pdf       # Basic statement with 5 transactions
│   │   ├── abn_amro_statement.pdf     # Dutch format (DD-MM-YYYY, €)
│   │   └── mixed_format_statement.pdf # Multiple date/currency formats
│   └── generate_sample_pdfs.py        # Script to generate sample PDFs
│
├── test_infrastructure/               # Infrastructure layer tests
│   ├── test_parsers/
│   │   └── test_pdf_parser.py        # PDF extraction tests
│   └── test_ai/
│       ├── test_ollama_client.py     # Ollama client tests
│       ├── test_prompt_builder.py    # Prompt generation tests
│       └── test_response_parser.py   # LLM response parsing tests
│
├── test_application/                  # Application layer tests
│   ├── test_categorization_service.py # Service orchestration tests
│   └── test_import_pdf_use_case.py   # Use case tests
│
└── test_integration/                  # End-to-end integration tests
    └── test_pdf_import_integration.py # Full workflow tests
```

## Running Tests

### Quick Start

```bash
# Run all unit tests
pytest tests/ -v -m "not real_ollama"

# With coverage
pytest tests/ -v --cov=src --cov-report=html
```

See [docs/MANUAL_TESTING_PDF_IMPORT.md](../docs/MANUAL_TESTING_PDF_IMPORT.md) for detailed manual testing procedures.
