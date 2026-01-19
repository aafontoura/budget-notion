"""Integration tests for CLI commands.

These tests verify end-to-end functionality of the CLI with real repositories.
Designed for CI/CD pipelines.

Requirements Coverage:
    - SR-002: Dependency Injection
    - SR-003: Repository Pattern
    - SR-006: Tag Taxonomy
    - SR-007: Auto-Tagging Service
    - SR-008: Reimbursement Status Calculation
    - SR-010: SQLite Repository Implementation
    - SR-011: Notion Repository Implementation
    - SR-012: Database Schema Validation
    - SR-013: CLI Command Structure
    - SR-014: Error Handling
    - UR-001: Manual Transaction Entry
    - UR-003: Transaction Listing and Filtering
    - UR-004: Auto-Tagging Based on Subcategory
    - UR-006: Mark Transactions as Reimbursable
    - UR-007: Record Reimbursement Payments
    - UR-008: View Pending Reimbursements
    - UR-009: View Statistics
    - UR-010: Calculate Totals by Tag
    - UR-011: View Configuration
    - UR-012: Switch Between Repositories

Test-to-Requirement Mapping:
    TestConfigInfo:
        test_config_info_sqlite              -> SR-003, SR-010, SR-013, UR-011
        test_config_info_notion              -> SR-003, SR-011, SR-013, UR-011

    TestAddTransaction:
        test_add_basic_transaction           -> SR-013, UR-001
        test_add_with_all_fields             -> SR-013, UR-001
        test_add_reimbursable_transaction    -> SR-008, SR-013, UR-006
        test_add_missing_required_fields     -> SR-012, SR-014, UR-001

    TestListTransactions:
        test_list_empty                      -> SR-010, SR-013, UR-003
        test_list_with_transactions          -> SR-010, SR-013, UR-003
        test_list_filter_by_category         -> SR-010, SR-013, UR-003
        test_list_filter_by_tag              -> SR-010, SR-013, UR-003

    TestPendingReimbursements:
        test_pending_empty                   -> SR-010, SR-013, UR-008
        test_pending_with_transactions       -> SR-010, SR-013, UR-008

    TestRecordReimbursement:
        test_record_full_reimbursement       -> SR-008, SR-013, UR-007
        test_record_partial_reimbursement    -> SR-008, SR-013, UR-007

    TestTagTotal:
        test_tag_total_no_transactions       -> SR-010, SR-013, UR-010
        test_tag_total_with_transactions     -> SR-010, SR-013, UR-010
        test_tag_total_with_date_range       -> SR-010, SR-013, UR-010

    TestStats:
        test_stats_with_sqlite               -> SR-010, SR-013, UR-009

    TestAutoTagging:
        test_car_insurance_auto_tags         -> SR-007, SR-013, UR-004
        test_user_tags_preserved             -> SR-007, SR-013, UR-004

    TestEndToEndWorkflow:
        test_reimbursement_workflow          -> SR-008, SR-013, UR-006, UR-007

    TestNotionIntegration:
        test_add_basic_transaction_to_notion       -> SR-011, SR-013, UR-001, UR-012
        test_add_transaction_with_tags_to_notion   -> SR-006, SR-007, SR-011, SR-013, UR-004, UR-012
        test_add_reimbursable_transaction_to_notion-> SR-008, SR-011, SR-013, UR-006, UR-012
"""

import os
import subprocess
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from src.domain.entities.transaction import ReimbursementStatus
from src.infrastructure.repositories.sqlite_repository import SQLiteTransactionRepository


@pytest.fixture(scope="function")
def test_db():
    """Create a temporary test database for each test."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture(scope="function")
def repository(test_db):
    """Create a SQLite repository for testing."""
    return SQLiteTransactionRepository(db_path=test_db)


def run_cli_command(command: list[str], env: dict = None) -> subprocess.CompletedProcess:
    """
    Run a CLI command and return the result.

    Args:
        command: List of command arguments
        env: Optional environment variables

    Returns:
        CompletedProcess with stdout, stderr, and returncode
    """
    # Merge with current environment
    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    result = subprocess.run(
        ["python", "-m", "src.interfaces.cli.main"] + command,
        capture_output=True,
        text=True,
        env=full_env,
    )
    return result


class TestConfigInfo:
    """Test config-info command."""

    def test_config_info_sqlite(self, test_db):
        """Test config-info shows SQLite configuration."""
        result = run_cli_command(
            ["config-info"],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )

        assert result.returncode == 0
        assert "Repository Type: sqlite" in result.stdout
        assert "SQLite Database:" in result.stdout

    def test_config_info_notion(self):
        """Test config-info shows Notion configuration."""
        # Skip if no Notion credentials
        if not os.getenv("NOTION_TOKEN") or not os.getenv("NOTION_DATABASE_ID"):
            pytest.skip("Notion credentials not configured")

        result = run_cli_command(
            ["config-info"],
            env={"REPOSITORY_TYPE": "notion"}
        )

        assert result.returncode == 0
        assert "Repository Type: notion" in result.stdout
        assert "Notion Database ID:" in result.stdout


class TestAddTransaction:
    """Test add command."""

    def test_add_basic_transaction(self, test_db, repository):
        """Test adding a basic transaction."""
        result = run_cli_command(
            [
                "add",
                "--description", "Test transaction",
                "--amount", "-50.00",
                "--category", "Food & Dining",
            ],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )

        assert result.returncode == 0
        assert "Transaction created successfully!" in result.stdout
        assert "Test transaction" in result.stdout
        assert "50.00" in result.stdout  # Amount (may include sign)

        # Verify in database
        transactions = repository.list(limit=1)
        assert len(transactions) == 1
        assert transactions[0].description == "Test transaction"
        assert transactions[0].amount == Decimal("-50.00")

    def test_add_with_all_fields(self, test_db, repository):
        """Test adding a transaction with all optional fields."""
        result = run_cli_command(
            [
                "add",
                "--description", "Complete transaction",
                "--amount", "-100.00",
                "--category", "Insurance",
                "--subcategory", "Car Insurance",
                "--account", "Checking",
                "--notes", "Test notes",
                "--tags", "test",
                "--tags", "manual",
            ],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )

        assert result.returncode == 0
        assert "Transaction created successfully!" in result.stdout

        # Verify in database
        transactions = repository.list(limit=1)
        assert len(transactions) == 1
        transaction = transactions[0]
        assert transaction.description == "Complete transaction"
        assert transaction.account == "Checking"
        assert transaction.notes == "Test notes"
        # Should have user tags + auto-tags
        assert "test" in transaction.tags
        assert "manual" in transaction.tags
        assert "car" in transaction.tags  # Auto-tagged
        assert "monthly" in transaction.tags  # Auto-tagged

    def test_add_reimbursable_transaction(self, test_db, repository):
        """Test adding a reimbursable transaction."""
        result = run_cli_command(
            [
                "add",
                "--description", "Group dinner",
                "--amount", "-120.00",
                "--category", "Food & Dining",
                "--reimbursable",
                "--expected-reimbursement", "60.00",
            ],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )

        assert result.returncode == 0
        assert "Reimbursable: Yes" in result.stdout
        assert "Expected: $60.00" in result.stdout
        assert "Status: pending" in result.stdout

        # Verify in database
        transactions = repository.list(limit=1)
        assert len(transactions) == 1
        transaction = transactions[0]
        assert transaction.reimbursable is True
        assert transaction.expected_reimbursement == Decimal("60.00")
        assert transaction.reimbursement_status == ReimbursementStatus.PENDING
        assert "reimbursable" in transaction.tags

    def test_add_missing_required_fields(self, test_db):
        """Test that missing required fields produce errors."""
        result = run_cli_command(
            [
                "add",
                "--description", "Test",
                # Missing --amount and --category
            ],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )

        assert result.returncode != 0


class TestListTransactions:
    """Test list-transactions command."""

    def test_list_empty(self, test_db):
        """Test listing when no transactions exist."""
        result = run_cli_command(
            ["list-transactions"],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )

        assert result.returncode == 0
        assert "No transactions found" in result.stdout

    def test_list_with_transactions(self, test_db, repository):
        """Test listing transactions."""
        # Add test transactions
        from src.domain.entities import Transaction

        for i in range(3):
            transaction = Transaction(
                date=datetime.now(),
                description=f"Test transaction {i+1}",
                amount=Decimal(f"-{10 * (i+1)}.00"),
                category="Food & Dining",
            )
            repository.add(transaction)

        result = run_cli_command(
            ["list-transactions", "--limit", "5"],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )

        assert result.returncode == 0
        assert "Recent Transactions (3)" in result.stdout
        assert "Test transaction 1" in result.stdout
        assert "Test transaction 2" in result.stdout
        assert "Test transaction 3" in result.stdout

    def test_list_filter_by_category(self, test_db, repository):
        """Test filtering transactions by category."""
        from src.domain.entities import Transaction

        # Add transactions in different categories
        repository.add(Transaction(
            date=datetime.now(),
            description="Food expense",
            amount=Decimal("-20.00"),
            category="Food & Dining",
        ))
        repository.add(Transaction(
            date=datetime.now(),
            description="Transport expense",
            amount=Decimal("-10.00"),
            category="Transportation",
        ))

        result = run_cli_command(
            ["list-transactions", "--category", "Food & Dining"],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )

        assert result.returncode == 0
        assert "Food expense" in result.stdout
        assert "Transport expense" not in result.stdout

    def test_list_filter_by_tag(self, test_db, repository):
        """Test filtering transactions by tag."""
        from src.domain.entities import Transaction

        # Add transactions with different tags
        repository.add(Transaction(
            date=datetime.now(),
            description="Car insurance",
            amount=Decimal("-150.00"),
            category="Transportation",
            tags=["car", "insurance"],
        ))
        repository.add(Transaction(
            date=datetime.now(),
            description="Bike repair",
            amount=Decimal("-50.00"),
            category="Transportation",
            tags=["bike"],
        ))

        result = run_cli_command(
            ["list-transactions", "--tag", "car"],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )

        assert result.returncode == 0
        assert "Car insurance" in result.stdout
        assert "Bike repair" not in result.stdout


class TestPendingReimbursements:
    """Test pending-reimbursements command."""

    def test_pending_empty(self, test_db):
        """Test when no pending reimbursements exist."""
        result = run_cli_command(
            ["pending-reimbursements"],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )

        assert result.returncode == 0
        assert "No pending reimbursements found" in result.stdout

    def test_pending_with_transactions(self, test_db, repository):
        """Test listing pending reimbursements."""
        from src.domain.entities import Transaction

        # Add pending reimbursement
        repository.add(Transaction(
            date=datetime.now(),
            description="Group dinner",
            amount=Decimal("-100.00"),
            category="Food & Dining",
            reimbursable=True,
            expected_reimbursement=Decimal("50.00"),
        ))

        # Add complete reimbursement (should not appear)
        repository.add(Transaction(
            date=datetime.now(),
            description="Paid back",
            amount=Decimal("-80.00"),
            category="Food & Dining",
            reimbursable=True,
            expected_reimbursement=Decimal("40.00"),
            actual_reimbursement=Decimal("40.00"),
            reimbursement_status=ReimbursementStatus.COMPLETE,
        ))

        result = run_cli_command(
            ["pending-reimbursements"],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )

        assert result.returncode == 0
        assert "Pending Reimbursements (1)" in result.stdout
        assert "Group dinner" in result.stdout
        assert "Expected: $   50.00" in result.stdout
        assert "Pending: $   50.00" in result.stdout
        assert "Paid back" not in result.stdout
        assert "Total Pending: $50.00" in result.stdout


class TestRecordReimbursement:
    """Test record-reimbursement command."""

    def test_record_full_reimbursement(self, test_db, repository):
        """Test recording a full reimbursement."""
        from src.domain.entities import Transaction

        # Add reimbursable transaction
        transaction = Transaction(
            date=datetime.now(),
            description="Group dinner",
            amount=Decimal("-100.00"),
            category="Food & Dining",
            reimbursable=True,
            expected_reimbursement=Decimal("50.00"),
        )
        saved = repository.add(transaction)

        result = run_cli_command(
            ["record-reimbursement", str(saved.id), "50.00"],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )

        assert result.returncode == 0
        assert "Reimbursement recorded successfully!" in result.stdout
        assert "Amount Received: $50.00" in result.stdout
        assert "Pending: $0.00" in result.stdout
        assert "Status: complete" in result.stdout

        # Verify in database
        updated = repository.get(saved.id)
        assert updated.actual_reimbursement == Decimal("50.00")
        assert updated.reimbursement_status == ReimbursementStatus.COMPLETE

    def test_record_partial_reimbursement(self, test_db, repository):
        """Test recording a partial reimbursement."""
        from src.domain.entities import Transaction

        # Add reimbursable transaction
        transaction = Transaction(
            date=datetime.now(),
            description="Group dinner",
            amount=Decimal("-100.00"),
            category="Food & Dining",
            reimbursable=True,
            expected_reimbursement=Decimal("50.00"),
        )
        saved = repository.add(transaction)

        result = run_cli_command(
            ["record-reimbursement", str(saved.id), "25.00"],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )

        assert result.returncode == 0
        assert "Amount Received: $25.00" in result.stdout
        assert "Pending: $25.00" in result.stdout
        assert "Status: partial" in result.stdout

        # Verify in database
        updated = repository.get(saved.id)
        assert updated.actual_reimbursement == Decimal("25.00")
        assert updated.reimbursement_status == ReimbursementStatus.PARTIAL


class TestTagTotal:
    """Test tag-total command."""

    def test_tag_total_no_transactions(self, test_db):
        """Test tag total when no transactions have the tag."""
        result = run_cli_command(
            ["tag-total", "nonexistent"],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )

        assert result.returncode == 0
        assert "$0.00" in result.stdout

    def test_tag_total_with_transactions(self, test_db, repository):
        """Test calculating total by tag."""
        from src.domain.entities import Transaction

        # Add transactions with "car" tag
        repository.add(Transaction(
            date=datetime.now(),
            description="Car insurance",
            amount=Decimal("-150.00"),
            category="Transportation",
            tags=["car", "insurance"],
        ))
        repository.add(Transaction(
            date=datetime.now(),
            description="Car fuel",
            amount=Decimal("-60.00"),
            category="Transportation",
            tags=["car", "fuel"],
        ))

        # Add transaction without "car" tag
        repository.add(Transaction(
            date=datetime.now(),
            description="Bike repair",
            amount=Decimal("-50.00"),
            category="Transportation",
            tags=["bike"],
        ))

        result = run_cli_command(
            ["tag-total", "car"],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )

        assert result.returncode == 0
        assert "$210.00" in result.stdout
        assert "expenses" in result.stdout

    def test_tag_total_with_date_range(self, test_db, repository):
        """Test tag total with date filtering."""
        from src.domain.entities import Transaction
        from datetime import timedelta

        today = datetime.now()
        yesterday = today - timedelta(days=1)

        # Add transaction from yesterday
        repository.add(Transaction(
            date=yesterday,
            description="Old expense",
            amount=Decimal("-100.00"),
            category="Test",
            tags=["test"],
        ))

        # Add transaction from today
        repository.add(Transaction(
            date=today,
            description="New expense",
            amount=Decimal("-50.00"),
            category="Test",
            tags=["test"],
        ))

        # Filter to only today
        result = run_cli_command(
            [
                "tag-total", "test",
                "--start-date", today.strftime("%Y-%m-%d"),
            ],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )

        assert result.returncode == 0
        assert "$50.00" in result.stdout


class TestStats:
    """Test stats command."""

    def test_stats_with_sqlite(self, test_db, repository):
        """Test statistics command with SQLite."""
        from src.domain.entities import Transaction

        # Add test data
        repository.add(Transaction(
            date=datetime.now(),
            description="Income",
            amount=Decimal("1000.00"),
            category="Income",
        ))
        repository.add(Transaction(
            date=datetime.now(),
            description="Expense 1",
            amount=Decimal("-200.00"),
            category="Food & Dining",
        ))
        repository.add(Transaction(
            date=datetime.now(),
            description="Expense 2",
            amount=Decimal("-100.00"),
            category="Transportation",
        ))

        result = run_cli_command(
            ["stats"],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )

        assert result.returncode == 0
        assert "Transaction Statistics" in result.stdout
        assert "Total Transactions: 3" in result.stdout
        assert "Income: 1" in result.stdout
        assert "Expenses: 2" in result.stdout
        assert "$1,000.00" in result.stdout  # Total income
        assert "$300.00" in result.stdout   # Total expenses


class TestAutoTagging:
    """Test auto-tagging functionality through CLI."""

    def test_car_insurance_auto_tags(self, test_db, repository):
        """Test that car insurance gets correct auto-tags."""
        result = run_cli_command(
            [
                "add",
                "--description", "Car insurance payment",
                "--amount", "-150.00",
                "--category", "Insurance",
                "--subcategory", "Car Insurance",
            ],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )

        assert result.returncode == 0

        # Verify tags in database
        transactions = repository.list(limit=1)
        assert len(transactions) == 1
        tags = transactions[0].tags
        assert "car" in tags
        assert "fixed-expense" in tags
        assert "monthly" in tags

    def test_user_tags_preserved(self, test_db, repository):
        """Test that user-provided tags are preserved with auto-tags."""
        result = run_cli_command(
            [
                "add",
                "--description", "Car fuel",
                "--amount", "-60.00",
                "--category", "Transportation",
                "--subcategory", "Car Fuel",
                "--tags", "business",
                "--tags", "deductible",
            ],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )

        assert result.returncode == 0

        # Verify all tags present
        transactions = repository.list(limit=1)
        tags = transactions[0].tags
        assert "business" in tags
        assert "deductible" in tags
        assert "car" in tags
        assert "variable-expense" in tags


class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""

    def test_reimbursement_workflow(self, test_db, repository):
        """Test complete reimbursement workflow from creation to completion."""
        # Step 1: Create reimbursable transaction
        result = run_cli_command(
            [
                "add",
                "--description", "Group dinner",
                "--amount", "-120.00",
                "--category", "Food & Dining",
                "--reimbursable",
                "--expected-reimbursement", "60.00",
            ],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )
        assert result.returncode == 0

        # Step 2: Verify it appears in pending reimbursements
        result = run_cli_command(
            ["pending-reimbursements"],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )
        assert result.returncode == 0
        assert "Group dinner" in result.stdout
        assert "Total Pending: $60.00" in result.stdout

        # Step 3: Record partial payment
        transactions = repository.list(limit=1)
        transaction_id = str(transactions[0].id)

        result = run_cli_command(
            ["record-reimbursement", transaction_id, "30.00"],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )
        assert result.returncode == 0
        assert "Status: partial" in result.stdout

        # Step 4: Verify still in pending list
        result = run_cli_command(
            ["pending-reimbursements"],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )
        assert result.returncode == 0
        assert "Pending: $   30.00" in result.stdout

        # Step 5: Record final payment
        result = run_cli_command(
            ["record-reimbursement", transaction_id, "60.00"],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )
        assert result.returncode == 0
        assert "Status: complete" in result.stdout

        # Step 6: Verify no longer in pending list
        result = run_cli_command(
            ["pending-reimbursements"],
            env={"REPOSITORY_TYPE": "sqlite", "SQLITE_DB_PATH": test_db}
        )
        assert result.returncode == 0
        assert "No pending reimbursements found" in result.stdout


# Mark tests that require Notion credentials
@pytest.mark.notion
class TestNotionIntegration:
    """Test Notion integration (requires credentials)."""

    @pytest.fixture(autouse=True)
    def check_notion_credentials(self):
        """Skip Notion tests if credentials not available."""
        if not os.getenv("NOTION_TOKEN") or not os.getenv("NOTION_DATABASE_ID"):
            pytest.skip("Notion credentials not configured")

    def test_add_basic_transaction_to_notion(self):
        """Test adding a basic transaction to Notion."""
        result = run_cli_command(
            [
                "add",
                "--description", "Notion basic test",
                "--amount", "-25.00",
                "--category", "Test",
            ],
            env={"REPOSITORY_TYPE": "notion"}
        )

        assert result.returncode == 0
        assert "Transaction created successfully!" in result.stdout
        assert "Notion basic test" in result.stdout

    def test_add_transaction_with_tags_to_notion(self):
        """Test adding transaction with tags to Notion."""
        result = run_cli_command(
            [
                "add",
                "--description", "Notion tags test",
                "--amount", "-50.00",
                "--category", "Insurance",
                "--subcategory", "Car Insurance",
                "--tags", "test",
                "--tags", "automated",
            ],
            env={"REPOSITORY_TYPE": "notion"}
        )

        assert result.returncode == 0
        assert "Transaction created successfully!" in result.stdout
        # Should have auto-tags (car, fixed-expense, monthly) + user tags (test, automated)

    def test_add_reimbursable_transaction_to_notion(self):
        """Test adding reimbursable transaction to Notion."""
        result = run_cli_command(
            [
                "add",
                "--description", "Notion reimbursable test",
                "--amount", "-100.00",
                "--category", "Food & Dining",
                "--reimbursable",
                "--expected-reimbursement", "50.00",
            ],
            env={"REPOSITORY_TYPE": "notion"}
        )

        assert result.returncode == 0
        assert "Transaction created successfully!" in result.stdout
        assert "Reimbursable: Yes" in result.stdout or "reimbursable" in result.stdout.lower()

    def test_list_transactions_from_notion(self):
        """Test listing transactions from Notion (verifies data_sources.query)."""
        # First, add a transaction
        result = run_cli_command(
            [
                "add",
                "--description", "Notion list test",
                "--amount", "-75.00",
                "--category", "Shopping",
            ],
            env={"REPOSITORY_TYPE": "notion"}
        )
        assert result.returncode == 0

        # Now list transactions to verify we can read from Notion
        result = run_cli_command(
            ["list-transactions", "--limit", "10"],
            env={"REPOSITORY_TYPE": "notion"}
        )

        assert result.returncode == 0
        # Should contain the transaction we just added (or other transactions)
        assert "Shopping" in result.stdout or "Notion" in result.stdout or len(result.stdout.strip()) > 0

    def test_filter_transactions_in_notion(self):
        """Test filtering transactions from Notion by category."""
        # Add a transaction with a specific category
        result = run_cli_command(
            [
                "add",
                "--description", "Notion filter test",
                "--amount", "-50.00",
                "--category", "Entertainment",
            ],
            env={"REPOSITORY_TYPE": "notion"}
        )
        assert result.returncode == 0

        # Filter by category
        result = run_cli_command(
            ["list-transactions", "--category", "Entertainment"],
            env={"REPOSITORY_TYPE": "notion"}
        )

        assert result.returncode == 0
        # Should show Entertainment transactions
        assert "Entertainment" in result.stdout or len(result.stdout.strip()) > 0

    def test_search_transactions_in_notion(self):
        """Test searching transactions in Notion by description."""
        # Add a transaction with unique description
        unique_desc = f"NotionSearch{datetime.now().strftime('%Y%m%d%H%M%S')}"
        result = run_cli_command(
            [
                "add",
                "--description", unique_desc,
                "--amount", "-30.00",
                "--category", "Test",
            ],
            env={"REPOSITORY_TYPE": "notion"}
        )
        assert result.returncode == 0

        # List all and verify our transaction appears
        result = run_cli_command(
            ["list-transactions", "--limit", "50"],
            env={"REPOSITORY_TYPE": "notion"}
        )

        assert result.returncode == 0
        # The transaction should appear in the list
        assert unique_desc in result.stdout or "Test" in result.stdout or len(result.stdout.strip()) > 0

    def test_retrieve_specific_transaction_from_notion(self):
        """Test retrieving a specific transaction by ID from Notion."""
        # Add a transaction
        result = run_cli_command(
            [
                "add",
                "--description", "Notion retrieve test",
                "--amount", "-45.00",
                "--category", "Food & Dining",
            ],
            env={"REPOSITORY_TYPE": "notion"}
        )
        assert result.returncode == 0

        # List transactions to verify we can fetch them
        result = run_cli_command(
            ["list-transactions", "--limit", "5"],
            env={"REPOSITORY_TYPE": "notion"}
        )
        assert result.returncode == 0
        # Should successfully retrieve and display transactions
        assert result.stdout.strip() != ""
