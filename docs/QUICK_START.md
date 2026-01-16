# Quick Start Guide

Get up and running with Budget Notion in 5 minutes!

## Option 1: SQLite Mode (No Notion Required)

Perfect for testing without setting up Notion.

```bash
# 1. Run setup script
./scripts/setup.sh

# 2. Activate virtual environment
source venv/bin/activate

# 3. Set SQLite mode in .env
echo "REPOSITORY_TYPE=sqlite" >> .env

# 4. Add a transaction
python -m src.interfaces.cli.main add \
  --description "Coffee at Starbucks" \
  --amount -5.50 \
  --category "Food & Dining"

# 5. List transactions
python -m src.interfaces.cli.main list-transactions

# 6. View statistics
python -m src.interfaces.cli.main stats
```

Done! Your transactions are stored in `data/transactions.db`

## Option 2: Notion Mode (Full Integration)

### Step 1: Setup Notion

1. **Create Notion Integration**
   - Visit [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations)
   - Click "New integration"
   - Name it "Budget Notion"
   - Copy the token (starts with `secret_`)

2. **Create Database**
   - In Notion, create a new page
   - Add a "Table" database
   - Name it "Transactions"
   - Add these properties:
     - Description (Title) ✓ Already exists
     - Date (Date type)
     - Amount (Number type, Dollar format)
     - Category (Select type)
     - Account (Select type)
     - Notes (Text type)
     - Reviewed (Checkbox type)
     - Transaction ID (Text type)
     - AI Confidence (Number type)

3. **Share Database**
   - Click "..." on your database
   - Click "Add connections"
   - Select "Budget Notion" integration

4. **Get Database ID**
   - From URL: `https://notion.so/<workspace>/<DATABASE_ID>?v=...`
   - Copy the 32-character ID

### Step 2: Configure Budget Notion

```bash
# 1. Run setup
./scripts/setup.sh

# 2. Edit .env file
nano .env

# 3. Add your credentials:
REPOSITORY_TYPE=notion
NOTION_TOKEN=secret_abc123xyz...
NOTION_DATABASE_ID=1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p

# 4. Save and exit (Ctrl+X, Y, Enter)
```

### Step 3: Use It!

```bash
# Activate environment
source venv/bin/activate

# Add a transaction
python -m src.interfaces.cli.main add \
  --description "Lunch at cafe" \
  --amount -12.50 \
  --category "Food & Dining" \
  --account "Credit Card"

# Check Notion - your transaction is there!
```

## Option 3: Import Bank Statement

```bash
# For ING Bank (Netherlands)
python -m src.interfaces.cli.main import-csv \
  Downloads/ing_statement.csv \
  --bank ing \
  --category "Uncategorized" \
  --account "Checking"

# For Rabobank
python -m src.interfaces.cli.main import-csv \
  Downloads/rabo_statement.csv \
  --bank rabobank

# For Generic CSV
python -m src.interfaces.cli.main import-csv \
  Downloads/statement.csv \
  --category "Uncategorized"
```

**Supported Banks:**
- `ing` - ING Bank (NL)
- `rabobank` - Rabobank (NL)
- `abn_amro` - ABN AMRO (NL)
- `generic_us` - US banks
- `generic_uk` - UK banks

## Option 4: Docker (Production)

```bash
# 1. Create secrets
mkdir secrets
echo "your_notion_token" > secrets/notion_token.txt
echo "your_database_id" > secrets/notion_database_id.txt

# 2. Build and run
cd docker
docker-compose up -d

# 3. Use CLI via Docker
docker-compose run app python -m src.interfaces.cli.main add \
  --description "Docker test" \
  --amount -10.00 \
  --category "Test"

# 4. View logs
docker-compose logs -f
```

## Common Commands

```bash
# Add transaction with all details
python -m src.interfaces.cli.main add \
  --date 2026-01-15 \
  --description "Grocery shopping" \
  --amount -87.32 \
  --category "Food & Dining" \
  --account "Checking" \
  --notes "Weekly shopping"

# List last 20 transactions
python -m src.interfaces.cli.main list-transactions --limit 20

# Filter by category
python -m src.interfaces.cli.main list-transactions \
  --category "Food & Dining" \
  --limit 10

# Show statistics (SQLite only)
python -m src.interfaces.cli.main stats

# View current configuration
python -m src.interfaces.cli.main config-info
```

## Troubleshooting

### "Module not found" error

```bash
# Make sure you're in project root
cd budget-notion

# Activate virtual environment
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### "Notion integration cannot access database"

1. Go to your Notion database
2. Click "..." → "Add connections"
3. Select your integration

### "Invalid database ID"

1. Get ID from database URL
2. It should be 32 characters (no hyphens)
3. Update NOTION_DATABASE_ID in .env

### CSV import fails

```bash
# Try without bank config first
python -m src.interfaces.cli.main import-csv \
  statement.csv \
  --category "Uncategorized"

# Check CSV format
head -5 statement.csv

# See docs/CSV_FORMAT.md for custom configuration
```

## Next Steps

1. **Read Full Documentation**
   - [README.md](../README.md) - Complete guide
   - [NOTION_SCHEMA.md](NOTION_SCHEMA.md) - Notion setup details
   - [PHASE1_SUMMARY.md](PHASE1_SUMMARY.md) - What's included

2. **Customize**
   - Add your own categories
   - Create bank-specific CSV configs
   - Set up Docker deployment

3. **Integrate**
   - Import historical statements
   - Set up scheduled imports
   - Create Notion dashboard views

4. **Extend** (Future)
   - Add ML categorization (Phase 2)
   - Build budgets (Phase 3)
   - Create API (Phase 4)

## Tips

- **Use SQLite for testing**: Fast and no Notion setup needed
- **Start small**: Add a few transactions manually first
- **Review imports**: Always check imported transactions
- **Backup data**: Export Notion database regularly
- **Check logs**: Use `--log-level DEBUG` for troubleshooting

## Getting Help

- Check [README.md](../README.md) for detailed documentation
- See [NOTION_SCHEMA.md](NOTION_SCHEMA.md) for Notion setup
- Read error messages carefully - they're descriptive!
- Check your .env configuration

---

**Time to first transaction**: ~5 minutes with SQLite, ~15 minutes with Notion

Happy budgeting! 💰
