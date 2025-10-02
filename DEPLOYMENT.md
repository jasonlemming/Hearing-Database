# 🚀 Congressional Hearings Database - Deployment Guide

## Overview
This Flask web application provides a searchable database of Congressional hearings, committees, members, and witnesses. Built with modular blueprints and ready for cloud deployment.

## Live Deployment Options

### Option 1: Vercel (Recommended for Flask)

#### 1. Prerequisites
- GitHub account
- Vercel account (free tier available)
- Domain name (optional, Vercel provides subdomain)

#### 2. GitHub Setup
```bash
# Initialize git if not already done
cd Congressional-meetings-api-claude-experiment
git init
git add .
git commit -m "Initial deployment setup"

# Push to GitHub
git remote add origin https://github.com/yourusername/congressional-hearings-db.git
git branch -M main
git push -u origin main
```

#### 3. Vercel Deployment
1. Visit [vercel.com](https://vercel.com) and sign in with GitHub
2. Click "New Project" and import your GitHub repository
3. Vercel will auto-detect the Flask app using `vercel.json`
4. Add environment variables in Vercel dashboard:
   - `CONGRESS_API_KEY`: Your Congress.gov API key
   - `DATABASE_PATH`: `/tmp/congressional_hearings.db`
   - `FLASK_ENV`: `production`
5. Deploy with one click!

#### 4. Custom Domain Setup
1. In Vercel dashboard, go to your project → Settings → Domains
2. Add your custom domain
3. Configure DNS records as instructed by Vercel
4. SSL certificate is automatically provided

### Option 2: Railway (Alternative)

#### 1. Install Railway CLI
```bash
npm install -g @railway/cli
railway login
```

#### 2. Deploy
```bash
cd Congressional-meetings-api-claude-experiment
railway init
railway up
```

### Option 3: PythonAnywhere (Budget Option)

#### 1. Upload code to PythonAnywhere
```bash
# Zip your project (excluding venv)
zip -r congressional-hearings.zip . -x "venv/*" "__pycache__/*"
```

#### 2. Configure web app
- Create new web app with Flask
- Upload and extract zip
- Set WSGI configuration to point to `web/app.py`

## Database Configuration

### Development vs Production
- **Development**: Uses `data/congressional_hearings.db` (local SQLite)
- **Production**: Uses included `database.db` (2MB with sample data)

### Database Updates
For periodic data updates in production:
1. Run import scripts locally
2. Copy updated database to `database.db`
3. Redeploy to Vercel

## Environment Variables

### Required
- `CONGRESS_API_KEY`: Get from [Congress.gov API](https://api.congress.gov/)

### Optional
- `DATABASE_PATH`: Override default database location
- `FLASK_ENV`: Set to `production` for live sites

## Project Structure for Deployment

```
congressional-hearings-db/
├── api/
│   └── index.py          # Vercel entry point
├── web/
│   ├── app.py            # Main Flask application
│   ├── blueprints/       # Modular route organization
│   └── templates/        # Jinja2 templates
├── database/             # Database management
├── config/               # Configuration files
├── database.db           # Production database (2MB)
├── vercel.json          # Vercel configuration
├── requirements.txt     # Python dependencies
└── README.md
```

## Performance Considerations

### Database
- SQLite is suitable for read-heavy workloads (< 100k records)
- Consider PostgreSQL for larger datasets
- Database is pre-populated with Congressional data

### Caching
- Static assets cached via CDN
- Database queries cached at application level
- Consider Redis for high-traffic sites

### Scaling
- Vercel: Automatic scaling, 100GB bandwidth free tier
- Railway: $5/month for hobby tier
- Consider database hosting separately for high-traffic

## Monitoring and Maintenance

### Built-in Features
- Import status tracking via `/api/witness-import-status`
- Error handling and logging
- Database statistics at `/api/stats`

### Recommended Monitoring
- Vercel Analytics (free)
- Uptime monitoring (UptimeRobot)
- Database backup strategy

## Security Considerations

### Environment Variables
- Never commit API keys to Git
- Use Vercel/Railway environment variable management
- Rotate API keys periodically

### Database
- SQLite file included for deployment convenience
- Consider encryption for sensitive data
- Regular security updates

## Cost Estimates

### Free Tier Options
- **Vercel**: Free for personal projects (100GB bandwidth)
- **Railway**: $5/month after free trial
- **PythonAnywhere**: $5/month beginner plan

### Custom Domain
- Domain registration: $10-15/year
- SSL: Free with all hosting options

## Troubleshooting

### Common Issues

1. **Import errors**: Check Python path configuration
2. **Database not found**: Verify `database.db` exists in project root
3. **Static files 404**: Ensure Flask static folder configuration
4. **API key issues**: Check environment variable names

### Debug Mode
```bash
# Local testing
export FLASK_ENV=development
export FLASK_DEBUG=1
python web/app.py
```

## Next Steps After Deployment

1. **Custom Domain**: Configure your domain DNS
2. **Analytics**: Set up traffic monitoring
3. **Database Updates**: Schedule periodic data imports
4. **Performance**: Monitor and optimize query performance
5. **Features**: Add user authentication, favorites, alerts

## Support

- Check GitHub Issues for common problems
- Vercel Documentation: [vercel.com/docs](https://vercel.com/docs)
- Flask Documentation: [flask.palletsprojects.com](https://flask.palletsprojects.com)

---

Your Congressional Hearings Database is now ready for the world! 🎉