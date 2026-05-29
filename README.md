# SEO Monitoring Agent for atozappliancesrepair.com

A Python-based SEO agent that monitors your website's search engine health for the Dubai market. Tracks keyword rankings, backlinks, technical SEO, and local SEO signals with automated reporting.

## 🎯 Features

- **Keyword Ranking Tracking**: Monitor positions for Dubai-specific appliance repair keywords
- **Backlink Analysis**: Track domain authority, referring domains, and backlink quality
- **Technical SEO Audit**: Check Core Web Vitals, mobile responsiveness, SSL, sitemaps, page speed
- **Local SEO Monitoring**: Track Google Business Profile, NAP consistency, local citations, reviews
- **Historical Data**: Store and analyze SEO metrics over time with SQLite database
- **Automated Reports**: Generate detailed reports and email them automatically
- **Mock Data Support**: Works without API keys for testing (uses demo data)

## 🚀 Quick Start

### 1. Installation

```bash
# Clone or navigate to the project directory
cd seo_agent

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your API keys
```

### 2. Basic Usage

```bash
# Run full SEO audit
python seo_agent.py audit

# View historical data
python seo_agent.py history 30
```

### 3. API Configuration (Optional)

The agent works with or without API keys:

**Without API Keys**: Uses mock data for demonstration
**With API Keys**: Connects to real data from:
- Google Search Console (keyword rankings)
- Ahrefs (backlinks, domain authority)
- Semrush (competitive analysis)
- Google PageSpeed Insights (Core Web Vitals)
- Google Business API (local SEO)

## 📊 What Gets Tracked

### Keyword Rankings
- Position for each keyword in Dubai search results
- Search impressions and click-through rates (CTR)
- Traffic trends over time

### Backlink Profile
- Total backlinks and referring domains
- Domain Authority (DA) and Page Authority (PA)
- Quality and relevance of backlinks
- Toxic link detection

### Technical SEO
- ✅ Core Web Vitals (LCP, FID, CLS)
- ✅ Mobile responsiveness
- ✅ SSL/HTTPS implementation
- ✅ XML sitemap presence
- ✅ robots.txt configuration
- ✅ Page load speed
- ✅ Crawlability and indexability

### Local SEO (Dubai)
- Google Business Profile status and ratings
- NAP (Name, Address, Phone) consistency
- Local business directory citations
- Review count and sentiment
- Dubai-specific keyword optimization

## 📁 Database Schema

SQLite database (`seo_agent.db`) with tables:
- **keyword_rankings**: Keyword positions, impressions, clicks, CTR
- **backlinks**: Domain authority, link quality, link types
- **technical_seo**: Technical metrics and audit results
- **local_seo**: Local SEO signals (GBP, NAP, citations)
- **domain_authority**: Overall domain metrics over time

## 📧 Automated Email Reports

To enable email reporting:

1. Update `.env` with SMTP credentials:
   ```
   SMTP_SERVER=smtp.gmail.com
   EMAIL_FROM=your_email@gmail.com
   EMAIL_PASSWORD=your_app_password  # Use Gmail app password
   REPORT_EMAIL=recipient@example.com
   ```

2. Set `send_email=True` in code:
   ```python
   agent.run_full_audit(save_report=True, send_email=True)
   ```

## 🔧 Customization

### Change Target Keywords

Edit `seo_agent.py`:
```python
CONFIG["keywords"] = [
    "appliance repair dubai",
    "ac repair dubai",
    "washing machine repair dubai",
    # Add your keywords here
]
```

### Change Target Location

```python
CONFIG["location"] = "Dubai"  # Change to your city
```

### Scheduling Automated Audits

Use a task scheduler:

**Windows (Task Scheduler)**:
```batch
# Schedule daily at 8 AM
schtasks /create /tn "SEO-Agent-Daily" /tr "python seo_agent.py audit" /sc daily /st 08:00
```

**Linux/Mac (cron)**:
```bash
# Edit crontab
crontab -e

# Add: Daily at 8 AM
0 8 * * * cd /path/to/seo_agent && python seo_agent.py audit
```

**Docker (Recommended)**:
Create a Docker container for repeatable scheduling.

## 📈 Sample Output

```
🚀 Starting SEO Agent Audit...
   Target: atozappliancesrepair.com (Dubai)
   Time: 2026-05-29 19:08

📊 Tracking keyword rankings...
   ✅ Tracked 8 keywords

🔗 Analyzing backlinks...
   ✅ Found 245 backlinks

🔧 Running technical SEO audit...
   ✅ Technical audit complete

📍 Checking local SEO signals...
   ✅ Local SEO audit complete

📄 Generating report...
   ✅ Report saved: seo_report_20260529_190800.txt
```

## 🛠️ Integration with APIs

### Google Search Console
```python
# Note: Requires OAuth2 authentication
# Generates: keyword rankings, impressions, CTR
from google.oauth2.service_account import Credentials
```

### Ahrefs API
```python
# Documentation: https://ahrefs.com/api
# Generates: backlinks, domain authority, referring domains
```

### Semrush API
```python
# Documentation: https://www.semrush.com/api
# Generates: competitor analysis, keyword research
```

## 📊 Report Structure

Generated reports include:

1. **Executive Summary**: Key metrics at a glance
2. **Keyword Rankings**: Position trends and traffic
3. **Backlink Profile**: Authority and quality metrics
4. **Technical SEO**: Health score and issues
5. **Local SEO**: Dubai market presence
6. **Recommendations**: Actionable improvement steps

## 🐛 Troubleshooting

**Issue**: "No GSC API key - using mock data"
**Solution**: Set `GSC_KEY` in `.env` or skip if testing

**Issue**: "Error fetching rankings"
**Solution**: Check API credentials and rate limits

**Issue**: "SSL verification failed"
**Solution**: May need to configure proxy or certificates

## 📚 Next Steps

1. ✅ Set up `.env` with API keys
2. ✅ Run `python seo_agent.py audit` to test
3. ✅ Review the generated report
4. ✅ Set up automated scheduling
5. ✅ Integrate with monitoring dashboard

## 📝 License

Built for atozappliancesrepair.com SEO monitoring.

## 🤝 Support

For issues or enhancements:
- Check API documentation for each service
- Verify `.env` configuration
- Review database schema for data structure
- Test with mock data first before API integration
