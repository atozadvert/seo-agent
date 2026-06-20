#!/usr/bin/env python3
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('seo_guardian.db')
c = conn.cursor()

# Check recent daily_stats entries
c.execute("""
SELECT site, date, total_keywords, suspicious_count, total_clicks
FROM daily_stats
ORDER BY date DESC, site
LIMIT 10
""")

results = c.fetchall()
print(f"Recent daily_stats entries:")
for row in results:
    print(f"  {row}")

# Check if any all_keywords_history data exists
c.execute("SELECT COUNT(*) FROM all_keywords_history")
count = c.fetchone()[0]
print(f"\nall_keywords_history rows: {count}")

conn.close()
