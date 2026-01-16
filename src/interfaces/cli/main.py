"""CLI interface for budget-notion application."""

import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import click

from config.settings import settings
from src.application.dtos import CreateTransactionDTO, ImportCSVDTO
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
@click.option("--account", help="Account name (optional).")
@click.option("--notes", "-n", help="Additional notes (optional).")
def add(date: str, description: str, amount: float, category: str, account: str, notes: str):
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
            account=account,
            notes=notes,
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
@click.option("--limit", "-l", default=10, type=int, help="Number of transactions to display.")
@click.option("--category", "-c", help="Filter by category.")
@click.option("--account", "-a", help="Filter by account.")
def list_transactions(limit: int, category: str, account: str):
    """List recent transactions."""
    try:
        # Get repository
        repository = container.transaction_repository()

        # List transactions
        transactions = repository.list(
            category=category,
            account=account,
            limit=limit,
        )

        if not transactions:
            click.echo("No transactions found.")
            return

        # Display transactions
        click.echo(f"\nRecent Transactions ({len(transactions)}):")
        click.echo("-" * 100)

        for transaction in transactions:
            # Color code based on income/expense
            amount_color = "green" if transaction.is_income else "red"
            amount_str = click.style(f"${abs(transaction.amount):,.2f}", fg=amount_color)

            # Truncate description
            description = transaction.description[:45] + "..." if len(transaction.description) > 45 else transaction.description

            click.echo(
                f"{transaction.date.strftime('%Y-%m-%d')} | "
                f"{description:<48} | "
                f"{amount_str:>10} | "
                f"{transaction.category}"
            )

        click.echo("-" * 100)

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


if __name__ == "__main__":
    cli()
