# Quick Start Guide

Get the Congressional Hearing Database running in 5 minutes.

## Prerequisites

- **Python 3.9+** installed
- **Git** for cloning the repository
- **Congress.gov API Key** ([Get one here](https://api.congress.gov/sign-up/))

## Step 1: Clone and Setup (2 minutes)

```bash
# Clone the repository
git clone https://github.com/your-org/Hearing-Database.git
cd Hearing-Database

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Configure (1 minute)

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your API key
API_KEY=your_congress_gov_api_key_here
```

That's it! The database is already included (`database.db`).

## Step 3: Start the Web Server (30 seconds)

```bash
# Start the Flask application
python cli.py web serve --port 5001

# Or run directly
python web/app.py
```

Open your browser to **http://localhost:5001**

## 🎉 You're Done!

You should now see the Congressional Hearing Database web interface with:
- Browse 1,168+ hearings from the 119th Congress
- Search by title, committee, date, or chamber
- View hearing details with videos, witnesses, and documents
- Explore committees and their hearing history

---

## Quick Commands Reference

```bash
# View database statistics
python cli.py database status

# Update with latest hearings (7-day lookback)
python cli.py update incremental --lookback-days 7

# Search for specific hearings
# Use the web interface at http://localhost:5001/hearings

# Stop the server
# Press Ctrl+C in the terminal
```

---

## What's Included?

The `database.db` file contains:
- **1,168+ hearings** from 119th Congress
- **213 committees** (House, Senate, Joint)
- **Witnesses** and their testimony appearances
- **Documents**: Transcripts, witness statements, supporting materials
- **Video links** to YouTube/Congress.gov videos

---

## Next Steps

### For End Users
- **[User Guide](../guides/user/USER_GUIDE.md)** - Learn all web interface features
- **[Browse Hearings](http://localhost:5001/hearings)** - Start exploring data

### For Developers
- **[Installation Guide](installation.md)** - Detailed setup and configuration
- **[Development Guide](../guides/developer/DEVELOPMENT.md)** - Architecture and workflows
- **[CLI Guide](../guides/developer/CLI_GUIDE.md)** - Command-line tools

### For Operators
- **[Update Protocols](../guides/operations/UPDATE_PROTOCOLS.md)** - Keep data current
- **[Admin Dashboard](../features/admin-dashboard.md)** - Monitor updates at `/admin`
- **[Deployment Guide](../deployment/DEPLOYMENT.md)** - Deploy to production

---

## Troubleshooting

### "Module not found" errors
```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### "Database not found" error
```bash
# Check database file exists
ls -lh database.db

# If missing, initialize new database
python cli.py database init
python cli.py import full --congress 119
```

### Port 5001 already in use
```bash
# Use a different port
python cli.py web serve --port 8080
```

### "API_KEY not configured" error
```bash
# Edit .env file and add your API key
nano .env  # or use any text editor
API_KEY=your_actual_key_here
```

---

## Need Help?

- **[Troubleshooting Guide](../troubleshooting/common-issues.md)** - Common problems and solutions
- **[Full Documentation](../README.md)** - Complete documentation hub
- **[GitHub Issues](https://github.com/your-org/Hearing-Database/issues)** - Report bugs or request features

---

[← Back to Documentation Hub](../README.md) | [Next: Installation Guide →](installation.md)
