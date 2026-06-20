#!/usr/bin/env python3
"""
Demo: Populate all_keywords_history with sample data from GSC
"""
import sqlite3
import json
import base64
import os
from datetime import timedelta
from datetime import datetime
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2 import service_account

load_dotenv()

# Setup
conn = sqlite3.connect('seo_guardian.db')
db = conn.cursor()
today = datetime.now()
end_date = (today - timedelta(days=2)).strftime('%Y-%m-%d')  # Yesterday (GSC has 1-2 day lag)
start_date = (today - timedelta(days=8)).strftime('%Y-%m-%d')  # 7 days ago

service_account_b64 = os.getenv("GSC_SERVICE_ACCOUNT_JSON", "").strip()
service_account_info = json.loads(service_account_b64)
creds = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
)
service = build("webmasters", "v3", credentials=creds)

# Get first 3 sites and fetch keywords
response = service.sites().list().execute()
sites = [s['siteUrl'] for s in response.get('siteEntry', [])[:3]]  # Demo: first 3 sites

total_inserted = 0
for site_url in sites:
    print(f"Fetching keywords from {site_url} ({start_date} to {end_date})...")
    try:
        result = service.searchanalytics().query(
            siteUrl=site_url,
                body={
                    'startDate': start_date,
                    'endDate': end_date,
                    'dimensions': ['query', 'date'],
                    'rowLimit': 1000,
            }
        ).execute()
        
        rows = result.get('rows', [])
        print(f"  Found {len(rows)} keywords")

        inserted = 0
        for row in rows:
            keyword = row['keys'][0]
            date = row['keys'][1]
            clicks = row.get('clicks', 0)
            impressions = row.get('impressions', 0)
            position = row.get('position', 0)
            ctr = row.get('ctr', 0) * 100

            try:
                db.execute('''INSERT OR REPLACE INTO all_keywords_history
                    (site, date, keyword, clicks, impressions, position, ctr)
                    VALUES (?,?,?,?,?,?,?)''',
                    (site_url, date, keyword, clicks, impressions, position, ctr))
                inserted += 1
            except Exception as e:
                pass

        conn.commit()
        print(f"  ✓ Inserted {inserted} keywords")
        total_inserted += inserted

    except Exception as e:
        print(f"  ✗ Error: {e}")

conn.close()
print(f"\n✓ Total inserted: {total_inserted} keywords")
print("Ready! Run: streamlit run dashboard.py")
print("Then go to 🧾 All Keywords page to search/filter/download")
