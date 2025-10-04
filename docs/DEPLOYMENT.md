# Congressional Hearing Database - Deployment Guide

Complete guide for deploying the Congressional Hearing Database to production.

## Deployment Options

### 1. Vercel (Recommended)

**Best For**: Serverless deployment with automated updates

**Pros**:
- Free tier available
- Automatic HTTPS
- Built-in cron jobs for daily updates
- Git-based deployments
- Zero-config Python support

**Cons**:
- SQLite read-only limitations in serverless
- 10-second function timeout
- Cold start latency

### 2. Traditional VPS/Cloud

**Best For**: Self-hosting with full control

**Pros**:
- Full SQLite write support
- No function timeouts
- Complete control over resources
- Can run background tasks

**Cons**:
- Manual server management
- Security updates required
- Higher cost for equivalent scale

### 3. Docker Container

**Best For**: Containerized deployments

**Pros**:
- Portable across platforms
- Consistent environment
- Easy scaling
- Works with Kubernetes

**Cons**:
- Requires container orchestration
- More complex setup

## Vercel Deployment

### Prerequisites

1. **GitHub Account** - Code hosted on GitHub
2. **Vercel Account** - Sign up at vercel.com
3. **Congress.gov API Key** - Get from api.congress.gov

### Initial Setup

#### 1. Prepare Repository

Ensure these files exist in your repo:

```
Hearing-Database/
├── vercel.json           # Vercel configuration
├── api/
│   ├── index.py          # Main web app entrypoint
│   └── cron-update.py    # Daily update cron job
├── requirements.txt      # Python dependencies
├── database.db          # Pre-populated database
└── .env.example         # Environment variable template
```

#### 2. Connect to Vercel

1. Go to https://vercel.com
2. Click "New Project"
3. Import your GitHub repository
4. Vercel auto-detects Python project

#### 3. Configure Build Settings

**Framework Preset**: Other
**Build Command**: (leave empty)
**Output Directory**: (leave empty)
**Install Command**: `pip install -r requirements.txt`

#### 4. Set Environment Variables

In Vercel dashboard → Project Settings → Environment Variables:

```
CONGRESS_API_KEY=your_api_key_here
API_KEY=your_api_key_here          # Fallback
DATABASE_PATH=/var/task/database.db
TARGET_CONGRESS=119
UPDATE_WINDOW_DAYS=30
LOG_LEVEL=INFO
```

**Important**: Set for "Production", "Preview", and "Development" environments

#### 5. Deploy

Click "Deploy" - Vercel will:
1. Install dependencies
2. Deploy the application
3. Set up cron jobs automatically
4. Provide a URL (e.g., `your-project.vercel.app`)

### Vercel Configuration

#### vercel.json

```json
{
  "version": 2,
  "builds": [
    {
      "src": "api/index.py",
      "use": "@vercel/python"
    },
    {
      "src": "api/cron-update.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/api/cron/daily-update",
      "dest": "api/cron-update.py"
    },
    {
      "src": "/(.*)",
      "dest": "api/index.py"
    }
  ],
  "crons": [
    {
      "path": "/api/cron/daily-update",
      "schedule": "0 6 * * *"
    }
  ]
}
```

### Database Handling on Vercel

**Challenge**: Vercel's serverless functions have read-only filesystem

**Solution**:
1. Deploy database with application
2. Write updates to temporary storage
3. Database updates happen via cron job
4. Consider external database for heavy writes

**Current Approach**:
- Database included in deployment
- Daily cron updates write temporarily
- Works for read-heavy workload

**Future Consideration**:
- Migrate to PostgreSQL or MySQL for frequent writes
- Use Vercel's storage integrations
- External database service (PlanetScale, Supabase)

### Monitoring Vercel Deployment

#### Check Deployment Status

```bash
# Install Vercel CLI
npm install -g vercel

# Login
vercel login

# Check deployments
vercel ls

# View logs
vercel logs your-project.vercel.app
```

#### Monitor Cron Jobs

- Vercel Dashboard → Project → Cron Jobs
- View execution logs
- Check success/failure status
- Review execution times

#### Health Checks

- Visit `/api/stats` - Should return database statistics
- Visit `/api/update-status` - Shows last update info
- Visit `/api/debug` - System diagnostics

### Troubleshooting Vercel

**Issue**: Database not found

**Solution**:
```python
# In config/settings.py
if os.environ.get('VERCEL'):
    self.database_path = '/var/task/database.db'
```

**Issue**: Import errors

**Solution**: Ensure all dependencies in `requirements.txt`

**Issue**: Cron job not running

**Solution**: Check `vercel.json` cron configuration matches endpoint

**Issue**: Function timeout

**Solution**: Reduce batch size in update operations

## VPS/Cloud Deployment

### Digital Ocean / Linode / AWS EC2

#### 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.8+
sudo apt install python3 python3-pip python3-venv -y

# Install Git
sudo apt install git -y

# Install Nginx (optional, for reverse proxy)
sudo apt install nginx -y
```

#### 2. Deploy Application

```bash
# Clone repository
cd /var/www
git clone <your-repo-url> Hearing-Database
cd Hearing-Database

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp .env.example .env
nano .env  # Add your API key
```

#### 3. Configure as System Service

Create `/etc/systemd/system/hearing-database.service`:

```ini
[Unit]
Description=Congressional Hearing Database
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/Hearing-Database
Environment="PATH=/var/www/Hearing-Database/venv/bin"
ExecStart=/var/www/Hearing-Database/venv/bin/python cli.py web serve --host 0.0.0.0 --port 5000

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable hearing-database
sudo systemctl start hearing-database

# Check status
sudo systemctl status hearing-database
```

#### 4. Configure Nginx Reverse Proxy

Create `/etc/nginx/sites-available/hearing-database`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Optional: Serve static files directly
    location /static {
        alias /var/www/Hearing-Database/web/static;
        expires 30d;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/hearing-database /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 5. Setup SSL with Let's Encrypt

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Obtain certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal is configured automatically
```

#### 6. Configure Automated Updates

```bash
# Edit crontab
crontab -e

# Add daily update at 2 AM
0 2 * * * cd /var/www/Hearing-Database && /var/www/Hearing-Database/venv/bin/python cli.py update incremental --quiet >> /var/log/hearing-db-updates.log 2>&1
```

### Docker Deployment

#### Dockerfile

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create data directory
RUN mkdir -p data logs

# Expose port
EXPOSE 5000

# Run application
CMD ["python", "cli.py", "web", "serve", "--host", "0.0.0.0", "--port", "5000"]
```

#### docker-compose.yml

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "5000:5000"
    environment:
      - CONGRESS_API_KEY=${CONGRESS_API_KEY}
      - DATABASE_PATH=/app/database.db
      - TARGET_CONGRESS=119
    volumes:
      - ./database.db:/app/database.db
      - ./logs:/app/logs
    restart: unless-stopped

  updater:
    build: .
    command: >
      sh -c "while true; do
        python cli.py update incremental --quiet &&
        sleep 86400;
      done"
    environment:
      - CONGRESS_API_KEY=${CONGRESS_API_KEY}
      - DATABASE_PATH=/app/database.db
    volumes:
      - ./database.db:/app/database.db
      - ./logs:/app/logs
    restart: unless-stopped
```

#### Build and Run

```bash
# Create .env file
echo "CONGRESS_API_KEY=your_key_here" > .env

# Build and start
docker-compose up -d

# View logs
docker-compose logs -f web

# Stop
docker-compose down
```

## Environment Variables Reference

### Required

- `CONGRESS_API_KEY` - Your Congress.gov API key (required for updates)

### Optional

- `DATABASE_PATH` - Database file location (default: `database.db`)
- `TARGET_CONGRESS` - Congress number to track (default: `119`)
- `BATCH_SIZE` - Import batch size (default: `50`)
- `UPDATE_WINDOW_DAYS` - Daily update lookback (default: `30`)
- `LOG_LEVEL` - Logging verbosity: DEBUG, INFO, WARNING, ERROR (default: `INFO`)
- `LOG_FILE` - Log file path (default: `logs/import.log`)

### Vercel-Specific

- `VERCEL` - Auto-set by Vercel (triggers special config)
- `API_KEY` - Fallback for `CONGRESS_API_KEY`

## Database Management

### Initial Database Setup

```bash
# Option 1: Initialize empty database
python cli.py database init

# Option 2: Import full dataset
python cli.py import full --congress 119

# Option 3: Use pre-populated database
# Download from releases or use existing database.db
```

### Database Backups

```bash
# Manual backup
cp database.db database.backup.$(date +%Y%m%d).db

# Automated daily backups (cron)
0 3 * * * cp /var/www/Hearing-Database/database.db /var/www/Hearing-Database/backups/db-$(date +\%Y\%m\%d).db

# Keep last 7 days
0 4 * * * find /var/www/Hearing-Database/backups -name "db-*.db" -mtime +7 -delete
```

### Database Migrations

For schema changes:

```bash
# Backup first
cp database.db database.pre-migration.db

# Apply migration
sqlite3 database.db < migrations/001_add_column.sql

# Verify
python cli.py analysis audit
```

## Performance Optimization

### For Vercel

1. **Reduce Cold Starts**: Keep functions warm with monitoring pings
2. **Optimize Database**: Keep database size < 50MB
3. **Cache Static Assets**: Use Vercel's CDN
4. **Minimize Dependencies**: Remove unused packages

### For VPS

1. **Enable SQLite WAL Mode**: Better concurrency
   ```bash
   sqlite3 database.db "PRAGMA journal_mode=WAL;"
   ```

2. **Add Database Indexes**: Optimize common queries
   ```sql
   CREATE INDEX idx_hearings_date ON hearings(hearing_date_only);
   CREATE INDEX idx_hearings_chamber ON hearings(chamber);
   ```

3. **Configure Nginx Caching**:
   ```nginx
   location /static {
       expires 1y;
       add_header Cache-Control "public, immutable";
   }
   ```

4. **Use Gunicorn**: Production WSGI server
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 'web.app:app'
   ```

## Monitoring & Alerts

### Basic Monitoring

```bash
# Check application status
curl http://localhost:5000/api/stats

# Check update status
curl http://localhost:5000/api/update-status

# Monitor logs
tail -f logs/import.log
```

### Advanced Monitoring

#### UptimeRobot (Free)

1. Create monitor for your deployment URL
2. Set check interval (5 minutes)
3. Configure email/SMS alerts
4. Monitor `/api/stats` endpoint

#### Custom Health Check Script

```bash
#!/bin/bash
# health-check.sh

STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/api/stats)

if [ $STATUS -ne 200 ]; then
    echo "Health check failed: HTTP $STATUS"
    # Send alert (email, Slack, etc.)
    exit 1
fi

echo "Health check passed"
exit 0
```

## Security Considerations

### API Key Protection

- **Never commit** `.env` file to Git
- Use environment variables in production
- Rotate keys periodically
- Monitor API usage

### Database Security

- **Restrict file permissions**:
  ```bash
  chmod 600 database.db
  ```
- **Regular backups**: Protect against data loss
- **No sensitive data**: Database contains only public information

### Application Security

- **Keep dependencies updated**:
  ```bash
  pip list --outdated
  pip install -U package-name
  ```
- **Use HTTPS**: Always (Let's Encrypt is free)
- **Rate limiting**: Consider for public APIs
- **Input validation**: Already implemented in parsers

## Scaling Considerations

### When to Scale

- Database size > 500MB
- Response times > 2 seconds
- > 1000 daily active users
- Heavy concurrent usage

### Scaling Options

1. **Migrate to PostgreSQL**: Better for concurrent writes
2. **Add Caching Layer**: Redis for frequent queries
3. **CDN for Static Assets**: CloudFlare, Fastly
4. **Load Balancer**: Multiple app instances
5. **Read Replicas**: Separate read/write databases

## Troubleshooting

### Common Issues

**Issue**: Import/update fails
- Check API key validity
- Verify internet connectivity
- Review logs in `logs/import.log`
- Check API rate limits

**Issue**: Web app won't start
- Verify all dependencies installed
- Check port availability
- Review Flask errors in logs
- Ensure database file exists

**Issue**: Slow queries
- Add database indexes
- Enable WAL mode
- Optimize query patterns
- Consider caching

**Issue**: Disk space issues
- Rotate log files
- Clean old backups
- Vacuum database: `sqlite3 database.db "VACUUM;"`

## Support

- **Documentation**: Check other guides in `docs/`
- **GitHub Issues**: Report deployment problems
- **Logs**: Always check logs first
- **API Debug**: Use `/api/debug` endpoint

---

**Deployment Checklist**:

- [ ] Environment variables configured
- [ ] Database initialized or uploaded
- [ ] Cron jobs scheduled (if applicable)
- [ ] HTTPS enabled
- [ ] Backups configured
- [ ] Monitoring setup
- [ ] Health checks working
- [ ] Documentation updated with your URL

Happy deploying!
