"""Use case for exporting transactions to CSV."""

import csv
import logging
from pathlib import Path
from typing import Optional

from src.domain.repositories import TransactionRepository

logger = logging.getLogger(__name__)


class ExportCSVUseCase:
    """
    Use case for exporting transactions to CSV file.

    This allows users to:
    - Export all transactions or filtered subset to CSV
    - Analyze data in Excel or other tools
    - Backup transaction data
    - Share data with accountants or financial advisors
    """

    def __init__(self, repository: TransactionRepository):
        """
        Initialize use case.

        Args:
            repository: Transaction repository (Notion or SQLite).
        """
        self.repository = repository

    def execute(
        self,
        output_path: str,
        category: Optional[str] = None,
        account: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> int:
        """
        Export transactions to CSV file.

        Args:
            output_path: Path to output CSV file.
            category: Optional category filter.
            account: Optional account filter.
            limit: Optional maximum number of transactions.

        Returns:
            Number of transactions exported.

        Raises:
            RepositoryError: If transactions cannot be fetched.
            IOError: If file cannot be written.
        """
        # Fetch transactions
        if category:
            transactions = self.repository.get_by_category(category)
            if limit:
                transactions = transactions[:limit]
        elif account:
            transactions = self.repository.get_by_account(account)
            if limit:
                transactions = transactions[:limit]
        else:
            transactions = self.repository.list(limit=limit)

        logger.info(f"Exporting {len(transactions)} transactions to CSV")

        # Ensure output directory exists
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Write to CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'id',
                'date',
                'description',
                'summary',
                'amount',
                'category',
                'subcategory',
                'account',
                'tags',
                'notes',
                'reviewed',
                'ai_confidence',
                'reimbursable',
                'expected_reimbursement',
                'actual_reimbursement',
                'reimbursement_status',
                'created_at',
                'updated_at',
            ]

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for txn in transactions:
                writer.writerow({
                    'id': str(txn.id),
                    'date': txn.date.strftime('%Y-%m-%d'),
                    'description': txn.description,
                    'summary': txn.summary or '',
                    'amount': float(txn.amount),
                    'category': txn.category,
                    'subcategory': txn.subcategory or '',
                    'account': txn.account or '',
                    'tags': ','.join(txn.tags) if txn.tags else '',
                    'notes': txn.notes or '',
                    'reviewed': txn.reviewed,
                    'ai_confidence': f'{txn.ai_confidence:.2f}' if txn.ai_confidence is not None else '',
                    'reimbursable': txn.reimbursable,
                    'expected_reimbursement': float(txn.expected_reimbursement),
                    'actual_reimbursement': float(txn.actual_reimbursement),
                    'reimbursement_status': txn.reimbursement_status.value,
                    'created_at': txn.created_at.isoformat(),
                    'updated_at': txn.updated_at.isoformat(),
                })

        logger.info(f"Successfully exported {len(transactions)} transactions to {output_path}")
        return len(transactions)
