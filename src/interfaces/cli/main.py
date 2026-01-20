"""CLI interface for budget-notion application."""

import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import click

from config.settings import settings
from src.application.dtos import (
    CreateTransactionDTO,
    ImportCAMT053DTO,
    ImportCSVDTO,
    ImportPDFDTO,
)
from src.container import Container, setup_logging


# Initialize container
container = Container()
container.wire(modules=[__name__])

# Setup logging
setup_logging(settings.log_level)


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """
    Budget Notion - Personal Finance Aggregator

    Manage your finances with AI-powered categorization and Notion integration.
    """
    # Ensure data directory exists
    settings.ensure_data_directory()


@cli.command()
@click.option("--date", "-d", help="Transaction date (YYYY-MM-DD). Defaults to today.")
@click.option("--description", "-desc", required=True, help="Transaction description.")
@click.option("--amount", "-a", required=True, type=float, help="Transaction amount.")
@click.option("--category", "-c", required=True, help="Transaction category.")
@click.option("--subcategory", "-s", help="Transaction subcategory (optional).")
@click.option("--account", help="Account name (optional).")
@click.option("--notes", "-n", help="Additional notes (optional).")
@click.option("--tags", "-t", multiple=True, help="Tags for this transaction (can be specified multiple times).")
@click.option("--reimbursable", "-r", is_flag=True, help="Mark as reimbursable (for group expenses/Tikkie).")
@click.option("--expected-reimbursement", "-e", type=float, help="Expected reimbursement amount.")
def add(
    date: str,
    description: str,
    amount: float,
    category: str,
    subcategory: str,
    account: str,
    notes: str,
    tags: tuple,
    reimbursable: bool,
    expected_reimbursement: float
):
    """Add a new transaction manually."""
    try:
        # Parse date
        if date:
            transaction_date = datetime.strptime(date, "%Y-%m-%d")
        else:
            transaction_date = datetime.now()

        # Create DTO
        dto = CreateTransactionDTO(
            date=transaction_date,
            description=description,
            amount=Decimal(str(amount)),
            category=category,
            subcategory=subcategory,
            account=account,
            notes=notes,
            tags=list(tags) if tags else [],
            reimbursable=reimbursable,
            expected_reimbursement=Decimal(str(expected_reimbursement)) if expected_reimbursement else Decimal("0"),
        )

        # Execute use case
        use_case = container.create_transaction_use_case()
        transaction = use_case.execute(dto)

        # Display result
        click.echo(click.style("✓ Transaction created successfully!", fg="green", bold=True))
        click.echo(f"  ID: {transaction.id}")
        click.echo(f"  Date: {transaction.date.strftime('%Y-%m-%d')}")
        click.echo(f"  Description: {transaction.description}")
        click.echo(f"  Amount: ${transaction.amount:,.2f}")
        click.echo(f"  Category: {transaction.category}")
        if transaction.account:
            click.echo(f"  Account: {transaction.account}")
        if transaction.tags:
            click.echo(f"  Tags: {', '.join(transaction.tags)}")
        if transaction.reimbursable:
            click.echo(f"  Reimbursable: Yes (Expected: ${transaction.expected_reimbursement:,.2f})")
            click.echo(f"  Status: {transaction.reimbursement_status.value}")

    except Exception as e:
        click.echo(click.style(f"✗ Error: {e}", fg="red", bold=True), err=True)
        sys.exit(1)


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--category", "-c", default="Uncategorized", help="Default category for transactions.")
@click.option("--account", "-a", help="Account name (optional).")
@click.option("--bank", "-b", help="Bank configuration (e.g., 'ing', 'rabobank', 'generic_us').")
def import_csv(file_path: str, category: str, account: str, bank: str):
    """Import transactions from a CSV file."""
    try:
        click.echo(f"Importing transactions from: {file_path}")

        # Create DTO
        dto = ImportCSVDTO(
            file_path=file_path,
            default_category=category,
            account_name=account,
            bank_config=bank,
        )

        # Execute use case
        use_case = container.import_csv_use_case()
        result = use_case.execute(dto)

        # Display results
        click.echo()
        click.echo(click.style("✓ Import complete!", fg="green", bold=True))
        click.echo(f"  Total parsed: {result['total_parsed']}")
        click.echo(f"  Successful imports: {result['successful_imports']}")
        click.echo(f"  Failed imports: {result['failed_imports']}")

        if result['successful_imports'] > 0:
            click.echo()
            click.echo("Sample transactions:")
            for transaction in result['transactions'][:5]:  # Show first 5
                click.echo(f"  • {transaction.date.strftime('%Y-%m-%d')} | "
                          f"{transaction.description[:40]} | "
                          f"${transaction.amount:,.2f} | "
                          f"{transaction.category}")

    except Exception as e:
        click.echo(click.style(f"✗ Error: {e}", fg="red", bold=True), err=True)
        sys.exit(1)


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--account", "-a", help="Account name (optional).")
@click.option("--no-ai", is_flag=True, help="Disable AI categorization (use default category).")
@click.option("--confidence-threshold", "-t", type=float, default=0.7, help="Confidence threshold for review (default: 0.7).")
def import_pdf(file_path: str, account: str, no_ai: bool, confidence_threshold: float):
    """Import transactions from a PDF bank statement with AI categorization."""
    try:
        click.echo(f"Importing transactions from PDF: {file_path}")

        if not no_ai:
            click.echo("Testing connection to Ollama LLM server...")
            # Test Ollama connection
            categorization_service = container.categorization_service()
            if not categorization_service.test_connection():
                click.echo(click.style("⚠ Warning: Cannot connect to Ollama server. Falling back to default categorization.", fg="yellow"))
                no_ai = True
            else:
                click.echo(click.style("✓ Connected to Ollama", fg="green"))

        # Create DTO
        dto = ImportPDFDTO(
            file_path=file_path,
            account_name=account,
            use_ai_categorization=not no_ai,
            confidence_threshold=confidence_threshold,
        )

        # Execute use case with progress indicator
        click.echo("\nExtracting transactions from PDF...")
        use_case = container.import_pdf_use_case()

        with click.progressbar(length=100, label="Processing") as bar:
            bar.update(30)  # PDF extraction
            result = use_case.execute(dto)
            bar.update(70)  # AI categorization + import

        # Display results
        click.echo()
        click.echo(click.style("✓ Import complete!", fg="green", bold=True))
        click.echo(f"  Total parsed: {result['total_parsed']}")
        click.echo(f"  Successful imports: {result['successful_imports']}")
        click.echo(f"  Failed imports: {result['failed_imports']}")

        if result['needs_review'] > 0:
            click.echo()
            click.echo(click.style(f"⚠ {result['needs_review']} transactions need review (low confidence)", fg="yellow", bold=True))
            click.echo(f"  Run 'budget-notion review-transactions' to review them")

        if result['successful_imports'] > 0:
            click.echo()
            click.echo("Sample transactions:")
            for transaction in result['transactions'][:5]:  # Show first 5
                confidence_indicator = ""
                if transaction.ai_confidence is not None:
                    confidence_color = "green" if transaction.ai_confidence >= confidence_threshold else "yellow"
                    confidence_indicator = click.style(f" [{transaction.ai_confidence:.0%}]", fg=confidence_color)

                click.echo(f"  • {transaction.date.strftime('%Y-%m-%d')} | "
                          f"{transaction.description[:35]:35} | "
                          f"€{transaction.amount:,.2f} | "
                          f"{transaction.category}/{transaction.subcategory or 'N/A'}"
                          f"{confidence_indicator}")

    except Exception as e:
        click.echo(click.style(f"✗ Error: {e}", fg="red", bold=True), err=True)
        import traceback
        if settings.log_level.upper() == "DEBUG":
            click.echo(traceback.format_exc(), err=True)
        sys.exit(1)


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--account", "-a", help="Account name (optional).")
@click.option("--no-ai", is_flag=True, help="Disable AI categorization (use default category).")
@click.option("--confidence-threshold", "-t", type=float, default=0.7, help="Confidence threshold for review (default: 0.7).")
@click.option("--allow-duplicates", is_flag=True, help="Import duplicate transactions (default: skip duplicates).")
def import_camt053(file_path: str, account: str, no_ai: bool, confidence_threshold: float, allow_duplicates: bool):
    """Import transactions from CAMT.053 XML, ZIP, or directory with AI categorization.

    Supports:
    - Single XML file: statement.xml
    - ZIP archive: statements.zip (processes all .xml files)
    - Directory: statements/ (processes all .xml files)

    Automatically skips duplicate transactions unless --allow-duplicates is specified.
    """
    try:
        path = Path(file_path)

        # Detect file type for user message
        if path.is_dir():
            click.echo(f"Importing from directory: {file_path}")
        elif path.suffix.lower() == '.zip':
            click.echo(f"Importing from ZIP archive: {file_path}")
        else:
            click.echo(f"Importing from XML file: {file_path}")

        if not no_ai:
            click.echo("Testing connection to Ollama LLM server...")
            categorization_service = container.categorization_service()
            if not categorization_service.test_connection():
                click.echo(click.style("⚠ Warning: Cannot connect to Ollama server. Falling back to default categorization.", fg="yellow"))
                no_ai = True
            else:
                click.echo(click.style("✓ Connected to Ollama", fg="green"))

        # Create DTO
        dto = ImportCAMT053DTO(
            file_path=file_path,
            account_name=account,
            use_ai_categorization=not no_ai,
            confidence_threshold=confidence_threshold,
            allow_duplicates=allow_duplicates,
        )

        # Execute use case with progress indicator
        click.echo("\nExtracting and importing transactions...")
        use_case = container.import_camt053_use_case()

        with click.progressbar(length=100, label="Processing") as bar:
            bar.update(30)  # Extraction
            result = use_case.execute(dto)
            bar.update(70)  # AI categorization + import

        # Display results
        click.echo()
        click.echo(click.style("✓ Import complete!", fg="green", bold=True))
        click.echo(f"  Files processed: {result['total_files']}")
        click.echo(f"  Total extracted: {result['total_parsed']}")
        if result['duplicates_skipped'] > 0:
            click.echo(click.style(f"  Duplicates skipped: {result['duplicates_skipped']}", fg="yellow"))
        click.echo(f"  Successful imports: {result['successful_imports']}")
        click.echo(f"  Failed imports: {result['failed_imports']}")

        if result['needs_review'] > 0:
            click.echo()
            click.echo(click.style(f"⚠ {result['needs_review']} transactions need review (low confidence)", fg="yellow", bold=True))
            click.echo(f"  Run 'budget-notion review-transactions' to review them")

        if result['successful_imports'] > 0:
            click.echo()
            click.echo("Sample transactions:")
            for transaction in result['transactions'][:5]:  # Show first 5
                confidence_indicator = ""
                if transaction.ai_confidence is not None:
                    confidence_color = "green" if transaction.ai_confidence >= confidence_threshold else "yellow"
                    confidence_indicator = click.style(f" [{transaction.ai_confidence:.0%}]", fg=confidence_color)

                click.echo(f"  • {transaction.date.strftime('%Y-%m-%d')} | "
                          f"{transaction.description[:35]:35} | "
                          f"€{transaction.amount:,.2f} | "
                          f"{transaction.category}/{transaction.subcategory or 'N/A'}"
                          f"{confidence_indicator}")

    except Exception as e:
        click.echo(click.style(f"✗ Error: {e}", fg="red", bold=True), err=True)
        import traceback
        if settings.log_level.upper() == "DEBUG":
            click.echo(traceback.format_exc(), err=True)
        sys.exit(1)


@cli.command()
@click.option("--limit", "-l", default=10, type=int, help="Number of transactions to display.")
@click.option("--category", "-c", help="Filter by category.")
@click.option("--account", "-a", help="Filter by account.")
@click.option("--tag", "-t", multiple=True, help="Filter by tag (can specify multiple).")
@click.option("--reimbursable", "-r", is_flag=True, help="Show only reimbursable transactions.")
def list_transactions(limit: int, category: str, account: str, tag: tuple, reimbursable: bool):
    """List recent transactions."""
    try:
        from src.domain.entities.transaction import ReimbursementStatus

        # Get repository
        repository = container.transaction_repository()

        # Determine reimbursement status filter
        reimbursable_status = None
        if reimbursable:
            reimbursable_status = ReimbursementStatus.PENDING

        # List transactions
        transactions = repository.list(
            category=category,
            account=account,
            tags=list(tag) if tag else None,
            reimbursable_status=reimbursable_status,
            limit=limit,
        )

        if not transactions:
            click.echo("No transactions found.")
            return

        # Display transactions
        click.echo(f"\nRecent Transactions ({len(transactions)}):")
        click.echo("-" * 120)

        for transaction in transactions:
            # Color code based on income/expense
            amount_color = "green" if transaction.is_income else "red"
            amount_str = click.style(f"${abs(transaction.amount):,.2f}", fg=amount_color)

            # Truncate description
            description = transaction.description[:35] + "..." if len(transaction.description) > 35 else transaction.description

            # Format tags
            tags_str = f"[{', '.join(transaction.tags[:3])}]" if transaction.tags else ""

            # Reimbursement indicator
            reimb_indicator = ""
            if transaction.reimbursable:
                reimb_indicator = f" 💸 {transaction.reimbursement_status.value}"

            click.echo(
                f"{transaction.date.strftime('%Y-%m-%d')} | "
                f"{description:<38} | "
                f"{amount_str:>12} | "
                f"{transaction.category[:20]:<20} | "
                f"{tags_str:<20}{reimb_indicator}"
            )

        click.echo("-" * 120)

    except Exception as e:
        click.echo(click.style(f"✗ Error: {e}", fg="red", bold=True), err=True)
        sys.exit(1)


@cli.command()
@click.option("--category", "-c", help="Category to analyze (optional).")
def stats(category: str):
    """Show transaction statistics."""
    try:
        # Get repository
        repository = container.transaction_repository()

        # Get statistics (only available for SQLite)
        if hasattr(repository, "get_statistics"):
            stats = repository.get_statistics()

            click.echo("\nTransaction Statistics:")
            click.echo("-" * 50)
            click.echo(f"Total Transactions: {stats['total_transactions']}")
            click.echo(f"  Income: {stats['income_count']}")
            click.echo(f"  Expenses: {stats['expense_count']}")
            click.echo()
            click.echo(f"Total Income: ${stats['total_income']:,.2f}")
            click.echo(f"Total Expenses: ${abs(stats['total_expenses']):,.2f}")
            click.echo(f"Net Total: ${stats['net_total']:,.2f}")
            click.echo("-" * 50)
        else:
            click.echo("Statistics are only available when using SQLite repository.")
            click.echo("Set REPOSITORY_TYPE=sqlite in your .env file.")

    except Exception as e:
        click.echo(click.style(f"✗ Error: {e}", fg="red", bold=True), err=True)
        sys.exit(1)


@cli.command()
def config_info():
    """Display current configuration."""
    click.echo("\nCurrent Configuration:")
    click.echo("-" * 50)
    click.echo(f"Repository Type: {settings.repository_type}")
    click.echo(f"Environment: {settings.environment}")
    click.echo(f"Log Level: {settings.log_level}")
    click.echo(f"Default Category: {settings.default_category}")

    if settings.repository_type == "sqlite":
        click.echo(f"SQLite Database: {settings.sqlite_db_path}")
    elif settings.repository_type == "notion":
        click.echo(f"Notion Database ID: {settings.notion_database_id[:8]}...")

    click.echo("-" * 50)


@cli.command()
def pending_reimbursements():
    """List all pending reimbursements."""
    try:
        # Get repository
        repository = container.transaction_repository()

        # Get pending reimbursements
        transactions = repository.get_pending_reimbursements()

        if not transactions:
            click.echo("No pending reimbursements found.")
            return

        # Display transactions
        click.echo(f"\nPending Reimbursements ({len(transactions)}):")
        click.echo("-" * 100)

        total_pending = Decimal("0")

        for transaction in transactions:
            pending_amount = transaction.pending_reimbursement
            total_pending += pending_amount

            status_color = "yellow" if transaction.reimbursement_status.value == "partial" else "red"
            status = click.style(transaction.reimbursement_status.value.upper(), fg=status_color, bold=True)

            click.echo(
                f"{transaction.date.strftime('%Y-%m-%d')} | "
                f"{transaction.description[:40]:<40} | "
                f"Expected: ${transaction.expected_reimbursement:>8,.2f} | "
                f"Received: ${transaction.actual_reimbursement:>8,.2f} | "
                f"Pending: ${pending_amount:>8,.2f} | "
                f"{status}"
            )

        click.echo("-" * 100)
        click.echo(f"Total Pending: ${total_pending:,.2f}")

    except Exception as e:
        click.echo(click.style(f"✗ Error: {e}", fg="red", bold=True), err=True)
        sys.exit(1)


@cli.command()
@click.argument("transaction_id")
@click.argument("amount", type=float)
def record_reimbursement(transaction_id: str, amount: float):
    """Record a reimbursement payment for a transaction."""
    try:
        from uuid import UUID

        # Get use case
        use_case = container.update_reimbursement_use_case()

        # Execute
        transaction = use_case.execute(
            transaction_id=UUID(transaction_id),
            actual_reimbursement=Decimal(str(amount))
        )

        # Display result
        click.echo(click.style("✓ Reimbursement recorded successfully!", fg="green", bold=True))
        click.echo(f"  Transaction: {transaction.description}")
        click.echo(f"  Amount Received: ${transaction.actual_reimbursement:,.2f}")
        click.echo(f"  Expected: ${transaction.expected_reimbursement:,.2f}")
        click.echo(f"  Pending: ${transaction.pending_reimbursement:,.2f}")
        click.echo(f"  Status: {transaction.reimbursement_status.value}")

    except Exception as e:
        click.echo(click.style(f"✗ Error: {e}", fg="red", bold=True), err=True)
        sys.exit(1)


@cli.command()
@click.argument("tag")
@click.option("--start-date", help="Start date (YYYY-MM-DD).")
@click.option("--end-date", help="End date (YYYY-MM-DD).")
def tag_total(tag: str, start_date: str, end_date: str):
    """Calculate total spending for a specific tag."""
    try:
        # Parse dates
        start = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
        end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

        # Get repository
        repository = container.transaction_repository()

        # Get total
        total = repository.get_total_by_tag(tag, start, end)

        # Display result
        period = ""
        if start and end:
            period = f" ({start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')})"
        elif start:
            period = f" (from {start.strftime('%Y-%m-%d')})"
        elif end:
            period = f" (until {end.strftime('%Y-%m-%d')})"

        click.echo(f"\nTotal for tag '{tag}'{period}:")

        if total < 0:
            click.echo(click.style(f"${abs(total):,.2f} (expenses)", fg="red", bold=True))
        else:
            click.echo(click.style(f"${total:,.2f} (income)", fg="green", bold=True))

    except Exception as e:
        click.echo(click.style(f"✗ Error: {e}", fg="red", bold=True), err=True)
        sys.exit(1)


@cli.command()
@click.option("--threshold", "-t", type=float, default=0.7, help="Show transactions below this confidence (default: 0.7).")
@click.option("--limit", "-l", type=int, default=50, help="Maximum number of transactions to review (default: 50).")
@click.option("--account", "-a", help="Filter by account.")
def review_transactions(threshold: float, limit: int, account: str):
    """Review transactions that need manual verification (low AI confidence)."""
    try:
        from src.application.dtos import UpdateTransactionDTO

        # Get repository
        repository = container.transaction_repository()

        # Find transactions that need review
        click.echo(f"Finding transactions with confidence < {threshold:.0%}...")
        all_transactions = repository.list(account=account, limit=limit * 2)  # Get more to filter

        # Filter unreviewed transactions with low confidence
        needs_review = [
            txn for txn in all_transactions
            if txn.needs_review and (txn.ai_confidence is None or txn.ai_confidence < threshold)
        ][:limit]

        if not needs_review:
            click.echo(click.style("✓ No transactions need review!", fg="green", bold=True))
            return

        click.echo(f"\nFound {len(needs_review)} transactions that need review:\n")

        reviewed_count = 0
        for i, transaction in enumerate(needs_review, 1):
            # Display transaction details
            click.echo(click.style(f"Transaction {i}/{len(needs_review)}", fg="cyan", bold=True))
            click.echo(f"  ID: {transaction.id}")
            click.echo(f"  Date: {transaction.date.strftime('%Y-%m-%d')}")
            click.echo(f"  Description: {transaction.description}")
            click.echo(f"  Amount: €{transaction.amount:,.2f}")

            confidence_str = f"{transaction.ai_confidence:.0%}" if transaction.ai_confidence is not None else "N/A"
            confidence_color = "yellow" if transaction.ai_confidence and transaction.ai_confidence < threshold else "red"
            click.echo(f"  AI Category: {transaction.category}/{transaction.subcategory or 'N/A'} "
                      f"(confidence: {click.style(confidence_str, fg=confidence_color)})")

            if transaction.account:
                click.echo(f"  Account: {transaction.account}")

            click.echo()

            # Ask user for action
            action = click.prompt(
                "Action",
                type=click.Choice(["accept", "edit", "skip", "quit"], case_sensitive=False),
                default="accept",
                show_choices=True,
            )

            if action == "quit":
                click.echo(f"\nReviewed {reviewed_count} transactions before quitting.")
                break

            elif action == "skip":
                click.echo(click.style("Skipped", fg="yellow"))
                click.echo()
                continue

            elif action == "accept":
                # Mark as reviewed without changes
                update_dto = UpdateTransactionDTO(reviewed=True)
                repository.update(transaction.id, update_dto)
                reviewed_count += 1
                click.echo(click.style("✓ Accepted and marked as reviewed", fg="green"))
                click.echo()

            elif action == "edit":
                # Allow editing category/subcategory
                click.echo("\nEdit transaction (press Enter to keep current value):")

                new_category = click.prompt("Category", default=transaction.category)
                new_subcategory = click.prompt("Subcategory", default=transaction.subcategory or "")

                # Update transaction
                update_dto = UpdateTransactionDTO(
                    category=new_category if new_category != transaction.category else None,
                    reviewed=True,
                )

                # Note: We can't update subcategory through UpdateTransactionDTO
                # This is a limitation - would need to extend the DTO
                repository.update(transaction.id, update_dto)
                reviewed_count += 1

                click.echo(click.style("✓ Updated and marked as reviewed", fg="green"))
                click.echo()

        # Summary
        click.echo()
        click.echo(click.style(f"Review complete! Processed {reviewed_count} transactions.", fg="green", bold=True))

        remaining = len(needs_review) - reviewed_count
        if remaining > 0:
            click.echo(f"{remaining} transactions still need review.")

    except Exception as e:
        click.echo(click.style(f"✗ Error: {e}", fg="red", bold=True), err=True)
        import traceback
        if settings.log_level.upper() == "DEBUG":
            click.echo(traceback.format_exc(), err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
