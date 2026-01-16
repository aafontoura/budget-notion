"""Category domain entity."""

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID, uuid4


@dataclass
class Category:
    """
    Category entity for organizing transactions.

    Supports hierarchical categories (parent-child relationships).
    """

    name: str
    color: str = "gray"
    parent_id: Optional[UUID] = None
    keywords: list[str] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        """Validate category data after initialization."""
        if not self.name or not self.name.strip():
            raise ValueError("Category name cannot be empty")

        # Normalize color to lowercase
        self.color = self.color.lower()

        # Valid Notion colors
        valid_colors = {
            "default", "gray", "brown", "orange", "yellow",
            "green", "blue", "purple", "pink", "red"
        }

        if self.color not in valid_colors:
            raise ValueError(f"Color must be one of {valid_colors}")

    @property
    def is_subcategory(self) -> bool:
        """Check if this is a subcategory (has a parent)."""
        return self.parent_id is not None

    def add_keyword(self, keyword: str) -> "Category":
        """
        Add a keyword for ML categorization training.

        Returns a new Category instance (immutable pattern).
        """
        if keyword and keyword.strip() and keyword not in self.keywords:
            new_keywords = self.keywords + [keyword.lower()]
            return Category(
                id=self.id,
                name=self.name,
                color=self.color,
                parent_id=self.parent_id,
                keywords=new_keywords
            )
        return self

    def matches_keyword(self, text: str) -> bool:
        """
        Check if text contains any of the category keywords.

        Used for rule-based categorization.
        """
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.keywords)

    def __str__(self) -> str:
        """Human-readable string representation."""
        parent_str = f" (subcategory of {self.parent_id})" if self.parent_id else ""
        return f"{self.name}{parent_str}"

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return f"Category(id={self.id}, name='{self.name}', color='{self.color}')"


# Default category set for quick start
DEFAULT_CATEGORIES = [
    Category(name="Food & Dining", color="red", keywords=["restaurant", "food", "cafe", "starbucks", "mcdonald"]),
    Category(name="Transportation", color="blue", keywords=["uber", "lyft", "gas", "parking", "transit"]),
    Category(name="Shopping", color="green", keywords=["amazon", "store", "retail", "purchase"]),
    Category(name="Bills & Utilities", color="yellow", keywords=["electricity", "water", "internet", "phone", "bill"]),
    Category(name="Entertainment", color="purple", keywords=["movie", "netflix", "spotify", "game", "concert"]),
    Category(name="Healthcare", color="pink", keywords=["pharmacy", "doctor", "hospital", "medical", "health"]),
    Category(name="Income", color="green", keywords=["salary", "payment", "income", "paycheck", "deposit"]),
    Category(name="Transfer", color="gray", keywords=["transfer", "atm", "withdrawal"]),
    Category(name="Other", color="default", keywords=[]),
]
