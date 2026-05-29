#!/usr/bin/env python3
"""
Fetch all search terms from Google Search Console
and flag any suspicious keywords
"""

import pickle
import json
from datetime import datetime, timedelta
from pathlib import Path
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SITE_URL = "https://atozappliancesrepair.com/"
TOKEN_FILE = "token.pickle"
DAYS = 30

# ── Suspicious keyword patterns ──────────────────────────────────
SUSPICIOUS_PATTERNS = [
    # Gambling / slot spam (CRITICAL for your site)
    "slot", "casino", "togel", "gacor", "toto", "jackpot", "poker",
    "betting", "judi", "maxwin", "depo", "wd", "bocoran",
    # Competitor brand hijacking
    "vs ", " or ", "alternative to", "instead of", "better than",
    # Negative / complaint intent
    "scam", "fraud", "fake", "cheat", "complaint", "bad", "worst",
    "not working", "rip off", "ripoff", "overcharged", "overcharge",
    # Other spam
    "porn", "sex", "drug", "bitcoin", "crypto", "hack",
    "free download", "crack", "keygen", "torrent",
    # Wrong business type
    "hiring", "job", "salary", "vacancy", "internship",
]

def get_credentials():
    if not Path(TOKEN_FILE).exists():
        print("❌ No token.pickle found. Run: python setup_google_auth.py")
        return None
    with open(TOKEN_FILE, 'rb') as f:
        creds = pickle.load(f)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds

def fetch_all_search_terms(service, days=30):
    """Fetch all search queries from GSC."""
    print(f"\n🔍 Fetching search terms for last {days} days...")
    
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    all_rows = []
    start_row = 0
    row_limit = 1000
    
    while True:
        result = service.searchanalytics().query(
            siteUrl=SITE_URL,
            body={
                'startDate': start_date,
                'endDate': end_date,
                'dimensions': ['query'],
                'rowLimit': row_limit,
                'startRow': start_row,
            }
        ).execute()
        
        rows = result.get('rows', [])
        if not rows:
            break
        
        all_rows.extend(rows)
        start_row += len(rows)
        
        if len(rows) < row_limit:
            break
    
    return all_rows

def analyze_keywords(rows):
    """Analyze keywords for suspicious patterns."""
    normal = []
    suspicious = []
    
    for row in rows:
        query = row['keys'][0].lower()
        clicks = row.get('clicks', 0)
        impressions = row.get('impressions', 0)
        position = round(row.get('position', 0), 1)
        ctr = round(row.get('ctr', 0) * 100, 2)
        
        entry = {
            'keyword': row['keys'][0],
            'clicks': clicks,
            'impressions': impressions,
            'position': position,
            'ctr': ctr,
        }
        
        matched = [p for p in SUSPICIOUS_PATTERNS if p in query]
        if matched:
            entry['reason'] = matched
            suspicious.append(entry)
        else:
            normal.append(entry)
    
    return normal, suspicious

def print_report(normal, suspicious):
    print("\n" + "="*65)
    print(f"  GSC SEARCH TERMS REPORT — {SITE_URL}")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*65)
    
    print(f"\n📊 SUMMARY")
    print(f"   Total Keywords: {len(normal) + len(suspicious)}")
    print(f"   ✅ Normal Keywords: {len(normal)}")
    print(f"   🚨 Suspicious Keywords: {len(suspicious)}")
    
    print(f"\n🏆 TOP 20 NORMAL KEYWORDS (by clicks)")
    print(f"   {'Keyword':<45} {'Pos':>5} {'Clicks':>7} {'CTR':>7}")
    print(f"   {'-'*45} {'-'*5} {'-'*7} {'-'*7}")
    for r in sorted(normal, key=lambda x: x['clicks'], reverse=True)[:20]:
        print(f"   {r['keyword']:<45} #{r['position']:>4} {r['clicks']:>7} {r['ctr']:>6}%")
    
    if suspicious:
        print(f"\n🚨 SUSPICIOUS KEYWORDS DETECTED ({len(suspicious)} found)")
        print(f"   {'Keyword':<45} {'Reason':<25} {'Clicks':>7}")
        print(f"   {'-'*45} {'-'*25} {'-'*7}")
        for r in sorted(suspicious, key=lambda x: x['clicks'], reverse=True):
            reason = ', '.join(r['reason'])[:24]
            print(f"   {r['keyword']:<45} {reason:<25} {r['clicks']:>7}")
    else:
        print(f"\n✅ No suspicious keywords found!")
    
    print("\n" + "="*65)
    
    # Save to file
    filename = f"search_terms_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"GSC Search Terms Report\n")
        f.write(f"Site: {SITE_URL}\n")
        f.write(f"Generated: {datetime.now()}\n\n")
        f.write(f"NORMAL KEYWORDS ({len(normal)}):\n")
        for r in sorted(normal, key=lambda x: x['clicks'], reverse=True):
            f.write(f"  {r['keyword']} | Pos #{r['position']} | {r['clicks']} clicks | {r['ctr']}% CTR\n")
        if suspicious:
            f.write(f"\nSUSPICIOUS KEYWORDS ({len(suspicious)}):\n")
            for r in suspicious:
                f.write(f"  {r['keyword']} | Reason: {r['reason']} | {r['clicks']} clicks\n")
    
    print(f"💾 Full report saved: {filename}")
    return filename

if __name__ == "__main__":
    creds = get_credentials()
    if not creds:
        exit(1)
    
    service = build('webmasters', 'v3', credentials=creds)
    rows = fetch_all_search_terms(service, days=DAYS)
    
    if not rows:
        print("⚠️  No search data found for this period.")
        exit(0)
    
    print(f"   ✅ Fetched {len(rows)} unique search terms")
    normal, suspicious = analyze_keywords(rows)
    print_report(normal, suspicious)
