"""Test the full import workflow with AI categorization."""

import logging
from pathlib import Path

from src.infrastructure.parsers.pdf_parser import PDFParser
from src.infrastructure.ai.ollama_client import OllamaClient
from src.infrastructure.ai.prompt_builder import CategorizationPromptBuilder
from src.infrastructure.ai.response_parser import CategorizationResponseParser
from src.application.services.categorization_service import CategorizationService

# Enable info logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

# Create parser
parser = PDFParser()

# Parse PDF
pdf_path = Path("tests/fixtures/pdfs/Account statement Trade Republic 12:25.pdf")

print(f"\n{'='*80}")
print(f"Testing full import workflow")
print(f"{'='*80}\n")

try:
    # Step 1: Extract transactions
    print("Step 1: Extracting transactions from PDF...")
    transactions = parser.extract_transactions(pdf_path)
    print(f"✓ Extracted {len(transactions)} transactions\n")

    if not transactions:
        print("✗ No transactions extracted!")
        exit(1)

    # Step 2: Categorize with AI (first 5 only for quick test)
    print("Step 2: Categorizing first 5 transactions with AI...")

    # Initialize AI components
    ollama_client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout=120
    )

    # Test connection
    if not ollama_client.test_connection():
        print("✗ Cannot connect to Ollama. Skipping AI categorization.")
        exit(1)

    prompt_builder = CategorizationPromptBuilder()
    response_parser = CategorizationResponseParser()
    categorization_service = CategorizationService(
        ollama_client=ollama_client,
        prompt_builder=prompt_builder,
        response_parser=response_parser,
        batch_size=5
    )

    # Prepare transactions for categorization (add IDs)
    test_txns = []
    for i, txn in enumerate(transactions[:5]):
        test_txns.append({
            "id": str(i),
            "description": txn["description"],
            "amount": txn["amount"],
            "date": txn["date"]
        })

    # Categorize in batch
    results = categorization_service.categorize_batch_optimized(test_txns)

    print(f"✓ Categorized {len(results)} transactions\n")

    # Display results
    print("Results:")
    print(f"{'Date':<12} | {'Description':<40} | {'Amount':>10} | {'Category':<20} | {'Subcategory':<20}")
    print("-" * 120)

    for i, txn in enumerate(transactions[:5]):
        txn_id = str(i)
        result = results.get(txn_id)
        if result:
            print(f"{txn['date']:<12} | {txn['description'][:40]:<40} | €{txn['amount']:>9} | {result.category:<20} | {result.subcategory:<20}")
        else:
            print(f"{txn['date']:<12} | {txn['description'][:40]:<40} | €{txn['amount']:>9} | {'N/A':<20} | {'N/A':<20}")

    print("\n✓ Full workflow test complete!")

except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
