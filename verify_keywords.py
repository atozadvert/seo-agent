#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('seo_guardian.db')
c = conn.cursor()

# Check if table exists
c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='all_keywords_history'")
exists = c.fetchone()[0]
print(f"✓ all_keywords_history table exists: {exists == 1}")

if exists:
    c.execute("SELECT COUNT(*) FROM all_keywords_history")
    count = c.fetchone()[0]
    print(f"✓ Total rows in all_keywords_history: {count:,}")
    
    c.execute("SELECT site, date, keyword, clicks, impressions FROM all_keywords_history LIMIT 3")
    sample = c.fetchall()
    print(f"\nSample rows:")
    for row in sample:
        print(f"  {row}")
else:
    print("✗ Table does not exist yet")

conn.close()
