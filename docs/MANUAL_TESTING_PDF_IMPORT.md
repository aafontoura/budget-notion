# Manual Testing Guide - PDF Import with AI Categorization

This guide provides step-by-step instructions for manually testing the PDF import and AI categorization features.

## Prerequisites

### 1. Ollama Server Setup

The AI categorization requires a running Ollama server with the `llama3.1:8b` model.

**On your supermicro machine:**

```bash
# Check if Ollama is running
curl http://supermicro:11434/api/tags

# If not installed, install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull the llama3.1:8b model
ollama pull llama3.1:8b

# Start Ollama (if not running)
ollama serve
```

**Verify from your local machine:**

```bash
# Test connection
curl http://supermicro:11434/api/tags

# Expected response: JSON with list of models including llama3.1:8b
```

### 2. Python Environment

```bash
# Activate virtual environment
source venv/bin/activate

# Ensure all dependencies are installed
pip install -r requirements.txt
```

## Test Scenarios

### Scenario 1: Basic PDF Import with AI Categorization

**Objective:** Import a simple PDF bank statement with AI categorization.

**Steps:**

1. **Prepare test data:**
   ```bash
   # Generate sample PDFs (if not already done)
   python3 tests/fixtures/generate_sample_pdfs.py
   ```

2. **Test Ollama connection:**
   ```bash
   # Using Python
   python3 << 'EOF'
   from src.infrastructure.ai.ollama_client import OllamaClient

   client = OllamaClient(base_url="http://supermicro:11434")

   if client.test_connection():
       print("✓ Connected to Ollama")
       models = client.list_models()
       print(f"✓ Available models: {models}")
   else:
       print("✗ Cannot connect to Ollama")
   EOF
   ```

3. **Import PDF with AI categorization:**
   ```bash
   # Set repository type (SQLite for local testing)
   export REPOSITORY_TYPE=sqlite
   export SQLITE_DB_PATH=data/test_transactions.db

   # Import simple statement
   python -m src.interfaces.cli.main import-pdf \
     tests/fixtures/pdfs/simple_statement.pdf \
     --account "Test Account"
   ```

**Expected Output:**
```
Importing transactions from PDF: tests/fixtures/pdfs/simple_statement.pdf
Testing connection to Ollama LLM server...
✓ Connected to Ollama

Extracting transactions from PDF...
Processing  [####################################]  100%

✓ Import complete!
  Total parsed: 5
  Successful imports: 5
  Failed imports: 0

Sample transactions:
  • 2025-01-19 | Albert Heijn Supermarket           | €-50.00 | FOOD & GROCERIES/Groceries [95%]
  • 2025-01-18 | Shell Gas Station                  | €-60.00 | TRANSPORTATION/Car Fuel [88%]
  • 2025-01-17 | Restaurant De Eethoek              | €-35.50 | FOOD & GROCERIES/Takeout & Delivery [92%]
  • 2025-01-16 | Salary Deposit                     | €2500.00 | Income/Salary [98%]
  • 2025-01-15 | ABN AMRO Car Insurance             | €-52.15 | INSURANCE/Car Insurance [95%]
```

**Verification:**
```bash
# Check imported transactions
python -m src.interfaces.cli.main list-transactions --limit 10

# Verify database
sqlite3 data/test_transactions.db "SELECT description, category, subcategory, ai_confidence FROM transactions ORDER BY date DESC LIMIT 5;"
```

---

### Scenario 2: PDF Import Without AI (Fallback Mode)

**Objective:** Test import with AI disabled or unavailable.

**Steps:**

1. **Import without AI categorization:**
   ```bash
   python -m src.interfaces.cli.main import-pdf \
     tests/fixtures/pdfs/simple_statement.pdf \
     --account "Test Account" \
     --no-ai
   ```

**Expected Output:**
```
Importing transactions from PDF: tests/fixtures/pdfs/simple_statement.pdf

Extracting transactions from PDF...
Processing  [####################################]  100%

✓ Import complete!
  Total parsed: 5
  Successful imports: 5
  Failed imports: 0

Sample transactions:
  • 2025-01-19 | Albert Heijn Supermarket           | €-50.00 | Miscellaneous/Uncategorized
  • 2025-01-18 | Shell Gas Station                  | €-60.00 | Miscellaneous/Uncategorized
  ...
```

**Verification:**
- All transactions should have `Miscellaneous/Uncategorized` category
- `ai_confidence` should be `0.0`

---

### Scenario 3: Review Low-Confidence Transactions

**Objective:** Test the review workflow for transactions with low AI confidence.

**Steps:**

1. **Import transactions** (some will have low confidence):
   ```bash
   python -m src.interfaces.cli.main import-pdf \
     tests/fixtures/pdfs/abn_amro_statement.pdf \
     --account "ABN AMRO" \
     --confidence-threshold 0.8
   ```

2. **Review transactions that need verification:**
   ```bash
   python -m src.interfaces.cli.main review-transactions \
     --threshold 0.8 \
     --limit 10
   ```

**Expected Interaction:**
```
Finding transactions with confidence < 80%...

Found 3 transactions that need review:

Transaction 1/3
  ID: txn-abc123
  Date: 2025-01-14
  Description: Bol.com Aankoop
  Amount: €-29.99
  AI Category: PERSONAL & LIFESTYLE/Hobbies & Entertainment (confidence: 65%)
  Account: ABN AMRO

Action [accept/edit/skip/quit] (accept): accept
✓ Accepted and marked as reviewed

Transaction 2/3
  ID: txn-abc124
  Date: 2025-01-13
  Description: IKEA Meubels
  Amount: €-250.00
  AI Category: HOME/Furniture (confidence: 75%)
  Account: ABN AMRO

Action [accept/edit/skip/quit] (accept): edit

Edit transaction (press Enter to keep current value):
Category [HOME]: HOME
Subcategory [Furniture]: Furniture
✓ Updated and marked as reviewed

...

Review complete! Processed 3 transactions.
```

---

### Scenario 4: Dutch Bank Statement (ABN AMRO Format)

**Objective:** Test parsing of Dutch-formatted statements.

**Steps:**

1. **Import Dutch statement:**
   ```bash
   python -m src.interfaces.cli.main import-pdf \
     tests/fixtures/pdfs/abn_amro_statement.pdf \
     --account "ABN AMRO NL01"
   ```

**Expected Output:**
- Dates in `DD-MM-YYYY` format should be correctly parsed
- Amounts in European format (€ 1.234,56) should be correctly parsed
- Dutch descriptions should be categorized appropriately

**Verification:**
```bash
# Check specific transactions
python -m src.interfaces.cli.main list-transactions \
  --account "ABN AMRO NL01" \
  --limit 10
```

---

### Scenario 5: Mixed Format Statement

**Objective:** Test handling of various date and currency formats.

**Steps:**

1. **Import mixed format statement:**
   ```bash
   python -m src.interfaces.cli.main import-pdf \
     tests/fixtures/pdfs/mixed_format_statement.pdf \
     --account "International"
   ```

**Expected Output:**
- All date formats (YYYY-MM-DD, DD/MM/YYYY, DD Mon YYYY) should be normalized
- All currency formats ($, €, R$) should be parsed correctly
- Parentheses-style negatives should be handled: `($35.50)` → `-35.50`

---

### Scenario 6: Real Bank Statement

**Objective:** Test with your actual bank statement.

**Preparation:**
1. Export a PDF statement from your bank (ABN AMRO, Trade Republic, or Nubank)
2. Place it in a safe location (e.g., `~/Documents/statements/`)

**Steps:**

1. **Import your statement:**
   ```bash
   python -m src.interfaces.cli.main import-pdf \
     ~/Documents/statements/my_statement_jan2025.pdf \
     --account "My Checking Account"
   ```

2. **Review the results:**
   ```bash
   # List imported transactions
   python -m src.interfaces.cli.main list-transactions --limit 20

   # Review low-confidence transactions
   python -m src.interfaces.cli.main review-transactions
   ```

3. **Check accuracy:**
   - Compare AI categorization with manual expectations
   - Note any misclassifications
   - Track confidence scores

**Expected Performance:**
- **Extraction time:** < 10 seconds for typical monthly statement
- **AI categorization:** ~2-3 seconds per transaction (batch of 5)
- **Overall accuracy:** > 80% for common transactions

---

## Troubleshooting

### Issue: Cannot Connect to Ollama

**Error Message:**
```
⚠ Warning: Cannot connect to Ollama server. Falling back to default categorization.
```

**Solutions:**

1. **Check Ollama is running on supermicro:**
   ```bash
   ssh supermicro
   ps aux | grep ollama
   # If not running:
   ollama serve
   ```

2. **Check network connectivity:**
   ```bash
   ping supermicro
   curl http://supermicro:11434/api/tags
   ```

3. **Check firewall:**
   ```bash
   # On supermicro
   sudo ufw status
   sudo ufw allow 11434/tcp
   ```

4. **Update settings (if using different host):**
   ```bash
   export OLLAMA_BASE_URL="http://your-host:11434"
   ```

---

### Issue: PDF Parsing Fails

**Error Message:**
```
✗ Error: Failed to parse PDF: ...
```

**Solutions:**

1. **Check PDF is readable:**
   ```bash
   # Try opening with pdfplumber directly
   python3 << 'EOF'
   import pdfplumber
   with pdfplumber.open("path/to/statement.pdf") as pdf:
       print(f"Pages: {len(pdf.pages)}")
       print(pdf.pages[0].extract_text()[:500])
   EOF
   ```

2. **Check PDF is not encrypted:**
   - Some banks encrypt PDFs with passwords
   - You may need to decrypt first

3. **Check PDF has extractable text:**
   - PDFs that are scanned images cannot be parsed
   - You would need OCR (not currently supported)

---

### Issue: Low AI Accuracy

**Symptoms:**
- Many transactions categorized as "Miscellaneous"
- Low confidence scores (< 0.5)
- Wrong categories

**Solutions:**

1. **Check model is loaded:**
   ```bash
   ssh supermicro
   ollama list
   # Should show llama3.1:8b
   ```

2. **Test model manually:**
   ```bash
   ollama run llama3.1:8b
   # Try: Categorize this transaction: "Albert Heijn grocery shopping" amount: -50 EUR
   ```

3. **Adjust confidence threshold:**
   ```bash
   # Lower threshold for less strict review requirement
   export AI_CONFIDENCE_THRESHOLD=0.6
   ```

4. **Check category structure:**
   - Ensure `src/domain/data/categories.py` has comprehensive categories
   - Add more subcategories if needed

---

## Performance Benchmarks

Based on testing with sample PDFs on i5-8400 CPU (supermicro):

| Metric | Value |
|--------|-------|
| PDF extraction (5 transactions) | ~1-2 seconds |
| AI categorization (batch of 5) | ~5-8 seconds |
| Single transaction categorization | ~3-4 seconds |
| Total import time (5 transactions) | ~10-15 seconds |

**Notes:**
- First request may be slower (model loading)
- Batch processing is 2-3x faster than individual
- CPU-only mode (no GPU acceleration)

---

## Running Automated Tests

### Unit Tests

Run all unit tests:
```bash
# Run all tests
REPOSITORY_TYPE=sqlite pytest tests/test_infrastructure/ tests/test_application/

# Run specific test file
pytest tests/test_infrastructure/test_parsers/test_pdf_parser.py -v

# Run with coverage
pytest --cov=src tests/test_infrastructure/ tests/test_application/
```

### Integration Tests

Run integration tests (with sample PDFs):
```bash
# Run integration tests
pytest tests/test_integration/test_pdf_import_integration.py -v

# Skip tests that require real Ollama
pytest tests/test_integration/ -v -m "not real_ollama"
```

### Test with Real Ollama Server

```bash
# Run tests that use real Ollama (manual)
pytest tests/test_integration/test_pdf_import_integration.py::TestPDFImportIntegration::test_full_workflow_with_real_ollama -v -m real_ollama
```

---

## Configuration Reference

### Environment Variables

```bash
# Repository
export REPOSITORY_TYPE=sqlite  # or "notion"
export SQLITE_DB_PATH=data/transactions.db

# Ollama Configuration
export OLLAMA_BASE_URL=http://supermicro:11434
export OLLAMA_MODEL=llama3.1:8b
export OLLAMA_TIMEOUT=60
export OLLAMA_BATCH_SIZE=5

# AI Settings
export AI_CONFIDENCE_THRESHOLD=0.7

# Logging
export LOG_LEVEL=INFO  # or DEBUG for verbose output
```

### Configuration Files

Settings can also be configured in `.env` file:

```bash
# .env file
REPOSITORY_TYPE=sqlite
SQLITE_DB_PATH=data/transactions.db
OLLAMA_BASE_URL=http://supermicro:11434
OLLAMA_MODEL=llama3.1:8b
AI_CONFIDENCE_THRESHOLD=0.7
```

---

## Next Steps After Testing

1. **If tests pass:**
   - Start using with real bank statements
   - Monitor accuracy over time
   - Adjust confidence threshold based on experience

2. **If issues found:**
   - Document specific issues in GitHub issues
   - Check logs with `LOG_LEVEL=DEBUG`
   - Try different Ollama models if needed

3. **Improvements to consider:**
   - Add rule-based shortcuts for common merchants
   - Fine-tune prompts for better accuracy
   - Add support for OCR (scanned PDFs)
   - Implement learning from user corrections

---

## Support

For issues or questions:
- Check logs: `tail -f logs/budget-notion.log` (if configured)
- Enable debug mode: `export LOG_LEVEL=DEBUG`
- Review error messages carefully
- Test with sample PDFs first before real statements

Happy testing! 🚀
