"""Notion implementation of TransactionRepository."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from notion_client import Client
from notion_client.errors import APIResponseError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.domain.entities import Transaction
from src.domain.entities.transaction import ReimbursementStatus
from src.domain.repositories import (
    DuplicateTransactionError,
    RepositoryError,
    TransactionNotFoundError,
    TransactionRepository,
)

logger = logging.getLogger(__name__)


# Retry decorator for Notion API calls with exponential backoff
# Retries up to 5 times with exponential backoff: 1s, 2s, 4s, 8s, 16s
def _log_retry_attempt(retry_state):  # type: ignore
    """Log retry attempts for Notion API calls."""
    if retry_state.outcome and retry_state.outcome.failed:
        exc = retry_state.outcome.exception()
        logger.warning(
            f"Notion API error, retrying ({retry_state.attempt_number}/5): {exc}"
        )


notion_retry = retry(
    retry=retry_if_exception_type(APIResponseError),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=60),
    reraise=True,
    before_sleep=_log_retry_attempt,
)


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
        self._data_source_id: Optional[str] = None  # Cached data source ID

    def _get_data_source_id(self) -> str:
        """
        Get the data source ID for querying the database.

        In Notion API 2025-09-03+, databases have separate data source IDs.
        This method retrieves and caches the first data source ID from the database.

        Returns:
            The data source ID to use for queries.

        Raises:
            RepositoryError: If data source ID cannot be retrieved.
        """
        if self._data_source_id is not None:
            return self._data_source_id

        try:
            # Retrieve database to get data source IDs
            db_info = self.client.databases.retrieve(database_id=self.database_id)  # type: ignore[misc]
            data_sources = db_info.get("data_sources", [])  # type: ignore[union-attr]

            if not data_sources or len(data_sources) == 0:
                raise RepositoryError(
                    f"No data sources found for database {self.database_id}"
                )

            # Use the first data source
            self._data_source_id = str(data_sources[0]["id"])  # type: ignore[index]
            logger.info(f"Retrieved data source ID: {self._data_source_id}")
            return self._data_source_id

        except APIResponseError as e:
            logger.error(f"Failed to retrieve data source ID: {e}")
            raise RepositoryError(f"Failed to get data source ID: {e}") from e

    @notion_retry
    def add(self, transaction: Transaction) -> Transaction:
        """Add a new transaction to Notion database with automatic retry on rate limits."""
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

    @notion_retry
    def get(self, transaction_id: UUID) -> Optional[Transaction]:
        """Retrieve a transaction by ID from Notion with automatic retry."""
        try:
            # In Notion, we store the UUID in a property and use Notion page ID
            # For now, we'll search by UUID in the transaction ID property
            # Use data_sources.query (Notion API version 2025-09-03+)
            # Note: Type checker shows Awaitable but Client returns sync results
            data_source_id = self._get_data_source_id()
            results = self.client.data_sources.query(  # type: ignore[misc]
                data_source_id=data_source_id,
                filter={
                    "property": "Transaction ID",
                    "rich_text": {"equals": str(transaction_id)}
                }
            )

            if not results["results"]:  # type: ignore[index]
                return None

            # Map Notion page to domain entity
            page = results["results"][0]  # type: ignore[index]
            return self._notion_page_to_transaction(page)

        except APIResponseError as e:
            logger.error(f"Notion API error while getting transaction: {e}")
            raise RepositoryError(f"Failed to get transaction: {e}") from e

    @notion_retry
    def list(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        category: Optional[str] = None,
        account: Optional[str] = None,
        tags: Optional[list[str]] = None,
        reimbursable_status: Optional[ReimbursementStatus] = None,
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

            if reimbursable_status:
                filters.append({
                    "property": "Reimbursement Status",
                    "select": {"equals": reimbursable_status.value}
                })

            # Note: Tags filtering will be done in-memory after fetching
            # because Notion's multi-select filtering is limited

            # Construct query
            data_source_id = self._get_data_source_id()
            query_params: dict = {"data_source_id": data_source_id}

            if filters:
                if len(filters) == 1:
                    query_params["filter"] = filters[0]
                else:
                    query_params["filter"] = {"and": filters}

            if limit:
                query_params["page_size"] = min(limit, 100)  # Notion max is 100

            # Query Notion data source (API version 2025-09-03+)
            # Note: Type checker shows Awaitable but Client returns sync results
            response = self.client.data_sources.query(**query_params)  # type: ignore[misc]

            # Map results to domain entities
            transactions = []
            for page in response["results"]:  # type: ignore[index]
                try:
                    transaction = self._notion_page_to_transaction(page)
                    transactions.append(transaction)
                except Exception as e:
                    logger.warning(f"Skipping invalid page {page.get('id', 'unknown')}: {e}")
                    continue

            # Handle pagination if needed
            while response["has_more"] and (limit is None or len(transactions) < limit):  # type: ignore[index]
                response = self.client.data_sources.query(  # type: ignore[misc]
                    **query_params,
                    start_cursor=response["next_cursor"]  # type: ignore[index]
                )
                transactions.extend([
                    self._notion_page_to_transaction(page)
                    for page in response["results"]  # type: ignore[index]
                ])

            # Apply in-memory tag filtering if specified
            if tags:
                transactions = [
                    t for t in transactions
                    if any(t.has_tag(tag) for tag in tags)
                ]

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

    @notion_retry
    def update(self, transaction: Transaction) -> Transaction:
        """Update an existing transaction in Notion with automatic retry."""
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

    @notion_retry
    def delete(self, transaction_id: UUID) -> bool:
        """Delete a transaction from Notion (archives it) with automatic retry."""
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

    def get_by_category(self, category: str) -> "list[Transaction]":
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

    def search(self, query: str) -> "list[Transaction]":
        """Search transactions by description."""
        try:
            # Note: Type checker shows Awaitable but Client returns sync results
            data_source_id = self._get_data_source_id()
            response = self.client.data_sources.query(  # type: ignore[misc]
                data_source_id=data_source_id,
                filter={
                    "property": "Description",
                    "title": {"contains": query}
                }
            )

            transactions = [
                self._notion_page_to_transaction(page)
                for page in response["results"]  # type: ignore[index]
            ]

            logger.info(f"Found {len(transactions)} transactions matching '{query}'")
            return transactions

        except APIResponseError as e:
            logger.error(f"Notion API error while searching transactions: {e}")
            raise RepositoryError(f"Failed to search transactions: {e}") from e

    # Private helper methods

    def _get_notion_page_by_uuid(self, transaction_id: UUID) -> Optional[dict]:
        """Get Notion page by transaction UUID."""
        # Note: Type checker shows Awaitable but Client returns sync results
        data_source_id = self._get_data_source_id()
        results = self.client.data_sources.query(  # type: ignore[misc]
            data_source_id=data_source_id,
            filter={
                "property": "Transaction ID",
                "rich_text": {"equals": str(transaction_id)}
            }
        )

        return results["results"][0] if results["results"] else None  # type: ignore[index,return-value]

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
            "Subcategory": {
                "select": {"name": transaction.subcategory} if transaction.subcategory else None
            },
            "AI Confidence": {
                "number": round(transaction.ai_confidence * 100, 2) if transaction.ai_confidence is not None else None
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

        # Add tags (multi-select)
        if transaction.tags:
            properties["Tags"] = {
                "multi_select": [{"name": tag} for tag in transaction.tags]
            }

        # Add reimbursement fields
        if transaction.reimbursable:
            properties["Reimbursable"] = {"checkbox": True}

            if transaction.expected_reimbursement > 0:
                properties["Expected Reimbursement"] = {
                    "number": float(transaction.expected_reimbursement)
                }

            if transaction.actual_reimbursement > 0:
                properties["Actual Reimbursement"] = {
                    "number": float(transaction.actual_reimbursement)
                }

            properties["Reimbursement Status"] = {
                "select": {"name": transaction.reimbursement_status.value}
            }

        return properties

    def _notion_page_to_transaction(self, page: dict) -> Transaction:
        """Map Notion page to Transaction entity."""
        if not page:
            raise ValueError("Page is None or empty")

        props = page.get("properties")
        if not props:
            raise ValueError(f"No properties found in page {page.get('id')}")

        # Extract required properties with defensive checks
        description = self._extract_title(props, "Description")

        # Date property - check if Date property exists and has a value
        if "Date" not in props:
            raise ValueError(f"Date property missing in page {page.get('id')}")

        date_field = props["Date"]
        if date_field is None:
            raise ValueError(f"Date property is None in page {page.get('id')}")

        if not isinstance(date_field, dict):
            raise ValueError(f"Date property is not a dict (type: {type(date_field)}) in page {page.get('id')}")

        date_prop = date_field.get("date")
        if date_prop is None:
            raise ValueError(f"Date.date is None in page {page.get('id')}")

        if not isinstance(date_prop, dict):
            raise ValueError(f"Date.date is not a dict in page {page.get('id')}")

        if "start" not in date_prop or date_prop["start"] is None:
            raise ValueError(f"Date.date.start missing or None in page {page.get('id')}")

        date_str = date_prop["start"]

        # Amount property
        if "Amount" not in props or props["Amount"] is None:
            raise ValueError(f"Amount property missing in page {page.get('id')}")

        amount_field = props["Amount"]
        if not isinstance(amount_field, dict):
            raise ValueError(f"Amount property is not a dict in page {page.get('id')}")

        amount_value = amount_field.get("number")
        if amount_value is None:
            raise ValueError(f"Amount.number is None in page {page.get('id')}")
        amount = Decimal(str(amount_value))

        # Category property
        if "Category" not in props or props["Category"] is None:
            raise ValueError(f"Category property missing in page {page.get('id')}")

        category_field = props["Category"]
        if not isinstance(category_field, dict):
            raise ValueError(f"Category property is not a dict in page {page.get('id')}")

        category_select = category_field.get("select")
        if not category_select or not isinstance(category_select, dict):
            raise ValueError(f"Category.select missing or invalid in page {page.get('id')}")

        category = category_select.get("name")
        if not category:
            raise ValueError(f"Category.select.name missing in page {page.get('id')}")

        # Reviewed property
        if "Reviewed" in props and props["Reviewed"] and isinstance(props["Reviewed"], dict):
            reviewed = props["Reviewed"].get("checkbox", False)
        else:
            reviewed = False

        # Extract UUID from Transaction ID property
        transaction_id_str = self._extract_rich_text(props, "Transaction ID")
        transaction_id = UUID(transaction_id_str) if transaction_id_str else UUID(page["id"])

        # Extract optional properties
        account = None
        if "Account" in props and props["Account"] and isinstance(props["Account"], dict):
            account_select = props["Account"].get("select")
            if account_select and isinstance(account_select, dict):
                account = account_select.get("name")

        notes = self._extract_rich_text(props, "Notes")

        ai_confidence = None
        if "AI Confidence" in props and props["AI Confidence"] and isinstance(props["AI Confidence"], dict):
            ai_conf_value = props["AI Confidence"].get("number")
            if ai_conf_value is not None:
                ai_confidence = ai_conf_value / 100.0

        # Parse date
        date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))

        # Extract timestamps
        created_at = datetime.fromisoformat(page["created_time"].replace("Z", "+00:00"))
        updated_at = datetime.fromisoformat(page["last_edited_time"].replace("Z", "+00:00"))

        # Extract tags (multi-select)
        tags = []
        if "Tags" in props and props["Tags"] and isinstance(props["Tags"], dict):
            multi_select = props["Tags"].get("multi_select")
            if multi_select and isinstance(multi_select, list):
                tags = [item.get("name", "") for item in multi_select if isinstance(item, dict) and item.get("name")]

        # Extract reimbursement fields
        reimbursable = False
        if "Reimbursable" in props and props["Reimbursable"] and isinstance(props["Reimbursable"], dict):
            reimbursable = props["Reimbursable"].get("checkbox", False)

        expected_reimbursement = Decimal("0")
        if "Expected Reimbursement" in props and props["Expected Reimbursement"] and isinstance(props["Expected Reimbursement"], dict):
            exp_reimb_value = props["Expected Reimbursement"].get("number")
            if exp_reimb_value is not None:
                expected_reimbursement = Decimal(str(exp_reimb_value))

        actual_reimbursement = Decimal("0")
        if "Actual Reimbursement" in props and props["Actual Reimbursement"] and isinstance(props["Actual Reimbursement"], dict):
            act_reimb_value = props["Actual Reimbursement"].get("number")
            if act_reimb_value is not None:
                actual_reimbursement = Decimal(str(act_reimb_value))

        reimbursement_status = ReimbursementStatus.NONE
        if "Reimbursement Status" in props and props["Reimbursement Status"] and isinstance(props["Reimbursement Status"], dict):
            status_select = props["Reimbursement Status"].get("select")
            if status_select and isinstance(status_select, dict):
                status_name = status_select.get("name")
                if status_name:
                    try:
                        reimbursement_status = ReimbursementStatus(status_name.lower())
                    except ValueError:
                        pass  # Keep default if invalid status

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
            tags=tags,
            reimbursable=reimbursable,
            expected_reimbursement=expected_reimbursement,
            actual_reimbursement=actual_reimbursement,
            reimbursement_status=reimbursement_status,
            created_at=created_at,
            updated_at=updated_at,
        )

    @staticmethod
    def _extract_title(props: dict, key: str) -> str:
        """Extract text from Notion title property."""
        if key not in props or props[key] is None:
            return ""

        title_prop = props[key]
        if not isinstance(title_prop, dict) or "title" not in title_prop:
            return ""

        title_list = title_prop["title"]
        if not title_list or not isinstance(title_list, list) or len(title_list) == 0:
            return ""

        return title_list[0].get("text", {}).get("content", "")

    @staticmethod
    def _extract_rich_text(props: dict, key: str) -> Optional[str]:
        """Extract text from Notion rich_text property."""
        if key not in props or props[key] is None:
            return None

        rich_text_prop = props[key]
        if not isinstance(rich_text_prop, dict) or "rich_text" not in rich_text_prop:
            return None

        rich_text_list = rich_text_prop["rich_text"]
        if not rich_text_list or not isinstance(rich_text_list, list) or len(rich_text_list) == 0:
            return None

        return rich_text_list[0].get("text", {}).get("content")

    def get_by_tag(self, tag: str) -> list[Transaction]:
        """Get all transactions with a specific tag."""
        return self.list(tags=[tag])

    def get_pending_reimbursements(self) -> list[Transaction]:
        """Get all transactions with pending or partial reimbursements."""
        # Get all reimbursable transactions
        all_reimbursable = self.list(reimbursable_status=ReimbursementStatus.PENDING)
        partial_reimbursable = self.list(reimbursable_status=ReimbursementStatus.PARTIAL)
        return all_reimbursable + partial_reimbursable

    def get_total_by_tag(
        self,
        tag: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Decimal:
        """Calculate total spending/income for transactions with a specific tag."""
        transactions = self.list(
            tags=[tag],
            start_date=start_date,
            end_date=end_date
        )

        total = sum((t.amount for t in transactions), Decimal("0"))
        return total
