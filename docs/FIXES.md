# Bug Fixes and Python Version Updates

## Summary of Changes

### 1. Python Version Constraint (3.12-3.13)

**Issue**: Python 3.14 is not yet fully supported by all dependencies, particularly `dependency-injector`.

**Changes Made**:
- ✅ Updated [pyproject.toml](../pyproject.toml): `requires-python = ">=3.12,<3.14"`
- ✅ Updated [docker/Dockerfile](../docker/Dockerfile): `FROM python:3.13-slim`
- ✅ Updated [scripts/setup.sh](../scripts/setup.sh): Version check for 3.12-3.13
- ✅ Updated [README.md](../README.md): Documentation reflects 3.12-3.13
- ✅ Updated [requirements.txt](../requirements.txt): `dependency-injector==4.43.0`

**Recommended Python Versions**:
- ✅ Python 3.12.x (stable, tested)
- ✅ Python 3.13.x (stable, tested)
- ❌ Python 3.14+ (not yet supported)

### 2. Notion Repository JSON Serialization Error

**Issue**:
```
ERROR - Unexpected error while adding transaction: Object of type method is not JSON serializable
```

**Root Cause**:
The dependency-injector was passing method references (`config.provided.get_notion_token`) instead of calling them. The Notion Client tried to serialize the method object, which failed.

**Fix Applied** ([src/container.py](../src/container.py)):

```python
# BEFORE (broken):
notion_client = providers.Singleton(
    Client,
    auth=config.provided.get_notion_token,  # ❌ Method reference
)

# AFTER (fixed):
notion_client = providers.Singleton(
    Client,
    auth=config.provided.get_notion_token.call(),  # ✅ Method call
)
```

Same fix applied to `database_id`:
```python
# BEFORE:
database_id=config.provided.get_notion_database_id,

# AFTER:
database_id=config.provided.get_notion_database_id.call(),
```

**Why This Works**:
- `.call()` tells dependency-injector to **invoke** the method and use the return value
- Without `.call()`, it passes the method object itself
- The Notion Client expects a string, not a callable

### 3. Setup Script Python Detection

**Issue**: Original script assumed `python3.14` command exists.

**Fix Applied** ([scripts/setup.sh](../scripts/setup.sh)):
- Uses `PYTHON_BIN` environment variable (defaults to `python3`)
- Validates Python version is >= 3.12 and < 3.14
- Provides helpful error messages with installation suggestions
- Works with Homebrew Python installations (`python@3.12`, `python@3.13`)

**Usage**:
```bash
# Use default python3
./scripts/setup.sh

# Use specific version
PYTHON_BIN=python3.13 ./scripts/setup.sh
```

## Verification

### Test the Fix

```bash
# 1. Make sure you have Python 3.12 or 3.13
python3 --version

# 2. Recreate virtual environment with correct Python
rm -rf venv
python3 -m venv venv
source venv/bin/activate

# 3. Reinstall dependencies
pip install -r requirements.txt

# 4. Test Notion integration
python -m src.interfaces.cli.main add \
  --description "Test transaction" \
  --amount -10.00 \
  --category "Test"

# Expected: ✓ Transaction created successfully!
```

### Expected Behavior

**Before Fix**:
```
ERROR - Unexpected error while adding transaction: Object of type method is not JSON serializable
✗ Error: Failed to add transaction: Object of type method is not JSON serializable
```

**After Fix**:
```
INFO - Created transaction in Notion: abc123...
✓ Transaction created successfully!
  ID: 550e8400-e29b-41d4-a716-446655440000
  Date: 2026-01-16
  Description: Test transaction
  Amount: $-10.00
  Category: Test
```

## Dependencies Updated

### requirements.txt Changes

```diff
- dependency-injector==4.41.0
+ dependency-injector==4.43.0
```

**Reason**: Version 4.43.0 has better Python 3.12/3.13 support.

## Python Version Compatibility Matrix

| Python Version | Status | Notes |
|---------------|--------|-------|
| 3.11 | ❌ Not supported | Too old |
| 3.12 | ✅ Fully supported | **Recommended** |
| 3.13 | ✅ Fully supported | **Recommended** |
| 3.14+ | ❌ Not supported | Dependencies not ready yet |

## Testing Checklist

After applying these fixes, verify:

- [ ] `python3 --version` shows 3.12.x or 3.13.x
- [ ] `pip install -r requirements.txt` succeeds without errors
- [ ] `python -m src.interfaces.cli.main config-info` shows correct config
- [ ] SQLite mode works: `REPOSITORY_TYPE=sqlite python -m src.interfaces.cli.main add ...`
- [ ] Notion mode works: `REPOSITORY_TYPE=notion python -m src.interfaces.cli.main add ...`
- [ ] CSV import works: `python -m src.interfaces.cli.main import-csv statement.csv`
- [ ] Docker build succeeds: `docker build -f docker/Dockerfile .`

## Additional Notes

### Why Not Python 3.14?

Python 3.14 was released very recently (January 2026) and many popular packages haven't updated yet:
- `dependency-injector` - No 3.14 wheels available
- Some native extensions need recompilation
- Better to use stable 3.12/3.13 for production

### Migration Path to 3.14+

When dependencies support 3.14:

1. Update `pyproject.toml`:
   ```toml
   requires-python = ">=3.12,<3.15"
   ```

2. Update `Dockerfile`:
   ```dockerfile
   FROM python:3.14-slim
   ```

3. Test all functionality
4. Update documentation

## Rollback Instructions

If you need to rollback to original version:

```bash
git checkout HEAD -- src/container.py
git checkout HEAD -- pyproject.toml
git checkout HEAD -- docker/Dockerfile
git checkout HEAD -- requirements.txt
pip install -r requirements.txt
```

## Related Files

All files affected by these fixes:
- [src/container.py](../src/container.py) - Fixed method calls
- [pyproject.toml](../pyproject.toml) - Python version constraint
- [requirements.txt](../requirements.txt) - Updated dependency-injector
- [docker/Dockerfile](../docker/Dockerfile) - Python 3.13 base image
- [scripts/setup.sh](../scripts/setup.sh) - Smart Python detection
- [README.md](../README.md) - Updated documentation

## Support

If you still encounter issues:

1. **Check Python version**: `python3 --version`
2. **Verify dependencies**: `pip list | grep dependency-injector`
3. **Check logs**: Run with `--log-level DEBUG`
4. **Test SQLite first**: Rule out Notion API issues
5. **Check .env file**: Verify credentials are correct

### 3. Notion Property Name Issue

**Issue**:
```
ERROR - Notion API error while adding transaction: Description is not a property that exists.
```

**Root Cause**:
Notion databases automatically create a "Name" property as the title property. The code expects "Description" but Notion uses "Name" by default.

**Fix**: Rename the "Name" property to "Description" in Notion

**Steps to Fix**:
1. Open your Transactions database in Notion
2. Click on the "Name" property header
3. Click "Edit property"
4. Rename from "Name" to "Description"
5. Click outside to save

**Alternative**: If you prefer to keep "Name", you would need to update the code to use "Name" instead of "Description" in all property mappings.

**Verification**:
```bash
# This should now work:
python -m src.interfaces.cli.main add \
  --description 'Coffee' \
  --amount -5.00 \
  --category 'Food & Dining'

# Expected output:
# ✓ Transaction created successfully!
```

## Testing

### Integration Test Script

Run the comprehensive integration test:

```bash
./scripts/test_notion_integration.sh
```

This will:
- Check configuration
- Add test transactions
- List transactions
- Filter by category
- Verify all operations work

### Manual Testing

```bash
# 1. Add a transaction
python -m src.interfaces.cli.main add \
  --description "Lunch" \
  --amount -12.50 \
  --category "Food & Dining"

# 2. List recent transactions
python -m src.interfaces.cli.main list-transactions --limit 10

# 3. Filter by category
python -m src.interfaces.cli.main list-transactions --category "Food & Dining"

# 4. Check Notion database - transaction should appear!
```

### 4. Notion Client Version Incompatibility

**Issue**:
```
ERROR - 'DatabasesEndpoint' object has no attribute 'query'
✗ Error: 'NoneType' object has no attribute 'get'
```

**Root Cause**:
- notion-client 2.7.0 removed the `databases.query()` method (replaced with `data_sources.query()`)
- Properties returned from Notion API could be None, causing AttributeError when accessing nested fields

**Fix Applied**:

1. **Downgraded notion-client**: 2.7.0 → 2.2.1
   - Version 2.2.1 has the stable `databases.query()` API
   - File: [requirements.txt](../requirements.txt)

2. **Added defensive property extraction**:
   - Check if properties exist before accessing
   - Validate property types (dict, list, etc.)
   - Handle None values gracefully
   - File: [src/infrastructure/repositories/notion_repository.py](../src/infrastructure/repositories/notion_repository.py)

**Changes Required**:
```bash
# Reinstall with correct version
pip install notion-client==2.2.1 --force-reinstall
```

**Verification**:
```bash
# Run integration test
./scripts/test_notion_integration.sh

# Expected output:
# 🎉 All tests passed! Your Notion integration is working perfectly!
```

## Conclusion

✅ **All issues resolved**:
- Notion integration now works correctly
- Python 3.12-3.13 fully supported
- Setup script handles version detection
- Docker uses compatible Python version
- notion-client downgraded to stable version (2.2.1)
- Defensive property extraction prevents crashes
- Property name issue documented
- All integration tests passing

**Ready to use!** 🚀
