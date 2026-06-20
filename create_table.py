#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('seo_guardian.db')
c = conn.cursor()

# Create the all_keywords_history table
c.execute('''CREATE TABLE IF NOT EXISTS all_keywords_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site TEXT NOT NULL,
    date TEXT NOT NULL,
    keyword TEXT NOT NULL,
    clicks INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    position REAL,
    ctr REAL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(site, date, keyword))''')

conn.commit()
conn.close()

print("✓ all_keywords_history table created successfully")
