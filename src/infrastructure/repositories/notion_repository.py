"""Notion implementation of TransactionRepository."""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from notion_client import Client
from notion_client.errors import APIResponseError

from src.domain.entities import Transaction
from src.domain.repositories import (
    DuplicateTransactionError,
    RepositoryError,
    TransactionNotFoundError,
    TransactionRepository,
)

logger = logging.getLogger(__name__)


class NotionTransactionRepository(TransactionRepository):
    """
    Notion-based implementation of TransactionRepository.

    This adapter maps between domain entities and Notion API format.
    Can be easily swapped for other implementations (SQLite, Web API, Obsidian, etc.)
    """

    def __init__(self, client: Client, database_id: str):
        """
        Initialize Notion repository.

        Args:
            client: Authenticated Notion client.
            database_id: ID of the Notion database for transactions.
        """
        self.client = client
        self.database_id = database_id

    def add(self, transaction: Transaction) -> Transaction:
        """Add a new transaction to Notion database."""
        try:
            # Map domain entity to Notion properties
            properties = self._transaction_to_notion_properties(transaction)

            # Create page in Notion database
            response = self.client.pages.create(
                parent={"database_id": self.database_id},
                properties=properties
            )

            # Update transaction with Notion page ID
            logger.info(f"Created transaction in Notion: {response['id']}")
            return transaction

        except APIResponseError as e:
            logger.error(f"Notion API error while adding transaction: {e}")
            raise RepositoryError(f"Failed to add transaction: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error while adding transaction: {e}")
            raise RepositoryError(f"Failed to add transaction: {e}") from e

    def get(self, transaction_id: UUID) -> Optional[Transaction]:
        """Retrieve a transaction by ID from Notion."""
        try:
            # In Notion, we store the UUID in a property and use Notion page ID
            # For now, we'll search by UUID in the transaction ID property
            results = self.client.databases.query(
                database_id=self.database_id,
                filter={
                    "property": "Transaction ID",
                    "rich_text": {"equals": str(transaction_id)}
                }
            )

            if not results["results"]:
                return None

            # Map Notion page to domain entity
            page = results["results"][0]
            return self._notion_page_to_transaction(page)

        except APIResponseError as e:
            logger.error(f"Notion API error while getting transaction: {e}")
            raise RepositoryError(f"Failed to get transaction: {e}") from e

    def list(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        category: Optional[str] = None,
        account: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[Transaction]:
        """List transactions with optional filtering."""
        try:
            # Build Notion filter
            filters = []

            if start_date:
                filters.append({
                    "property": "Date",
                    "date": {"on_or_after": start_date.isoformat()}
                })

            if end_date:
                filters.append({
                    "property": "Date",
                    "date": {"on_or_before": end_date.isoformat()}
                })

            if category:
                filters.append({
                    "property": "Category",
                    "select": {"equals": category}
                })

            if account:
                filters.append({
                    "property": "Account",
                    "select": {"equals": account}
                })

            # Construct query
            query_params: dict = {"database_id": self.database_id}

            if filters:
                if len(filters) == 1:
                    query_params["filter"] = filters[0]
                else:
                    query_params["filter"] = {"and": filters}

            if limit:
                query_params["page_size"] = min(limit, 100)  # Notion max is 100

            # Query Notion database
            response = self.client.databases.query(**query_params)

            # Map results to domain entities
            transactions = [
                self._notion_page_to_transaction(page)
                for page in response["results"]
            ]

            # Handle pagination if needed
            while response["has_more"] and (limit is None or len(transactions) < limit):
                response = self.client.databases.query(
                    **query_params,
                    start_cursor=response["next_cursor"]
                )
                transactions.extend([
                    self._notion_page_to_transaction(page)
                    for page in response["results"]
                ])

            # Apply offset and limit
            if offset:
                transactions = transactions[offset:]
            if limit:
                transactions = transactions[:limit]

            logger.info(f"Retrieved {len(transactions)} transactions from Notion")
            return transactions

        except APIResponseError as e:
            logger.error(f"Notion API error while listing transactions: {e}")
            raise RepositoryError(f"Failed to list transactions: {e}") from e

    def update(self, transaction: Transaction) -> Transaction:
        """Update an existing transaction in Notion."""
        try:
            # Find the Notion page ID for this transaction
            page = self._get_notion_page_by_uuid(transaction.id)

            if not page:
                raise TransactionNotFoundError(transaction.id)

            # Map domain entity to Notion properties
            properties = self._transaction_to_notion_properties(transaction)

            # Update page in Notion
            self.client.pages.update(
                page_id=page["id"],
                properties=properties
            )

            logger.info(f"Updated transaction in Notion: {page['id']}")
            return transaction

        except TransactionNotFoundError:
            raise
        except APIResponseError as e:
            logger.error(f"Notion API error while updating transaction: {e}")
            raise RepositoryError(f"Failed to update transaction: {e}") from e

    def delete(self, transaction_id: UUID) -> bool:
        """Delete a transaction from Notion (archives it)."""
        try:
            # Find the Notion page ID for this transaction
            page = self._get_notion_page_by_uuid(transaction_id)

            if not page:
                return False

            # Archive page in Notion (Notion doesn't support true deletion)
            self.client.pages.update(
                page_id=page["id"],
                archived=True
            )

            logger.info(f"Archived transaction in Notion: {page['id']}")
            return True

        except APIResponseError as e:
            logger.error(f"Notion API error while deleting transaction: {e}")
            raise RepositoryError(f"Failed to delete transaction: {e}") from e

    def get_by_category(self, category: str) -> list[Transaction]:
        """Get all transactions for a specific category."""
        return self.list(category=category)

    def get_total_by_category(
        self,
        category: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Decimal:
        """Calculate total spending/income for a category."""
        transactions = self.list(
            category=category,
            start_date=start_date,
            end_date=end_date
        )

        total = sum((t.amount for t in transactions), Decimal("0"))
        return total

    def search(self, query: str) -> list[Transaction]:
        """Search transactions by description."""
        try:
            response = self.client.databases.query(
                database_id=self.database_id,
                filter={
                    "property": "Description",
                    "title": {"contains": query}
                }
            )

            transactions = [
                self._notion_page_to_transaction(page)
                for page in response["results"]
            ]

            logger.info(f"Found {len(transactions)} transactions matching '{query}'")
            return transactions

        except APIResponseError as e:
            logger.error(f"Notion API error while searching transactions: {e}")
            raise RepositoryError(f"Failed to search transactions: {e}") from e

    # Private helper methods

    def _get_notion_page_by_uuid(self, transaction_id: UUID) -> Optional[dict]:
        """Get Notion page by transaction UUID."""
        results = self.client.databases.query(
            database_id=self.database_id,
            filter={
                "property": "Transaction ID",
                "rich_text": {"equals": str(transaction_id)}
            }
        )

        return results["results"][0] if results["results"] else None

    def _transaction_to_notion_properties(self, transaction: Transaction) -> dict:
        """Map Transaction entity to Notion properties format."""
        properties = {
            "Description": {
                "title": [{"text": {"content": transaction.description}}]
            },
            "Date": {
                "date": {"start": transaction.date.isoformat()}
            },
            "Amount": {
                "number": float(transaction.amount)
            },
            "Category": {
                "select": {"name": transaction.category}
            },
            "Reviewed": {
                "checkbox": transaction.reviewed
            },
            "Transaction ID": {
                "rich_text": [{"text": {"content": str(transaction.id)}}]
            },
        }

        # Add optional properties
        if transaction.account:
            properties["Account"] = {"select": {"name": transaction.account}}

        if transaction.notes:
            properties["Notes"] = {
                "rich_text": [{"text": {"content": transaction.notes}}]
            }

        if transaction.ai_confidence is not None:
            properties["AI Confidence"] = {
                "number": round(transaction.ai_confidence * 100, 2)
            }

        return properties

    def _notion_page_to_transaction(self, page: dict) -> Transaction:
        """Map Notion page to Transaction entity."""
        props = page["properties"]

        # Extract required properties
        description = self._extract_title(props, "Description")
        date_str = props["Date"]["date"]["start"]
        amount = Decimal(str(props["Amount"]["number"]))
        category = props["Category"]["select"]["name"]
        reviewed = props["Reviewed"]["checkbox"]

        # Extract UUID from Transaction ID property
        transaction_id_str = self._extract_rich_text(props, "Transaction ID")
        transaction_id = UUID(transaction_id_str) if transaction_id_str else UUID(page["id"])

        # Extract optional properties
        account = props.get("Account", {}).get("select", {}).get("name")
        notes = self._extract_rich_text(props, "Notes")

        ai_confidence = None
        if "AI Confidence" in props and props["AI Confidence"]["number"] is not None:
            ai_confidence = props["AI Confidence"]["number"] / 100.0

        # Parse date
        date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))

        # Extract timestamps
        created_at = datetime.fromisoformat(page["created_time"].replace("Z", "+00:00"))
        updated_at = datetime.fromisoformat(page["last_edited_time"].replace("Z", "+00:00"))

        return Transaction(
            id=transaction_id,
            date=date,
            description=description,
            amount=amount,
            category=category,
            account=account,
            notes=notes,
            reviewed=reviewed,
            ai_confidence=ai_confidence,
            created_at=created_at,
            updated_at=updated_at,
        )

    @staticmethod
    def _extract_title(props: dict, key: str) -> str:
        """Extract text from Notion title property."""
        if key not in props or not props[key]["title"]:
            return ""
        return props[key]["title"][0]["text"]["content"]

    @staticmethod
    def _extract_rich_text(props: dict, key: str) -> Optional[str]:
        """Extract text from Notion rich_text property."""
        if key not in props or not props[key]["rich_text"]:
            return None
        return props[key]["rich_text"][0]["text"]["content"]
