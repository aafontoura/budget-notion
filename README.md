# Budget Notion

> Personal finance aggregator with AI-powered categorization and Notion integration

A modular, self-hosted personal finance tool that visualizes spending by categories and budgets, supports manual transaction entries and automated imports from bank statement files (CSV), and uses Notion databases as the UI layer via its API.

Built with **clean architecture** to enable seamless future swaps to other UIs (custom web apps, Obsidian) without core logic changes.

## Features

- **Transaction Management**: Add, view, and categorize financial transactions
- **Bank Statement Import**: Parse CSV files from various banks (ING, Rabobank, ABN AMRO, and more)
- **Notion Integration**: Use Notion as your financial dashboard with full API integration
- **SQLite Fallback**: Local-first design with SQLite for offline mode and fast queries
- **Clean Architecture**: Repository pattern enables easy UI swapping (Notion → Web App → Obsidian)
- **Docker Support**: Self-hosted, secure deployment with Docker Secrets
- **Python 3.14+**: Built with the latest Python features
- **AI-Ready**: Designed for future ML categorization integration

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Interfaces Layer                      │
│  (CLI, FastAPI, Streamlit - easily swappable)           │
└───────────────────┬─────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────┐
│                 Application Layer                        │
│         (Use Cases: Create, Import, Analyze)            │
└───────────────────┬─────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────┐
│                   Domain Layer                           │
│    (Entities: Transaction, Category, Budget)            │
│    (Repository Interface: TransactionRepository)        │
└───────────────────┬─────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────┐
│              Infrastructure Layer                        │
│  (Adapters: Notion, SQLite, CSV Parser)                 │
│  (Swappable implementations!)                           │
└─────────────────────────────────────────────────────────┘
```

**Key Principle**: The domain layer (core business logic) has **zero dependencies** on external services. Infrastructure adapters implement domain interfaces, allowing Notion to be swapped for any other UI/storage without touching core code.

## Quick Start

### Prerequisites

- Python 3.14+
- Docker & Docker Compose (optional, for containerized deployment)
- Notion account (for Notion integration)

### Installation

1. **Clone the repository**

```bash
git clone <repository-url>
cd budget-notion
```

2. **Create virtual environment**

```bash
python3.14 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Configure environment**

```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Run the CLI**

```bash
python -m src.interfaces.cli.main --help
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Repository Configuration
REPOSITORY_TYPE=sqlite  # or "notion"

# Notion Configuration (if using Notion)
NOTION_TOKEN=your_notion_integration_token
NOTION_DATABASE_ID=your_notion_database_id

# SQLite Configuration
SQLITE_DB_PATH=data/transactions.db

# Application Settings
DEFAULT_CATEGORY=Uncategorized
LOG_LEVEL=INFO
ENVIRONMENT=development
```

### Notion Setup

1. **Create a Notion Integration**
   - Go to [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations)
   - Click "New integration"
   - Give it a name (e.g., "Budget Notion")
   - Copy the "Internal Integration Token"

2. **Create Transactions Database**
   - See [docs/NOTION_SCHEMA.md](docs/NOTION_SCHEMA.md) for detailed schema
   - Create a database with these properties:
     - **Description** (Title)
     - **Date** (Date)
     - **Amount** (Number, $ format)
     - **Category** (Select)
     - **Account** (Select)
     - **Notes** (Text)
     - **Reviewed** (Checkbox)
     - **Transaction ID** (Text)
     - **AI Confidence** (Number, 0-100)

3. **Share Database with Integration**
   - Click "..." on your database
   - Click "Add connections"
   - Select your integration

4. **Get Database ID**
   - From database URL: `https://notion.so/<database_id>?v=...`
   - Copy the `<database_id>` part
   - Add to `.env` as `NOTION_DATABASE_ID`

## Usage

### CLI Commands

#### Add a Transaction

```bash
python -m src.interfaces.cli.main add \
  --date 2026-01-15 \
  --description "Starbucks Coffee" \
  --amount -5.75 \
  --category "Food & Dining" \
  --account "Checking"
```

#### Import CSV

```bash
python -m src.interfaces.cli.main import-csv \
  path/to/statement.csv \
  --bank ing \
  --category "Uncategorized" \
  --account "Checking"
```

**Supported Banks:**
- `ing` - ING Bank (Netherlands)
- `rabobank` - Rabobank (Netherlands)
- `abn_amro` - ABN AMRO (Netherlands)
- `generic_us` - Generic US format
- `generic_uk` - Generic UK format

#### List Transactions

```bash
# List recent transactions
python -m src.interfaces.cli.main list-transactions --limit 20

# Filter by category
python -m src.interfaces.cli.main list-transactions --category "Food & Dining"

# Filter by account
python -m src.interfaces.cli.main list-transactions --account "Checking"
```

#### Show Statistics

```bash
python -m src.interfaces.cli.main stats
```

#### View Configuration

```bash
python -m src.interfaces.cli.main config-info
```

## Docker Deployment

### Using Docker Compose (Recommended)

1. **Create secrets directory**

```bash
mkdir -p secrets
echo "your_notion_token" > secrets/notion_token.txt
echo "your_database_id" > secrets/notion_database_id.txt
echo "your_encryption_key" > secrets/encryption_key.txt
chmod 600 secrets/*.txt
```

2. **Build and run**

```bash
cd docker
docker-compose up -d
```

3. **Run commands**

```bash
# Add a transaction
docker-compose run app python -m src.interfaces.cli.main add \
  --description "Docker test" \
  --amount -10.00 \
  --category "Test"

# Import CSV
docker-compose run app python -m src.interfaces.cli.main import-csv \
  /app/uploads/statement.csv \
  --bank ing
```

### Building Docker Image

```bash
docker build -f docker/Dockerfile -t budget-notion:latest .
```

## Project Structure

```
budget-notion/
├── src/
│   ├── domain/                    # Core business logic
│   │   ├── entities/              # Transaction, Category, Budget
│   │   └── repositories/          # Repository interfaces (ABCs)
│   ├── application/               # Use cases
│   │   ├── use_cases/             # CreateTransaction, ImportCSV
│   │   └── dtos/                  # Data Transfer Objects
│   ├── infrastructure/            # External integrations
│   │   ├── repositories/          # Notion, SQLite implementations
│   │   └── parsers/               # CSV, PDF parsers
│   ├── interfaces/                # UI layer (CLI, API)
│   │   └── cli/                   # Click CLI
│   └── container.py               # Dependency injection
├── config/                        # Configuration
│   └── settings.py                # Settings management
├── tests/                         # Unit and integration tests
├── docker/                        # Docker configuration
│   ├── Dockerfile
│   └── docker-compose.yml
├── docs/                          # Documentation
├── data/                          # SQLite database (gitignored)
├── secrets/                       # Docker secrets (gitignored)
└── requirements.txt               # Python dependencies
```

## Development

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black src/ tests/
ruff check src/ tests/
```

### Type Checking

```bash
mypy src/
```

## Swapping UI Layers

The repository pattern makes it trivial to swap UIs:

### Current: Notion

```python
# container.py
transaction_repository = NotionTransactionRepository(client, database_id)
```

### Future: Custom Web App

```python
# container.py
transaction_repository = PostgreSQLRepository(connection_string)
```

### Future: Obsidian Plugin

```python
# container.py
transaction_repository = ObsidianRepository(vault_path)
```

**No changes needed** to use cases, domain entities, or business logic!

## Roadmap

### Phase 2: ML Categorization (Future)
- [ ] Integrate sentence-transformers for AI categorization
- [ ] Training data collection interface
- [ ] Confidence-based review workflow

### Phase 3: Advanced Features (Future)
- [ ] Budget tracking and alerts
- [ ] Spending analysis and reports
- [ ] Multi-currency support
- [ ] FastAPI REST API
- [ ] Streamlit web dashboard

### Phase 4: UI Alternatives (Future)
- [ ] Custom web app (React + FastAPI)
- [ ] Obsidian plugin
- [ ] Mobile app integration

## Security

- **Docker Secrets**: Use Docker Secrets for production (not environment variables)
- **Encryption**: File encryption for uploaded statements (optional)
- **PII Redaction**: Automatic redaction of sensitive data in logs
- **Non-root User**: Docker container runs as non-root user
- **No Hardcoded Secrets**: All secrets via environment or secrets files

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests for new features
4. Ensure code passes linting (`ruff`, `black`, `mypy`)
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details

## Acknowledgments

- Built with clean architecture principles
- Inspired by [Firefly III](https://www.firefly-iii.org) and [Actual Budget](https://actualbudget.org)
- Research sources cited in [docs/RESEARCH.md](docs/RESEARCH.md)

## Support

- **Issues**: [GitHub Issues](https://github.com/your-username/budget-notion/issues)
- **Documentation**: [docs/](docs/)
- **Notion Setup**: [docs/NOTION_SCHEMA.md](docs/NOTION_SCHEMA.md)
