#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('seo_guardian.db')
c = conn.cursor()

# List all tables
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = c.fetchall()
print(f"Tables in database: {[t[0] for t in tables]}")

# Check if any data exists
for table in tables:
    table_name = table[0]
    c.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = c.fetchone()[0]
    print(f"  {table_name}: {count} rows")

conn.close()
