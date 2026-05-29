#!/usr/bin/env python3
"""
Quick Start Guide - SEO Monitoring Agent
For atozappliancesrepair.com Dubai SEO Tracking
"""

# ==================== QUICK START ====================

"""
1. INSTALLATION (First time only)
   python -m pip install --upgrade pip
   pip install -r requirements.txt

2. CONFIGURATION
   cp .env.example .env
   # Edit .env file with your API keys (optional - works without them)

3. RUN YOUR FIRST AUDIT
   python seo_agent.py audit

4. VIEW YOUR REPORT
   Look for: seo_report_YYYYMMDD_HHMMSS.txt
   This file contains your complete SEO health report

5. SET UP AUTOMATIC SCHEDULING (Optional)

   Windows (Task Scheduler):
   - Press Win+R, type: taskschd.msc
   - Create Basic Task → "SEO Agent Daily"
   - Trigger: Daily at 8:00 AM
   - Action: Run python with argument: "D:\Agents\Agent1\seo_agent.py" audit

   Linux/Mac (cron):
   crontab -e
   # Add this line:
   0 8 * * * cd /path/to/seo_agent && python seo_agent.py audit >> seo_agent.log 2>&1

6. ACCESSING YOUR DATA
   All historical data is stored in: seo_agent.db (SQLite)
   
   View past rankings:
   python seo_agent.py history 30  # Last 30 days

7. INTEGRATING WITH APIs (Optional)

   To get real data instead of mock data:
   
   A) Google Search Console
      - Go to: https://search.google.com/search-console
      - Claim your property
      - Generate OAuth credentials
      - Add GSC_KEY to .env
   
   B) Ahrefs API
      - Sign up: https://ahrefs.com
      - Get API key from settings
      - Add AHREFS_API_KEY to .env
   
   C) Google Business Profile
      - Claim your business: https://business.google.com
      - Enable Google Business API
      - Add GOOGLE_BUSINESS_API_KEY to .env
   
   D) Email Reports
      - Gmail: Use "App Password" (not regular password)
      - Settings: https://myaccount.google.com/apppasswords
      - Add to .env:
        EMAIL_FROM=your_email@gmail.com
        EMAIL_PASSWORD=your_app_password

8. CUSTOMIZING FOR YOUR BUSINESS

   Edit seo_agent.py:
   
   CONFIG = {
       "website": "atozappliancesrepair.com",      # Your domain
       "location": "Dubai",                         # Your city
       "keywords": [
           "appliance repair dubai",                # Add your keywords
           "ac repair dubai",
       ],
   }

9. INTERPRETING THE REPORT

   Key Metrics to Monitor:
   - Average Position: Target < #10 for main keywords
   - Click-Through Rate (CTR): Benchmark by search intent
   - Domain Authority (DA): Build to 30+ for better rankings
   - Local Signals: 4.7+ rating, 100+ reviews
   - Core Web Vitals: All "Good" status

10. TROUBLESHOOTING

    Q: "No GSC API key - using mock data"
    A: This is normal! Agent uses demo data when APIs aren't configured.
       Add real API keys to .env when ready.

    Q: Where's my database?
    A: seo_agent.db is created automatically on first run.

    Q: Can I email reports to my team?
    A: Yes! Configure SMTP settings in .env and set send_email=True

    Q: How often should I run audits?
    A: Daily or weekly. Set up scheduling (see step 5).

    Q: My domain has 0 backlinks/domain authority
    A: Using mock data. Add AHREFS_API_KEY to .env for real metrics.

11. NEXT STEPS

    ✅ Run your first audit: python seo_agent.py audit
    ✅ Review the generated report
    ✅ Set up daily scheduling
    ✅ Add API keys when ready
    ✅ Create action plan from recommendations
    ✅ Monitor trends week-over-week

12. EXAMPLE WORKFLOW

    # Day 1: Set it up
    $ cp .env.example .env
    $ python seo_agent.py audit
    # Opens: seo_report_20260529_191342.txt

    # Day 2: Check historical data
    $ python seo_agent.py history 1
    # Shows: Keywords Tracked: 4, Avg Data Points: 1.0

    # Week 1: Set up scheduling
    # Windows: Use Task Scheduler (see step 5)

    # Week 2: Add API keys
    # Edit .env with your real API credentials
    # Re-run: python seo_agent.py audit
    # Now gets REAL data!

    # Month 1: Analyze trends
    $ python seo_agent.py history 30
    # See: Improvement trends, keyword movements

13. FILES YOU HAVE

    seo_agent.py          → Main agent script
    requirements.txt      → Python dependencies
    .env.example          → Configuration template
    seo_agent.db          → Your data (auto-created)
    seo_report_*.txt      → Generated reports (auto-created)

---

Questions? Check README.md for detailed documentation.
Ready to boost your SEO? Run: python seo_agent.py audit
"""

if __name__ == "__main__":
    print(__doc__)
