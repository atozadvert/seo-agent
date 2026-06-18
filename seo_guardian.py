#!/usr/bin/env python3
"""
SEO Guardian â€” Daily Multi-Site Monitor
Checks ALL verified Google Search Console properties and sends
ONE beautifully designed HTML email report.
"""

import os
import json
import pickle
import smtplib
import sqlite3
import requests
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.oauth2 import service_account
import base64

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Manual .env loader fallback
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  CONFIGURATION
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
CONFIG = {
    "email_to":       "info@atozadvert.com",
    "email_cc":       "ziarandhawa841@gmail.com",
    "email_from":     os.getenv("EMAIL_FROM", ""),
    "email_password": os.getenv("EMAIL_PASSWORD", ""),
    "smtp_server":    os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port":      587,
    "slack_webhook":  os.getenv("SLACK_WEBHOOK_URL", ""),
    "token_file":     "token.pickle",
    "days_lookback":  7,        # 7 for first run; change to 1 for daily use
    "min_clicks_alert": 1,
    "drop_threshold": 30,
    "db_path": os.getenv("DB_PATH", "seo_guardian.db"),
}

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  SUSPICIOUS PATTERNS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
SUSPICIOUS_PATTERNS = {
    "ðŸŽ° Gambling/Slot Spam": [
        "slot", "gacor", "togel", "toto", "jackpot", "maxwin",
        "bocoran", "judi", "casino", "betting", "poker",
        "kicau", "bacan", "madura", "sengtoto", "watitoto",
        "lotery", "lotere", "bandot", "slothok",
    ],
    "ðŸ”ž Adult Content":    ["porn", "sex", "xxx", "adult", "nude", "escort"],
    "ðŸ’Š Drugs/Illegal":    ["drug", "buy weed", "cocaine", "pills online"],
    "â‚¿ Crypto Spam":       ["bitcoin", "crypto", "nft", "forex scam"],
    "ðŸ’€ Hack/Inject":      ["hack", "crack", "keygen", "torrent", "nulled", "warez"],
    "ðŸ˜¤ Complaints":       ["scam", "fraud", "fake", "cheat", "ripoff",
                            "rip off", "overcharged", "worst", "avoid"],
    "ðŸ’¼ Wrong Intent":     ["hiring", "job vacancy", "salary", "internship"],
}

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  DATABASE
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def init_db():
    conn = sqlite3.connect(CONFIG["db_path"])
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS daily_stats (
        id INTEGER PRIMARY KEY, site TEXT, date TEXT,
        total_keywords INTEGER, suspicious_count INTEGER,
        total_clicks INTEGER, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS suspicious_log (
        id INTEGER PRIMARY KEY, site TEXT, keyword TEXT,
        category TEXT, clicks INTEGER, impressions INTEGER,
        position REAL, date TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS managed_sites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT UNIQUE NOT NULL,
        category TEXT,
        location TEXT,
        gsc_url TEXT,
        source TEXT DEFAULT 'gsc_auto',
        added_date DATE DEFAULT CURRENT_DATE,
        is_active INTEGER DEFAULT 1)''')
    conn.commit()
    return conn


def site_domain(site_url: str) -> str:
    if site_url.startswith("sc-domain:"):
        return site_url.replace("sc-domain:", "").strip().lower()
    return site_url.replace("https://", "").replace("http://", "").rstrip("/").lower()


def sync_managed_sites_from_gsc(db, sites: list[str]) -> int:
    synced = 0
    for site_url in sites:
        domain = site_domain(site_url)
        if not domain:
            continue
        db.execute('''INSERT OR REPLACE INTO managed_sites
            (domain, category, location, gsc_url, source, added_date, is_active)
            VALUES (
                ?,
                COALESCE((SELECT category FROM managed_sites WHERE domain=?), 'Uncategorized'),
                COALESCE((SELECT location FROM managed_sites WHERE domain=?), 'Unknown'),
                ?,
                'gsc_auto',
                date('now'),
                1
            )''', (domain, domain, domain, site_url))
        synced += 1
    db.commit()
    return synced

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  GOOGLE AUTH
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def get_gsc_service():
    service_account_b64 = os.getenv("GSC_SERVICE_ACCOUNT_JSON", "").strip()
    if service_account_b64:
        try:
            service_account_info = json.loads(base64.b64decode(service_account_b64).decode("utf-8"))
            creds = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
            )
            return build('webmasters', 'v3', credentials=creds)
        except Exception as exc:
            print(f"âŒ Invalid GSC_SERVICE_ACCOUNT_JSON: {exc}")
            return None

    if not Path(CONFIG["token_file"]).exists():
        print("âŒ No GSC credentials found. Set GSC_SERVICE_ACCOUNT_JSON or run: python setup_google_auth.py")
        return None
    with open(CONFIG["token_file"], 'rb') as f:
        creds = pickle.load(f)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(CONFIG["token_file"], 'wb') as f:
            pickle.dump(creds, f)
    if not creds or not creds.valid:
        print("âŒ Credentials invalid. Set GSC_SERVICE_ACCOUNT_JSON or run: python setup_google_auth.py")
        return None
    return build('webmasters', 'v3', credentials=creds)

def get_all_sites(service):
    response = service.sites().list().execute()
    return [s['siteUrl'] for s in response.get('siteEntry', [])]

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  DATA FETCHING
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def fetch_keywords(service, site_url, days=1):
    end_date   = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    all_rows, start_row = [], 0
    while True:
        try:
            result = service.searchanalytics().query(
                siteUrl=site_url,
                body={'startDate': start_date, 'endDate': end_date,
                      'dimensions': ['query'], 'rowLimit': 1000, 'startRow': start_row}
            ).execute()
            rows = result.get('rows', [])
            if not rows:
                break
            all_rows.extend(rows)
            start_row += len(rows)
            if len(rows) < 1000:
                break
        except Exception as e:
            print(f"   âš ï¸  {site_url}: {e}")
            break
    return all_rows

def fetch_7day_avg(service, site_url):
    try:
        result = service.searchanalytics().query(
            siteUrl=site_url,
            body={
                'startDate': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
                'endDate':   (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
                'dimensions': ['date'], 'rowLimit': 7,
            }
        ).execute()
        rows = result.get('rows', [])
        if not rows:
            return 0
        return round(sum(r.get('clicks', 0) for r in rows) / len(rows), 1)
    except:
        return 0

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  ANALYSIS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def classify_keyword(query):
    q = query.lower()
    for category, patterns in SUSPICIOUS_PATTERNS.items():
        for p in patterns:
            if p in q:
                return True, category
    return False, None

def analyze_site(service, site_url, db):
    domain = site_url.replace("https://", "").replace("http://", "").rstrip("/")
    print(f"   ðŸ” {domain} ...", end=" ", flush=True)
    today = datetime.now().strftime('%Y-%m-%d')
    rows  = fetch_keywords(service, site_url, days=CONFIG["days_lookback"])

    if not rows:
        print("no data")
        return {"site": domain, "site_url": site_url, "status": "no_data",
                "suspicious": {}, "normal": [], "total_keywords": 0,
                "total_clicks": 0, "avg_clicks": 0, "traffic_alert": False}

    suspicious_by_cat = {}
    normal = []
    total_clicks = 0

    for row in rows:
        keyword    = row['keys'][0]
        clicks     = int(row.get('clicks', 0))
        impressions= int(row.get('impressions', 0))
        position   = round(row.get('position', 0), 1)
        ctr        = round(row.get('ctr', 0) * 100, 2)
        total_clicks += clicks

        is_sus, category = classify_keyword(keyword)
        if is_sus:
            suspicious_by_cat.setdefault(category, []).append({
                "keyword": keyword, "clicks": clicks,
                "impressions": impressions, "position": position, "ctr": ctr,
            })
            db.execute('''INSERT INTO suspicious_log
                (site, keyword, category, clicks, impressions, position, date)
                VALUES (?,?,?,?,?,?,?)''',
                (domain, keyword, category, clicks, impressions, position, today))
        else:
            normal.append({"keyword": keyword, "clicks": clicks,
                           "impressions": impressions, "position": position, "ctr": ctr})

    # Sort each category by clicks desc
    for cat in suspicious_by_cat:
        suspicious_by_cat[cat].sort(key=lambda x: x['clicks'], reverse=True)
    normal.sort(key=lambda x: x['clicks'], reverse=True)

    avg_clicks   = fetch_7day_avg(service, site_url)
    drop_pct     = round((1 - total_clicks / avg_clicks) * 100) if avg_clicks > 0 else 0
    traffic_alert= drop_pct >= CONFIG["drop_threshold"]

    total_sus = sum(len(v) for v in suspicious_by_cat.values())
    db.execute('''INSERT INTO daily_stats
        (site, date, total_keywords, suspicious_count, total_clicks)
        VALUES (?,?,?,?,?)''',
        (domain, today, len(rows), total_sus, total_clicks))
    db.commit()

    print(f"{len(rows)} keywords | {total_sus} suspicious | {total_clicks} clicks")
    return {
        "site": domain, "site_url": site_url, "status": "ok",
        "total_keywords": len(rows),
        "suspicious": suspicious_by_cat,
        "total_suspicious": total_sus,
        "normal": normal,
        "total_clicks": total_clicks,
        "avg_clicks": avg_clicks,
        "drop_pct": drop_pct,
        "traffic_alert": traffic_alert,
    }

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  EMAIL BUILDER
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def build_email_html(reports, run_date):
    total_sites    = len([r for r in reports if r["status"] != "no_data"])
    total_sus      = sum(r.get("total_suspicious", 0) for r in reports)
    traffic_alerts = sum(1 for r in reports if r.get("traffic_alert"))
    sites_clean    = sum(1 for r in reports if r.get("status") == "ok" and r.get("total_suspicious", 0) == 0)
    overall_status = "ðŸš¨ Action Required" if total_sus > 0 or traffic_alerts else "âœ… All Clear"
    header_bg      = "#c0392b" if total_sus > 0 else "#27ae60"

    # â”€â”€ Top-level summary cards â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def card(icon, label, value, color="#2c3e50"):
        return f"""
        <td style="text-align:center;padding:15px;background:#fff;
                   border-radius:10px;min-width:120px;box-shadow:0 2px 6px rgba(0,0,0,0.08);">
            <div style="font-size:28px;">{icon}</div>
            <div style="font-size:26px;font-weight:700;color:{color};">{value}</div>
            <div style="font-size:12px;color:#888;margin-top:3px;">{label}</div>
        </td>"""

    summary_cards = f"""
    <table cellspacing="12" style="width:100%;margin:20px 0;">
      <tr>
        {card("ðŸŒ","Sites Monitored", total_sites)}
        {card("âœ…","Sites Clean", sites_clean, "#27ae60")}
        {card("ðŸš¨","Suspicious Keywords", total_sus, "#c0392b" if total_sus else "#27ae60")}
        {card("ðŸ“‰","Traffic Alerts", traffic_alerts, "#e67e22" if traffic_alerts else "#27ae60")}
      </tr>
    </table>"""

    # â”€â”€ Per-site blocks â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    site_blocks = ""
    for r in reports:
        domain = r["site"]
        if r["status"] == "no_data":
            site_blocks += f"""
            <div style="border-left:4px solid #bdc3c7;padding:12px 18px;margin:12px 0;
                        background:#f9f9f9;border-radius:6px;">
                <b>âšª {domain}</b> â€” No data available for this period.
            </div>"""
            continue

        sus       = r.get("suspicious", {})
        total_sus_site = r.get("total_suspicious", 0)
        top_normal = r["normal"][:5]
        border    = "#c0392b" if total_sus_site > 0 or r["traffic_alert"] else "#27ae60"
        site_icon = "ðŸš¨" if total_sus_site > 0 else ("âš ï¸" if r["traffic_alert"] else "âœ…")
        bg_header = "#fdf0f0" if total_sus_site > 0 else "#f0fdf4"

        # stats row
        stats_row = f"""
        <table style="width:100%;margin:10px 0;font-size:13px;">
          <tr>
            <td style="padding:6px 12px;background:#f8f9fa;border-radius:5px;text-align:center;">
                <b style="font-size:18px;">{r['total_keywords']}</b><br>
                <span style="color:#888;">Total Keywords</span>
            </td>
            <td width="10"></td>
            <td style="padding:6px 12px;background:#{'fdf0f0' if total_sus_site else 'f0fdf4'};border-radius:5px;text-align:center;">
                <b style="font-size:18px;color:{'#c0392b' if total_sus_site else '#27ae60'};">{total_sus_site}</b><br>
                <span style="color:#888;">Suspicious</span>
            </td>
            <td width="10"></td>
            <td style="padding:6px 12px;background:#f8f9fa;border-radius:5px;text-align:center;">
                <b style="font-size:18px;">{r['total_clicks']}</b><br>
                <span style="color:#888;">Clicks Today</span>
            </td>
            <td width="10"></td>
            <td style="padding:6px 12px;background:#{'fff3cd' if r['traffic_alert'] else 'f8f9fa'};border-radius:5px;text-align:center;">
                <b style="font-size:18px;color:{'#e67e22' if r['traffic_alert'] else '#2c3e50'};">{r['avg_clicks']}</b><br>
                <span style="color:#888;">7-Day Avg</span>
            </td>
          </tr>
        </table>"""

        # traffic alert banner
        traffic_banner = ""
        if r["traffic_alert"]:
            traffic_banner = f"""
            <div style="background:#fff3cd;border:1px solid #ffc107;border-radius:6px;
                        padding:10px 14px;margin:8px 0;font-size:13px;">
                âš ï¸ <b>Traffic Drop Alert:</b> Today's clicks are
                <b style="color:#e67e22;">{r['drop_pct']}% below</b> the 7-day average.
                Investigate immediately.
            </div>"""

        # suspicious categories table
        sus_section = ""
        if sus:
            sus_section = f"""
            <div style="margin-top:12px;">
              <p style="font-size:13px;font-weight:700;color:#c0392b;margin:0 0 6px;">
                ðŸš¨ Suspicious Keywords Detected ({total_sus_site} total)
              </p>"""
            for cat, items in sus.items():
                top_items = items[:8]
                sus_section += f"""
              <div style="margin-bottom:10px;">
                <div style="font-size:12px;font-weight:700;color:#7f8c8d;
                            background:#f8f9fa;padding:4px 10px;border-radius:4px;
                            display:inline-block;margin-bottom:4px;">{cat} ({len(items)} keywords)</div>
                <table style="width:100%;border-collapse:collapse;font-size:12px;">
                  <tr style="background:#fdf0f0;">
                    <th style="padding:5px 8px;text-align:left;border-bottom:1px solid #f5c6cb;">Keyword</th>
                    <th style="padding:5px 8px;text-align:center;border-bottom:1px solid #f5c6cb;">Clicks</th>
                    <th style="padding:5px 8px;text-align:center;border-bottom:1px solid #f5c6cb;">Impressions</th>
                    <th style="padding:5px 8px;text-align:center;border-bottom:1px solid #f5c6cb;">Position</th>
                  </tr>"""
                for i, kw in enumerate(top_items):
                    row_bg = "#fff" if i % 2 == 0 else "#fef9f9"
                    sus_section += f"""
                  <tr style="background:{row_bg};">
                    <td style="padding:5px 8px;color:#c0392b;font-weight:500;">{kw['keyword'][:60]}</td>
                    <td style="padding:5px 8px;text-align:center;font-weight:700;">{kw['clicks']}</td>
                    <td style="padding:5px 8px;text-align:center;">{kw['impressions']}</td>
                    <td style="padding:5px 8px;text-align:center;">#{kw['position']}</td>
                  </tr>"""
                if len(items) > 8:
                    sus_section += f"""
                  <tr><td colspan="4" style="padding:5px 8px;color:#888;font-style:italic;font-size:11px;">
                      + {len(items)-8} more keywords not shown...
                  </td></tr>"""
                sus_section += "</table></div>"
            sus_section += "</div>"

        # top legitimate keywords
        legit_section = ""
        if top_normal:
            legit_section = f"""
            <div style="margin-top:12px;">
              <p style="font-size:13px;font-weight:700;color:#27ae60;margin:0 0 6px;">
                âœ… Top Legitimate Keywords
              </p>
              <table style="width:100%;border-collapse:collapse;font-size:12px;">
                <tr style="background:#f0fdf4;">
                  <th style="padding:5px 8px;text-align:left;border-bottom:1px solid #b7efc5;">Keyword</th>
                  <th style="padding:5px 8px;text-align:center;border-bottom:1px solid #b7efc5;">Clicks</th>
                  <th style="padding:5px 8px;text-align:center;border-bottom:1px solid #b7efc5;">Position</th>
                  <th style="padding:5px 8px;text-align:center;border-bottom:1px solid #b7efc5;">CTR</th>
                </tr>"""
            for i, kw in enumerate(top_normal):
                row_bg = "#fff" if i % 2 == 0 else "#f9fef9"
                legit_section += f"""
                <tr style="background:{row_bg};">
                  <td style="padding:5px 8px;">{kw['keyword'][:55]}</td>
                  <td style="padding:5px 8px;text-align:center;font-weight:700;">{kw['clicks']}</td>
                  <td style="padding:5px 8px;text-align:center;">#{kw['position']}</td>
                  <td style="padding:5px 8px;text-align:center;">{kw['ctr']}%</td>
                </tr>"""
            legit_section += "</table></div>"

        site_blocks += f"""
        <div style="border-left:5px solid {border};border-radius:8px;
                    background:{bg_header};padding:16px 18px;margin:16px 0;
                    box-shadow:0 2px 8px rgba(0,0,0,0.06);">
            <h3 style="margin:0 0 10px;font-size:16px;color:#2c3e50;">
                {site_icon} &nbsp;{domain}
                <a href="https://search.google.com/search-console?resource_id={r['site_url']}"
                   style="font-size:11px;color:#3498db;font-weight:normal;
                          margin-left:10px;text-decoration:none;">
                   Open in GSC â†—
                </a>
            </h3>
            {stats_row}
            {traffic_banner}
            {sus_section}
            {legit_section}
        </div>"""

    # â”€â”€ Assemble full email â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  @media only screen and (max-width:600px){{
    .outer{{width:100%!important;margin:0!important;border-radius:0!important}}
    .inner{{padding:16px!important}}
    .stat-card{{display:block!important;width:100%!important;box-sizing:border-box!important;margin-bottom:8px!important}}
    .flex-bar{{display:block!important}}
    .flex-cell{{display:block!important;width:100%!important;border-right:none!important;border-bottom:1px solid #eee!important}}
    h1{{font-size:20px!important}}
    h2{{font-size:16px!important}}
    .hdr-pad{{padding:20px 16px!important}}
  }}
</style></head>
<body style="margin:0;padding:0;background:#eef2f7;font-family:Arial,sans-serif;">
<div class="outer" style="max-width:680px;margin:30px auto;background:#eef2f7;">

  <!-- HEADER -->
  <div style="background:{header_bg};border-radius:12px 12px 0 0;padding:28px 30px;text-align:center;">
    <div style="font-size:36px;margin-bottom:6px;">ðŸ›¡ï¸</div>
    <h1 style="margin:0;color:#fff;font-size:22px;letter-spacing:0.5px;">
        SEO Guardian â€” Daily Report
    </h1>
    <p style="margin:6px 0 0;color:rgba(255,255,255,0.85);font-size:13px;">
        {run_date} &nbsp;|&nbsp; Pakistan Standard Time &nbsp;|&nbsp; {overall_status}
    </p>
  </div>

  <!-- BODY -->
  <div class="inner" style="background:#fff;padding:24px 28px;border-radius:0 0 12px 12px;
              box-shadow:0 4px 15px rgba(0,0,0,0.08);">

    <!-- SUMMARY CARDS -->
    <h2 style="margin:0 0 4px;font-size:15px;color:#7f8c8d;
               text-transform:uppercase;letter-spacing:1px;">Overview</h2>
    {summary_cards}

    <!-- SITE REPORTS -->
    <h2 style="margin:24px 0 4px;font-size:15px;color:#7f8c8d;
               text-transform:uppercase;letter-spacing:1px;">Site-by-Site Report</h2>
    {site_blocks}

    <!-- WHAT TO DO SECTION -->
    {"" if total_sus == 0 else """
    <div style='background:#fff8f0;border:1px solid #ffd0a0;border-radius:8px;
                padding:16px 18px;margin-top:20px;'>
      <h3 style='margin:0 0 10px;color:#e67e22;font-size:14px;'>
          ðŸ”§ Recommended Actions
      </h3>
      <ol style='margin:0;padding-left:18px;font-size:13px;color:#444;line-height:1.8;'>
        <li>Log in to your website hosting panel and run a <b>malware scan</b></li>
        <li>Go to Google Search Console â†’ <b>Security &amp; Manual Actions</b> for each flagged site</li>
        <li>Search Google for: <code style='background:#f4f4f4;padding:2px 5px;border-radius:3px;'>site:yourdomain.com slot</code> to find injected pages</li>
        <li>Contact your hosting provider to <b>restore a clean backup</b></li>
        <li>After cleanup, request a <b>Google Review</b> in Search Console</li>
      </ol>
    </div>"""}

    <!-- FOOTER -->
    <div style="margin-top:28px;padding-top:16px;border-top:1px solid #ecf0f1;
                text-align:center;color:#bdc3c7;font-size:11px;">
        SEO Guardian &nbsp;|&nbsp; Auto-generated daily at 9:00 AM PKT<br>
        Monitoring {total_sites} Google Search Console properties<br>
        <span style="color:#e74c3c;">Reply to this email</span> if you need help taking action.
    </div>

  </div>
</div>
</body>
</html>"""

    return html


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  SEND EMAIL
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def send_email(html, total_sus, traffic_alerts):
    if not CONFIG["email_from"] or not CONFIG["email_password"]:
        print("\n   âš ï¸  Email not configured.")
        print("   Set EMAIL_FROM and EMAIL_PASSWORD environment variables.")
        print("   Or add them to a .env file and load with python-dotenv.")
        return False

    icon    = "ðŸš¨ ALERT" if total_sus > 0 or traffic_alerts else "âœ… All Clear"
    subject = f"{icon} â€” SEO Guardian Report ({datetime.now().strftime('%d %b %Y')})"

    try:
        msg = MIMEMultipart('alternative')
        msg['From']    = CONFIG["email_from"]
        msg['To']      = CONFIG["email_to"]
        msg['Subject'] = subject
        msg.attach(MIMEText(html, 'html', 'utf-8'))

        server = smtplib.SMTP(CONFIG["smtp_server"], CONFIG["smtp_port"])
        server.starttls()
        server.login(CONFIG["email_from"], CONFIG["email_password"])
        server.sendmail(CONFIG["email_from"], [CONFIG["email_to"], CONFIG["email_cc"]], msg.as_string())
        server.quit()
        print(f"   âœ… Email sent to {CONFIG['email_to']}")
        return True
    except Exception as e:
        print(f"   âŒ Email failed: {e}")
        return False


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  SLACK (optional)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def send_slack_summary(reports):
    webhook = CONFIG["slack_webhook"]
    if not webhook:
        return
    total_sus     = sum(r.get("total_suspicious", 0) for r in reports)
    traffic_alerts= sum(1 for r in reports if r.get("traffic_alert"))
    icon          = "ðŸš¨" if total_sus > 0 else "âœ…"
    text          = (f"{icon} *SEO Guardian â€” {datetime.now().strftime('%d %b %Y')}*\n"
                     f"Sites: {len(reports)} | Suspicious Keywords: {total_sus} | "
                     f"Traffic Alerts: {traffic_alerts}\n"
                     f"_Full report sent to {CONFIG['email_to']}_")
    try:
        requests.post(webhook, json={"text": text}, timeout=10)
        print("   âœ… Slack ping sent")
    except Exception as e:
        print(f"   âš ï¸  Slack failed: {e}")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  MAIN
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def run():
    run_date = datetime.now().strftime('%A, %d %B %Y â€” %I:%M %p')
    print("=" * 60)
    print("  SEO GUARDIAN â€” Daily Monitor")
    print(f"  {run_date}")
    print("=" * 60)

    service = get_gsc_service()
    if not service:
        return

    db    = init_db()
    sites = get_all_sites(service)
    print(f"\nâœ… Found {len(sites)} verified sites. Scanning...\n")
    synced = sync_managed_sites_from_gsc(db, sites)
    print(f"   âœ… Synced {synced} site(s) to managed_sites")

    reports = []
    for site_url in sites:
        report = analyze_site(service, site_url, db)
        reports.append(report)

    total_sus     = sum(r.get("total_suspicious", 0) for r in reports)
    traffic_alerts= sum(1 for r in reports if r.get("traffic_alert"))

    print(f"\nðŸ“§ Building email report...")
    html = build_email_html(reports, run_date)

    # Save HTML preview locally
    preview_file = f"email_preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(preview_file, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"   ðŸ’¾ Email preview saved: {preview_file} (open in browser to preview)")

    print(f"\nðŸ“£ Sending notifications...")
    send_email(html, total_sus, traffic_alerts)
    send_slack_summary(reports)

    print(f"\n{'='*60}")
    print(f"  DONE â€” {len(sites)} sites scanned")
    print(f"  ðŸš¨ Suspicious keywords: {total_sus}")
    print(f"  ðŸ“‰ Traffic alerts: {traffic_alerts}")
    print(f"{'='*60}")
    db.close()


if __name__ == "__main__":
    run()
