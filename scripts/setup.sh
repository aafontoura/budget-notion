#!/bin/bash
# Setup script for Budget Notion

set -e

echo "======================================"
echo "Budget Notion - Setup Script"
echo "======================================"
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.14"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Error: Python 3.14+ required. Found: $python_version"
    echo "Please install Python 3.14 or higher."
    exit 1
fi
echo "✓ Python version: $python_version"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
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
