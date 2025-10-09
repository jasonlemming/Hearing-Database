# Troubleshooting Guide

Common issues and solutions for the Congressional Hearing Database.

## Installation Issues

### Database Connection Errors

**Problem**: `sqlite3.OperationalError: unable to open database file`

**Solutions**:
1. Verify database file exists: `ls -la database.db`
2. Check file permissions: `chmod 644 database.db`
3. Ensure you're in the correct directory: `pwd`
4. Try absolute path in DATABASE_PATH environment variable

### API Key Issues

**Problem**: `401 Unauthorized` or API rate limit errors

**Solutions**:
1. Verify API key is correct in `.env` file
2. Check key hasn't expired at https://api.congress.gov
3. Verify `.env` is in project root directory
4. Check rate limits: max 5,000 requests/hour

### Import/Update Failures

**Problem**: Import or update commands fail with errors

**Solutions**:
1. Check API connectivity: `curl https://api.congress.gov/v3/`
2. Verify database is initialized: `python cli.py database init`
3. Run with verbose logging: `python cli.py import full --verbose`
4. Check update logs: `SELECT * FROM update_logs ORDER BY start_time DESC LIMIT 5;`

## Web Interface Issues

### Server Won't Start

**Problem**: `Address already in use` error

**Solutions**:
1. Check if another process is using port 5000: `lsof -i :5000`
2. Kill existing process: `kill -9 <PID>`
3. Use different port: `python cli.py web serve --port 8080`

### Pages Not Loading

**Problem**: 404 errors or blank pages

**Solutions**:
1. Verify database exists and has data: Check `/api/stats`
2. Clear browser cache
3. Check console for JavaScript errors (F12)
4. Verify static files are accessible

### Search Not Working

**Problem**: Search returns no results

**Solutions**:
1. Check if data exists for the search criteria
2. Verify hearings table has data: `SELECT COUNT(*) FROM hearings;`
3. Try simpler search terms
4. Check for special characters in search query

## Data Quality Issues

### Missing Video Embeds

**Problem**: "Video Available" shown but no player

**Solutions**:
1. Check video_type is set: `SELECT video_type FROM hearings WHERE video_url IS NOT NULL;`
2. If NULL, update based on URL pattern (see video-integration.md)
3. Verify URL is accessible

### Missing Witness Information

**Problem**: Hearings show no witnesses

**Solutions**:
1. Check if witnesses were fetched: `SELECT COUNT(*) FROM witness_appearances;`
2. Some hearings don't have witness lists published yet
3. Run enhancement: `python cli.py enhance witnesses --hearing-id <ID>`

### Outdated Data

**Problem**: Recent hearings not appearing

**Solutions**:
1. Check last update: Visit `/api/update-status`
2. Run manual update: `python cli.py update incremental`
3. Verify cron job is running (production)
4. Check update logs for errors

## Deployment Issues

### Vercel Deployment Fails

**Problem**: Build or deployment errors on Vercel

**Solutions**:
1. Check build logs in Vercel dashboard
2. Verify all dependencies in requirements.txt
3. Ensure database.db is included in deployment
4. Check environment variables are set in Vercel

### Cron Job Not Running

**Problem**: Daily updates not happening

**Solutions**:
1. Verify cron schedule in vercel.json
2. Check Vercel cron logs
3. Ensure /api/cron endpoint exists and works
4. Test manually: Visit `/api/cron?key=<CRON_SECRET>`

## Performance Issues

### Slow Page Loads

**Problem**: Pages take a long time to load

**Solutions**:
1. Check database size: `ls -lh database.db`
2. Verify indexes exist: See database-schema.md
3. Use pagination for large result sets
4. Check server resources (RAM, CPU)

### High Memory Usage

**Problem**: Application consuming too much memory

**Solutions**:
1. Reduce batch size in imports: `BATCH_SIZE=25`
2. Use incremental updates instead of full imports
3. Close database connections properly
4. Restart application periodically

## Getting More Help

Still having issues? Here's how to get help:

1. **Check logs**: Look for error messages in terminal output
2. **Review documentation**: See [Documentation Hub](../README.md)
3. **Database diagnostics**: Run `python cli.py analysis audit`
4. **System info**: Visit `/api/debug` to see system configuration
5. **GitHub Issues**: [Report bugs or ask questions](https://github.com/your-org/Hearing-Database/issues)

When reporting issues, include:
- Error messages (full stack trace)
- System information (`python --version`, OS)
- Steps to reproduce
- Relevant logs from update_logs or import_errors tables

---

**Last Updated**: October 9, 2025
**Status**: Living document - updated as new issues are discovered

[← Back: Documentation Hub](../README.md) | [Up: Troubleshooting](./) | [Next: Debugging Guide →](debugging.md)
