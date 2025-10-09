# Configuration Guide

Complete guide to configuring the Congressional Hearing Database for your environment.

## Configuration Overview

The application uses environment variables for configuration, managed through a `.env` file. This allows different settings for development, production, and testing environments without changing code.

## Environment File Setup

### Creating Your Configuration

```bash
# Copy example configuration
cp .env.example .env

# Edit with your settings
nano .env  # Or use any text editor
```

### .env File Format

```bash
# Comments start with #
# No spaces around = sign
# No quotes needed (they're treated as part of the value)

CONGRESS_API_KEY=your_api_key_here
DATABASE_PATH=database.db
```

---

## Configuration Variables Reference

### API Configuration

#### CONGRESS_API_KEY (Required for updates)
- **Description**: Your Congress.gov API key
- **Required**: Yes (for data updates), No (for browsing)
- **Default**: None
- **Get Key**: [api.congress.gov/sign-up](https://api.congress.gov/sign-up/)

```bash
CONGRESS_API_KEY=abcd1234efgh5678ijkl9012
```

**Rate Limits:**
- Free tier: 5,000 requests/hour
- Each hearing detail fetch = 1 request
- Daily 7-day update typically uses 200-500 requests

#### API_KEY (Fallback)
- **Description**: Alternative name for Congress API key (Vercel compatibility)
- **Required**: No (CONGRESS_API_KEY takes precedence)
- **Default**: None

```bash
API_KEY=abcd1234efgh5678ijkl9012
```

#### CONGRESS_API_BASE_URL
- **Description**: Base URL for Congress.gov API
- **Required**: No
- **Default**: `https://api.congress.gov/v3`

```bash
CONGRESS_API_BASE_URL=https://api.congress.gov/v3
```

**When to change:** Only if Congress.gov changes their API endpoint (rare).

---

### Database Configuration

#### DATABASE_PATH
- **Description**: Path to SQLite database file
- **Required**: No
- **Default**: `database.db`

```bash
# Relative path (from project root)
DATABASE_PATH=database.db

# Absolute path
DATABASE_PATH=/var/www/Hearing-Database/data/database.db

# Vercel deployment
DATABASE_PATH=/var/task/database.db
```

**Considerations:**
- Use absolute paths for production
- Ensure directory exists and is writable
- Vercel uses `/var/task/` directory

---

### Import/Update Configuration

#### TARGET_CONGRESS
- **Description**: Default Congress number to track
- **Required**: No
- **Default**: `119`
- **Values**: Any Congress number (e.g., 117, 118, 119)

```bash
TARGET_CONGRESS=119
```

**Current Congress:** 119th Congress (2025-2027)

#### BATCH_SIZE
- **Description**: Number of records to process per batch during imports
- **Required**: No
- **Default**: `50`
- **Range**: 10-100

```bash
BATCH_SIZE=50
```

**Tuning:**
- **Lower (10-25)**: Slower but more stable, better for limited memory
- **Higher (75-100)**: Faster but uses more memory
- **Default (50)**: Balanced for most systems

#### UPDATE_WINDOW_DAYS
- **Description**: Default lookback window for incremental updates (days)
- **Required**: No
- **Default**: `30`
- **Range**: 1-90

```bash
UPDATE_WINDOW_DAYS=30
```

**Recommendations:**
- **Daily updates**: 7 days
- **Weekly updates**: 30 days
- **Monthly updates**: 90 days

#### VALIDATION_MODE
- **Description**: Run imports in validation mode (no database writes)
- **Required**: No
- **Default**: `False`
- **Values**: `True`, `False`

```bash
VALIDATION_MODE=False
```

**When to use:** Testing API connectivity or data structure without modifying database.

---

### Logging Configuration

#### LOG_LEVEL
- **Description**: Logging verbosity level
- **Required**: No
- **Default**: `INFO`
- **Values**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

```bash
LOG_LEVEL=INFO
```

**Levels explained:**
- **DEBUG**: Detailed diagnostic information (verbose)
- **INFO**: General informational messages (recommended)
- **WARNING**: Warning messages for non-critical issues
- **ERROR**: Error messages only
- **CRITICAL**: Critical errors only

#### LOG_FILE
- **Description**: Path to log file
- **Required**: No
- **Default**: `logs/import.log`

```bash
LOG_FILE=logs/import.log
```

**Considerations:**
- Ensure `logs/` directory exists
- Log files can grow large (consider rotation)
- Use absolute paths for production

---

### Rate Limiting Configuration

#### RATE_LIMIT
- **Description**: Maximum API requests per hour
- **Required**: No
- **Default**: `5000`

```bash
RATE_LIMIT=5000
```

**Congress.gov Limits:**
- Free tier: 5,000 requests/hour
- Setting higher than actual limit will cause errors

#### REQUEST_TIMEOUT
- **Description**: Timeout for API requests (seconds)
- **Required**: No
- **Default**: `30`

```bash
REQUEST_TIMEOUT=30
```

**Tuning:**
- Slow network: Increase to 60
- Fast network: Can reduce to 15
- Production: Keep at 30 (safe default)

---

## Environment-Specific Configurations

### Development Environment

```bash
# .env (development)
CONGRESS_API_KEY=your_dev_key_here
DATABASE_PATH=data/dev_database.db
LOG_LEVEL=DEBUG
VALIDATION_MODE=False
TARGET_CONGRESS=119
BATCH_SIZE=25
```

**Characteristics:**
- DEBUG logging for detailed output
- Smaller batch size for faster iteration
- Separate dev database

### Production Environment

```bash
# .env (production)
CONGRESS_API_KEY=your_prod_key_here
DATABASE_PATH=/var/www/Hearing-Database/database.db
LOG_LEVEL=INFO
TARGET_CONGRESS=119
BATCH_SIZE=50
UPDATE_WINDOW_DAYS=7
```

**Characteristics:**
- INFO logging (less verbose)
- Optimized batch size
- Absolute database path
- Conservative update window

### Testing Environment

```bash
# .env.test
CONGRESS_API_KEY=test_key_placeholder
DATABASE_PATH=:memory:
LOG_LEVEL=WARNING
VALIDATION_MODE=True
BATCH_SIZE=10
```

**Characteristics:**
- In-memory database (fast, temporary)
- Minimal logging
- Validation mode (no writes)
- Small batches for fast tests

### Vercel Deployment

```bash
# Configured in Vercel Dashboard → Environment Variables
CONGRESS_API_KEY=your_prod_key
API_KEY=your_prod_key  # Fallback
DATABASE_PATH=/var/task/database.db
TARGET_CONGRESS=119
UPDATE_WINDOW_DAYS=30
LOG_LEVEL=INFO
VERCEL=1  # Auto-set by Vercel
```

**Important:**
- Set for Production, Preview, and Development environments
- `VERCEL=1` triggers special configuration in code
- Database path uses `/var/task/` (Vercel specific)

---

## Configuration Management

### Using Multiple Environments

**Method 1: Multiple .env files**
```bash
# Development
cp .env.example .env.dev
nano .env.dev

# Production
cp .env.example .env.prod
nano .env.prod

# Load specific environment
export $(cat .env.dev | xargs)  # Load dev config
python cli.py web serve
```

**Method 2: Environment-specific files**
```bash
# Load development config
python -m dotenv -f .env.dev run python cli.py web serve

# Or export before running
export $(cat .env.prod | grep -v '^#' | xargs)
python cli.py web serve
```

### Precedence Order

Configuration values are loaded in this order (later overrides earlier):

1. Default values (in `config/settings.py`)
2. `.env` file
3. Environment variables
4. Command-line arguments (highest priority)

**Example:**
```bash
# .env file
LOG_LEVEL=INFO

# Override with environment variable
LOG_LEVEL=DEBUG python cli.py web serve

# Command-line argument overrides all
python cli.py web serve --verbose  # Forces DEBUG
```

---

## Security Best Practices

### Protect API Keys

```bash
# NEVER commit .env to Git
git add .gitignore
# Ensure .env is in .gitignore

# Verify .env is ignored
git status  # Should not show .env

# Check if accidentally committed
git log --all --full-history -- .env
```

### File Permissions

```bash
# Restrict .env file access
chmod 600 .env

# Owner can read/write, no one else can access
ls -l .env
# Should show: -rw------- 1 user group ... .env
```

### Rotate API Keys

```bash
# Periodically rotate keys
# 1. Generate new key at api.congress.gov
# 2. Update .env file
# 3. Test configuration
# 4. Revoke old key

# Test new key
python cli.py update incremental --lookback-days 1 --dry-run
```

### Separate Keys by Environment

```bash
# Development key (for testing)
CONGRESS_API_KEY_DEV=dev_key_here

# Production key (for live data)
CONGRESS_API_KEY_PROD=prod_key_here

# Use appropriate key per environment
```

---

## Validation & Testing

### Verify Configuration

```bash
# Check configuration
python cli.py --config-check

# Output shows:
# ✓ API key configured
# ✓ API connectivity: OK
# ✓ Database path: /path/to/database.db
# ✓ Configuration check passed
```

### Test API Connectivity

```bash
# Test with curl
curl -H "X-API-Key: YOUR_KEY" \
  https://api.congress.gov/v3/committee/119/house?limit=1

# Should return JSON with committee data
```

### Check Database Configuration

```bash
# Verify database exists and is accessible
python cli.py database status

# Check database path
python -c "from config.settings import settings; print(settings.database_path)"
```

---

## Troubleshooting Configuration

### "API_KEY not configured"

**Problem:** Application can't find API key

**Solutions:**
1. Check `.env` file exists: `ls -la .env`
2. Verify variable name: `CONGRESS_API_KEY` (not `API_KEY` alone)
3. No quotes around value: `CONGRESS_API_KEY=abc123` (not `="abc123"`)
4. No spaces: `KEY=value` (not `KEY = value`)

### "Database not found"

**Problem:** Can't locate database file

**Solutions:**
1. Check `DATABASE_PATH` in `.env`
2. Use absolute path in production
3. Verify directory exists: `ls -ld $(dirname $DATABASE_PATH)`
4. Check permissions: `ls -l database.db`

### Configuration Not Loading

**Problem:** Changes to `.env` not taking effect

**Solutions:**
1. Restart the application (`.env` loaded at startup)
2. Check for syntax errors in `.env`
3. Verify no duplicate variable definitions
4. Check environment variables: `printenv | grep CONGRESS`

### Rate Limit Exceeded

**Problem:** "429 Too Many Requests" from API

**Solutions:**
1. Check `RATE_LIMIT` setting
2. Reduce `BATCH_SIZE` to slow down requests
3. Increase `UPDATE_WINDOW_DAYS` to reduce frequency
4. Wait for rate limit reset (hourly)

---

## Advanced Configuration

### Custom Configuration Module

For advanced users who need programmatic configuration:

```python
# config/custom_settings.py
from config.settings import Settings

class CustomSettings(Settings):
    def __init__(self):
        super().__init__()
        # Custom configuration logic
        if self.is_production():
            self.batch_size = 100
        else:
            self.batch_size = 25

    def is_production(self):
        import os
        return os.environ.get('VERCEL') or os.environ.get('PRODUCTION')

# Use custom settings
settings = CustomSettings()
```

### Database Connection Pooling

For high-traffic deployments:

```python
# config/settings.py modifications
class Settings(BaseSettings):
    database_pool_size: int = Field(default=5, env='DATABASE_POOL_SIZE')
    database_max_overflow: int = Field(default=10, env='DATABASE_MAX_OVERFLOW')
```

---

## Configuration Reference Table

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CONGRESS_API_KEY` | Yes* | None | Congress.gov API key |
| `DATABASE_PATH` | No | `database.db` | SQLite database file path |
| `TARGET_CONGRESS` | No | `119` | Congress number to track |
| `BATCH_SIZE` | No | `50` | Import batch size |
| `UPDATE_WINDOW_DAYS` | No | `30` | Update lookback window |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |
| `LOG_FILE` | No | `logs/import.log` | Log file path |
| `RATE_LIMIT` | No | `5000` | API requests per hour |
| `REQUEST_TIMEOUT` | No | `30` | API request timeout (seconds) |

*Required for data updates, optional for browsing

---

## Next Steps

- **[Installation Guide](installation.md)** - Set up the application
- **[Quick Start](quick-start.md)** - Get running quickly
- **[Deployment Guide](../deployment/DEPLOYMENT.md)** - Deploy to production
- **[Update Protocols](../guides/operations/UPDATE_PROTOCOLS.md)** - Configure updates

---

[← Back: Installation](installation.md) | [Up: Documentation Hub](../README.md) | [Next: User Guide →](../guides/user/USER_GUIDE.md)
