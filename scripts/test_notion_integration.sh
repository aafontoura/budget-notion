#!/bin/bash
# Test Notion integration end-to-end

set -e

echo "============================================================"
echo "Budget Notion - Integration Test"
echo "============================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
PASSED=0
FAILED=0

# Helper function
test_command() {
    local description=$1
    shift
    echo -n "Testing: $description... "

    if "$@" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASSED${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}"
        ((FAILED++))
        return 1
    fi
}

echo "1. Configuration Check"
echo "------------------------"
python -m src.interfaces.cli.main config-info
echo ""

echo "2. Add Transaction Test"
echo "------------------------"
TRANSACTION_OUTPUT=$(python -m src.interfaces.cli.main add \
    --description "Integration Test Transaction" \
    --amount -25.99 \
    --category "Test" \
    --notes "Automated integration test" 2>&1)

if echo "$TRANSACTION_OUTPUT" | grep -q "Transaction created successfully"; then
    echo -e "${GREEN}✓ Add transaction: PASSED${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ Add transaction: FAILED${NC}"
    echo "$TRANSACTION_OUTPUT"
    ((FAILED++))
fi
echo ""

echo "3. List Transactions Test"
echo "------------------------"
LIST_OUTPUT=$(python -m src.interfaces.cli.main list-transactions --limit 5 2>&1)

if echo "$LIST_OUTPUT" | grep -q "Recent Transactions"; then
    echo -e "${GREEN}✓ List transactions: PASSED${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ List transactions: FAILED${NC}"
    echo "$LIST_OUTPUT"
    ((FAILED++))
fi
echo ""

echo "4. Add Multiple Transactions"
echo "------------------------"
for i in {1..3}; do
    python -m src.interfaces.cli.main add \
        --description "Test Transaction $i" \
        --amount -$((RANDOM % 100)).99 \
        --category "Test" \
        > /dev/null 2>&1
    echo "  ✓ Transaction $i created"
done
echo ""

echo "5. Filter by Category Test"
echo "------------------------"
FILTER_OUTPUT=$(python -m src.interfaces.cli.main list-transactions --category "Test" --limit 10 2>&1)

if echo "$FILTER_OUTPUT" | grep -q "Test"; then
    echo -e "${GREEN}✓ Filter by category: PASSED${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ Filter by category: FAILED${NC}"
    echo "$FILTER_OUTPUT"
    ((FAILED++))
fi
echo ""

echo "============================================================"
echo "Test Summary"
echo "============================================================"
echo -e "${GREEN}Passed: $PASSED${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Failed: $FAILED${NC}"
else
    echo -e "${GREEN}Failed: $FAILED${NC}"
fi
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed! Your Notion integration is working perfectly!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed. Check the output above for details.${NC}"
    exit 1
fi
