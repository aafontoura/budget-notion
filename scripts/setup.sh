#!/bin/bash
# Setup script for Budget Notion

set -e

echo "======================================"
echo "Budget Notion - Setup Script"
echo "======================================"
echo ""

# Check Python version
echo "Checking Python version..."

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "❌ Error: '$PYTHON_BIN' not found on PATH."
  echo "Tip: install Python 3.12 or 3.13, or set PYTHON_BIN (e.g. PYTHON_BIN=python3.13)."
  exit 1
fi

python_version=$($PYTHON_BIN --version 2>&1 | awk '{print $2}')
required_min="3.12"
required_max_exclusive="3.14"

# Require: >= 3.12 and < 3.14
if [ "$(printf '%s\n' "$required_min" "$python_version" | sort -V | head -n1)" != "$required_min" ]; then
  echo "❌ Error: Python $required_min+ required. Found: $python_version"
  echo "Please install Python $required_min or $required_min.x (recommended: 3.12 or 3.13)."
  exit 1
fi

if [ "$(printf '%s\n' "$python_version" "$required_max_exclusive" | sort -V | head -n1)" = "$required_max_exclusive" ]; then
  echo "❌ Error: Python $python_version is too new for some native dependencies (requires < $required_max_exclusive)."
  echo "Please use Python 3.12 or 3.13 (e.g. via Homebrew: python@3.13 or python@3.12)."
  echo "You can also set PYTHON_BIN=python3.13 before running this script."
  exit 1
fi

echo "✓ Python version: $python_version ($PYTHON_BIN)"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    "$PYTHON_BIN" -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip --quiet
echo "✓ pip upgraded"
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt --quiet
echo "✓ Dependencies installed"
echo ""

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "⚠️  Please edit .env file and add your Notion credentials:"
    echo "   - NOTION_TOKEN"
    echo "   - NOTION_DATABASE_ID"
    echo ""
else
    echo "✓ .env file already exists"
    echo ""
fi

# Create data and uploads directories
echo "Creating data directories..."
mkdir -p data uploads
echo "✓ Directories created"
echo ""

# Create secrets directory for Docker
echo "Creating secrets directory..."
mkdir -p secrets
touch secrets/.gitkeep
echo "✓ Secrets directory created"
echo ""

echo "======================================"
echo "Setup Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Configure Notion:"
echo "   - Read docs/NOTION_SCHEMA.md for database setup"
echo "   - Add your credentials to .env file"
echo ""
echo "2. Try the CLI:"
echo "   source venv/bin/activate"
echo "   python -m src.interfaces.cli.main --help"
echo ""
echo "3. Add your first transaction:"
echo "   python -m src.interfaces.cli.main add \\"
echo "     --description 'Coffee' \\"
echo "     --amount -5.00 \\"
echo "     --category 'Food & Dining'"
echo ""
echo "4. Or use SQLite mode (no Notion required):"
echo "   # In .env: REPOSITORY_TYPE=sqlite"
echo "   python -m src.interfaces.cli.main add \\"
echo "     --description 'Test' \\"
echo "     --amount -10.00 \\"
echo "     --category 'Test'"
echo ""
echo "For more information, see README.md"
echo ""
