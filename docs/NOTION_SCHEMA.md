# Notion Database Schema

This document describes the Notion database structure required for Budget Notion integration.

## Transactions Database

### Required Properties

#### 1. Description (Title)
- **Type**: Title
- **Purpose**: Transaction description (merchant name, transaction details)
- **Example**: "Starbucks Coffee - Downtown", "Salary Payment"
- **Indexed**: Yes (Notion automatically indexes title)

#### 2. Date (Date)
- **Type**: Date
- **Purpose**: Transaction date
- **Format**: YYYY-MM-DD
- **Include Time**: No
- **Example**: 2026-01-15
- **Sortable**: Yes

#### 3. Amount (Number)
- **Type**: Number
- **Format**: Dollar ($)
- **Purpose**: Transaction amount
- **Negative**: Expenses (e.g., -$50.00)
- **Positive**: Income (e.g., +$3000.00)
- **Decimals**: 2

#### 4. Category (Select)
- **Type**: Select
- **Purpose**: Transaction category
- **Options** (with suggested colors):
  - Food & Dining (Red)
  - Transportation (Blue)
  - Shopping (Green)
  - Bills & Utilities (Yellow)
  - Entertainment (Purple)
  - Healthcare (Pink)
  - Income (Green)
  - Transfer (Gray)
  - Other (Default)

#### 5. Account (Select)
- **Type**: Select
- **Purpose**: Bank account or payment method
- **Options** (examples):
  - Checking Account
  - Savings Account
  - Credit Card
  - Cash
  - PayPal

### Optional Properties

#### 6. Notes (Text)
- **Type**: Text
- **Purpose**: Additional transaction notes or comments
- **Example**: "Business expense - keep receipt", "Split with roommate"

#### 7. Reviewed (Checkbox)
- **Type**: Checkbox
- **Purpose**: Mark if transaction has been manually reviewed
- **Default**: Unchecked
- **Auto-checked**: When AI confidence ≥ 90%

#### 8. Transaction ID (Text)
- **Type**: Text
- **Purpose**: Unique identifier (UUID) for programmatic access
- **Format**: UUID v4 (e.g., "550e8400-e29b-41d4-a716-446655440000")
- **Hidden**: Can be hidden from default view

#### 9. AI Confidence (Number)
- **Type**: Number
- **Format**: Percent (%) or Number (0-100)
- **Purpose**: AI categorization confidence score
- **Range**: 0-100
- **Example**: 85 (means 85% confidence)
- **Hidden**: Can be hidden from default view

## Database Views

### Recommended Views

#### 1. All Transactions (Default)
- **Type**: Table
- **Sort**: Date (descending)
- **Filters**: None
- **Visible Properties**: Date, Description, Amount, Category, Account

#### 2. Needs Review
- **Type**: Table
- **Sort**: Date (descending)
- **Filters**:
  - Reviewed = Unchecked
  - AI Confidence < 70 (if using AI)
- **Visible Properties**: Date, Description, Amount, Category, AI Confidence, Reviewed

#### 3. Expenses This Month
- **Type**: Table or Board (grouped by Category)
- **Sort**: Date (descending)
- **Filters**:
  - Date is this month
  - Amount < 0
- **Visible Properties**: Date, Description, Amount, Category

#### 4. Income
- **Type**: Table
- **Sort**: Date (descending)
- **Filters**:
  - Amount > 0
- **Visible Properties**: Date, Description, Amount, Category

#### 5. By Category (Board View)
- **Type**: Board
- **Group By**: Category
- **Sort**: Date (descending)
- **Filters**: Date is this month
- **Visible Properties**: Date, Description, Amount

## Setup Instructions

### Step 1: Create Database

1. Open Notion workspace
2. Click "+ New Page"
3. Select "Table" database
4. Name it "Transactions"

### Step 2: Add Properties

Click "+ Add a property" for each property listed above:

1. Rename default "Name" property to "Description" (already Title type)
2. Add "Date" property (Date type)
3. Add "Amount" property (Number type, Dollar format)
4. Add "Category" property (Select type)
   - Add color-coded options
5. Add "Account" property (Select type)
6. Add "Notes" property (Text type)
7. Add "Reviewed" property (Checkbox type)
8. Add "Transaction ID" property (Text type)
9. Add "AI Confidence" property (Number type, 0-100)

### Step 3: Configure Property Settings

**For Amount:**
- Click property → "Number" → "Dollar"
- Enable "Show as: Number"

**For Category:**
- Click property → "Edit property"
- Add options with colors:
  - Food & Dining → Red
  - Transportation → Blue
  - Shopping → Green
  - etc.

**For Transaction ID:**
- Click property → "Hide in view" (optional, for cleaner UI)

**For AI Confidence:**
- Click property → "Hide in view" (optional, for cleaner UI)

### Step 4: Create Views

1. Click "..." next to the database title
2. Select "Add a view"
3. Configure as described in "Recommended Views" section

### Step 5: Create Notion Integration

1. Go to [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click "+ New integration"
3. Name: "Budget Notion"
4. Associated workspace: Select your workspace
5. Capabilities:
   - ✓ Read content
   - ✓ Update content
   - ✓ Insert content
6. Click "Submit"
7. Copy the "Internal Integration Token"

### Step 6: Share Database with Integration

1. Open your Transactions database
2. Click "..." in the top right
3. Scroll to "Connections"
4. Click "Add connections"
5. Select "Budget Notion" integration

### Step 7: Get Database ID

**From Database URL:**
```
https://www.notion.so/<workspace>/<database_id>?v=<view_id>
```

The `<database_id>` is the 32-character string (with optional hyphens):
```
Example: 1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p
```

**Alternative Method:**
1. Open database as a full page
2. Click "Share" → "Copy link"
3. Extract ID from URL

### Step 8: Configure Budget Notion

Add to your `.env` file:
```bash
NOTION_TOKEN=secret_abc123xyz...
NOTION_DATABASE_ID=1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p
REPOSITORY_TYPE=notion
```

## Advanced Features

### Formulas (Optional)

Add these calculated properties for enhanced analytics:

#### Month (Formula)
```
formatDate(prop("Date"), "MMMM YYYY")
```
Shows transaction month (e.g., "January 2026")

#### Expense/Income (Formula)
```
if(prop("Amount") < 0, "Expense", if(prop("Amount") > 0, "Income", "Zero"))
```
Automatically categorizes as Expense or Income

#### Absolute Amount (Formula)
```
abs(prop("Amount"))
```
Shows amount without negative sign

### Relations (Future)

#### Link to Budgets Database

1. Create a "Budgets" database with:
   - Category (Select, matching Transaction categories)
   - Monthly Budget (Number, Dollar format)
   - Period (Select: Monthly, Quarterly, Yearly)

2. Add "Budget" property to Transactions:
   - Type: Relation
   - Related to: Budgets database
   - Relation property: Category

3. Add "Spent This Month" rollup to Budgets:
   - Type: Rollup
   - Relation: Transactions
   - Property: Amount
   - Calculate: Sum
   - Filter: Date is this month

## Troubleshooting

### Issue: "Integration cannot access database"

**Solution**: Make sure you shared the database with your integration (Step 6)

### Issue: "Property not found"

**Solution**: Check property names match exactly (case-sensitive):
- "Description" not "description"
- "Transaction ID" not "TransactionID"

### Issue: "Invalid database ID"

**Solution**:
1. Verify database ID is 32 characters
2. Remove hyphens if present
3. Make sure you're using the database ID, not the page ID

### Issue: "Date format error"

**Solution**: Ensure Date property format is YYYY-MM-DD without time

## Example Data

Here's what your database should look like:

| Description | Date | Amount | Category | Account | Reviewed |
|-------------|------|--------|----------|---------|----------|
| Starbucks Coffee | 2026-01-15 | -$5.75 | Food & Dining | Credit Card | ☑ |
| Grocery Store | 2026-01-14 | -$87.32 | Food & Dining | Checking | ☑ |
| Salary Payment | 2026-01-01 | $3,500.00 | Income | Checking | ☑ |
| Uber Ride | 2026-01-13 | -$15.20 | Transportation | Credit Card | ☐ |

## API Limitations

**Notion API Rate Limits:**
- 3 requests per second per integration
- Budget Notion automatically handles rate limiting

**Page Size:**
- Maximum 100 results per query
- Budget Notion automatically paginates

## Best Practices

1. **Consistent Categories**: Use the same category names across transactions
2. **Regular Review**: Check "Needs Review" view weekly
3. **Backup**: Export database regularly (Settings → Export)
4. **Archive Old Data**: Move transactions older than 2 years to archive database
5. **Use Views**: Create custom views for different analysis needs

## Need Help?

- [Notion API Documentation](https://developers.notion.com)
- [Budget Notion Issues](https://github.com/your-username/budget-notion/issues)
- [Notion Community](https://www.notion.so/help/category/notion-community)
