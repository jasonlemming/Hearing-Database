# Installation Guide

Complete installation guide for the Congressional Hearing Database.

## Prerequisites

### Required Software

- **Python 3.9 or higher** - [Download Python](https://www.python.org/downloads/)
- **Git** - [Download Git](https://git-scm.com/downloads)
- **pip** - Python package installer (included with Python 3.9+)

### Required API Key

- **Congress.gov API Key** - [Sign up here](https://api.congress.gov/sign-up/)
  - Free tier: 5,000 requests per hour
  - Required for data updates (not required for browsing existing database)

### Optional Tools

- **SQLite Browser** - [DB Browser for SQLite](https://sqlitebrowser.org/) (for database inspection)
- **VSCode** or preferred code editor
- **Postman** or **curl** - For testing API endpoints

---

## Installation Methods

Choose your installation method based on your use case:

### Method 1: Quick Install (Recommended for Users)

Fastest way to get up and running for browsing and exploring data.

```bash
# Clone repository
git clone https://github.com/your-org/Hearing-Database.git
cd Hearing-Database

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure API key (optional for browsing)
cp .env.example .env
nano .env  # Add your API key if you plan to update data

# Start web server
python cli.py web serve --port 5001
```

**Done!** Open http://localhost:5001 in your browser.

### Method 2: Development Install

For developers who want to contribute or modify the code.

```bash
# Clone with all branches
git clone https://github.com/your-org/Hearing-Database.git
cd Hearing-Database
git fetch --all

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies (including dev tools)
pip install -r requirements.txt
pip install pytest black flake8  # Dev dependencies

# Configure environment
cp .env.example .env
nano .env  # Add API key and configure settings

# Initialize database (if starting fresh)
python cli.py database init

# Run tests
pytest

# Start development server
python cli.py web serve --debug --port 5001
```

### Method 3: Docker Install

For containerized deployment.

```bash
# Clone repository
git clone https://github.com/your-org/Hearing-Database.git
cd Hearing-Database

# Create .env file
cp .env.example .env
nano .env  # Add your API key

# Build and run with docker-compose
docker-compose up -d

# Check logs
docker-compose logs -f web
```

---

## Detailed Installation Steps

### Step 1: Clone the Repository

```bash
# Via HTTPS
git clone https://github.com/your-org/Hearing-Database.git

# Or via SSH (if you have SSH keys configured)
git clone git@github.com:your-org/Hearing-Database.git

# Navigate to directory
cd Hearing-Database
```

### Step 2: Set Up Python Virtual Environment

**Why a virtual environment?**
- Isolates project dependencies
- Prevents conflicts with system Python packages
- Makes deployment easier

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
```

**Verify activation:**
```bash
which python  # Should show path to venv/bin/python
python --version  # Should be 3.9+
```

### Step 3: Install Dependencies

```bash
# Upgrade pip first
pip install --upgrade pip

# Install project dependencies
pip install -r requirements.txt
```

**Dependencies installed:**
- `flask>=3.0.0` - Web framework
- `requests>=2.31.0` - HTTP library for API calls
- `pydantic>=2.0.0` - Data validation
- `python-dotenv>=1.0.0` - Environment variable management
- `click>=8.1.0` - CLI framework
- `pyyaml>=6.0` - YAML parsing
- `pytest>=7.4.0` - Testing framework (optional)
- `black>=23.0.0` - Code formatter (optional)

### Step 4: Configure Environment Variables

```bash
# Copy example configuration
cp .env.example .env

# Edit configuration file
nano .env  # Or use any text editor
```

**Required configuration:**
```bash
# Congress.gov API Configuration
CONGRESS_API_KEY=your_api_key_here

# Optional Configuration
DATABASE_PATH=database.db
TARGET_CONGRESS=119
LOG_LEVEL=INFO
```

See [Configuration Guide](configuration.md) for detailed explanations of all settings.

### Step 5: Verify Database

The repository includes a pre-populated database (`database.db`) with 1,168+ hearings from the 119th Congress.

```bash
# Check database exists
ls -lh database.db

# View database statistics
python cli.py database status
```

**Output should show:**
```
Database Status:
==================================================
hearings            :      1,168
committees          :        213
members             :      [count]
witnesses           :      [count]
...
```

### Step 6: Start the Application

```bash
# Start web server
python cli.py web serve --host 0.0.0.0 --port 5001

# Or use Flask directly
python web/app.py
```

**Output:**
```
 * Running on http://0.0.0.0:5001
 * Debug mode: off
```

### Step 7: Verify Installation

Open your browser to http://localhost:5001 and verify:

- ✅ Homepage loads
- ✅ Browse hearings page shows data
- ✅ Search functionality works
- ✅ Committee pages display
- ✅ No error messages in terminal

---

## Platform-Specific Instructions

### macOS

**Install Python 3.9+:**
```bash
# Via Homebrew (recommended)
brew install python@3.9

# Or download from python.org
```

**Common Issues:**
- **"python: command not found"** - Use `python3` instead of `python`
- **SSL certificate errors** - Run: `/Applications/Python\ 3.9/Install\ Certificates.command`

### Windows

**Install Python:**
1. Download from [python.org](https://www.python.org/downloads/)
2. **Important:** Check "Add Python to PATH" during installation
3. Restart command prompt after installation

**Use PowerShell or Git Bash:**
- Command Prompt has limitations
- PowerShell or Git Bash recommended

**Common Issues:**
- **"python: command not found"** - Ensure Python is in PATH
- **Virtual environment activation** - Use `venv\Scripts\activate` (not `source`)

### Linux (Ubuntu/Debian)

**Install Python:**
```bash
sudo apt update
sudo apt install python3.9 python3.9-venv python3-pip git -y
```

**For other distributions:**
- **CentOS/RHEL:** `sudo yum install python39 python39-pip git`
- **Fedora:** `sudo dnf install python3.9 python3-pip git`
- **Arch:** `sudo pacman -S python python-pip git`

---

## Database Options

### Option 1: Use Included Database (Recommended)

The repository includes a pre-populated database with 1,168+ hearings.

**Pros:**
- Instant access to data
- No API key required initially
- No waiting for import

**Cons:**
- Data may become outdated over time
- Need API key to update

### Option 2: Initialize Fresh Database

Start with an empty database and import fresh data.

```bash
# Initialize empty database
python cli.py database init

# Import 119th Congress data (takes 20-30 minutes)
python cli.py import full --congress 119

# Or import specific phase
python cli.py import full --phase hearings --congress 119
```

### Option 3: Download Latest Database

Check releases for the latest database snapshot:

```bash
# Download latest release
wget https://github.com/your-org/Hearing-Database/releases/download/vX.X.X/database.db

# Or use curl
curl -L -o database.db https://github.com/your-org/Hearing-Database/releases/download/vX.X.X/database.db
```

---

## Verification Checklist

After installation, verify everything works:

- [ ] Virtual environment activated
- [ ] Dependencies installed (`pip list` shows Flask, requests, etc.)
- [ ] `.env` file exists with API key (if needed)
- [ ] Database file exists (`database.db`)
- [ ] Database status command works
- [ ] Web server starts without errors
- [ ] Homepage loads in browser
- [ ] Can browse hearings
- [ ] Search functionality works

---

## Post-Installation

### Run Your First Update

```bash
# Test API connection and fetch recent updates
python cli.py update incremental --lookback-days 7

# View update history
python cli.py analysis recent --days 7
```

### Explore the Database

```bash
# View database statistics
python cli.py database status

# Run data quality audit
python cli.py analysis audit
```

### Access Admin Dashboard

Navigate to http://localhost:5001/admin to access real-time monitoring and update controls.

⚠️ **Note:** Admin dashboard has no authentication - use only on localhost for development.

---

## Troubleshooting

### "Module not found" Errors

**Problem:** ImportError or ModuleNotFoundError

**Solutions:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # Check prompt shows (venv)

# Reinstall dependencies
pip install -r requirements.txt

# Check pip is installing to venv
which pip  # Should show venv/bin/pip
```

### Database Not Found

**Problem:** "No such file or directory: database.db"

**Solutions:**
```bash
# Check if database exists
ls -lh database.db

# If missing, initialize new one
python cli.py database init

# Or download from releases
```

### API Key Issues

**Problem:** "API_KEY not configured" or authentication errors

**Solutions:**
```bash
# Verify .env file exists
cat .env

# Check API key format (no quotes needed)
CONGRESS_API_KEY=abcd1234efgh5678

# Test API connection
curl -H "X-API-Key: YOUR_KEY" https://api.congress.gov/v3/committee/119/house?limit=1
```

### Port Already in Use

**Problem:** "Address already in use" when starting server

**Solutions:**
```bash
# Use different port
python cli.py web serve --port 8080

# Or find and kill process using port 5001
lsof -ti:5001 | xargs kill -9  # macOS/Linux
netstat -ano | findstr :5001  # Windows
```

### Permission Errors

**Problem:** Permission denied errors on database file

**Solutions:**
```bash
# Fix database permissions
chmod 644 database.db

# Fix directory permissions
chmod 755 .
```

### SQLite Version Issues

**Problem:** "database disk image is malformed" or version errors

**Solutions:**
```bash
# Check SQLite version (need 3.8+)
sqlite3 --version

# Verify database integrity
sqlite3 database.db "PRAGMA integrity_check;"

# If corrupted, restore from backup or re-import
```

---

## Uninstallation

To completely remove the installation:

```bash
# Deactivate virtual environment
deactivate

# Remove project directory
cd ..
rm -rf Hearing-Database

# Remove global packages (if installed globally - not recommended)
pip uninstall flask requests pydantic python-dotenv click
```

---

## Next Steps

- **[Configuration Guide](configuration.md)** - Detailed configuration options
- **[Quick Start](quick-start.md)** - Get running in 5 minutes
- **[Development Guide](../guides/developer/DEVELOPMENT.md)** - For contributors
- **[User Guide](../guides/user/USER_GUIDE.md)** - Using the web interface

---

## Getting Help

- **Common Issues:** Check [Troubleshooting Guide](../troubleshooting/common-issues.md)
- **GitHub Issues:** [Report a bug](https://github.com/your-org/Hearing-Database/issues)
- **Documentation:** [Full documentation](../README.md)

---

[← Back to Documentation Hub](../README.md) | [Next: Configuration →](configuration.md)
