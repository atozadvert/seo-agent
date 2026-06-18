#!/usr/bin/env python3
"""
Rank Tracker — Daily keyword position monitor using Google Search Console.
Tracks target keywords per site, alerts on drops, finds CTR opportunities.
Run daily via Task Scheduler (added automatically by setup).
"""

import os
import json
import base64
import pickle
import sqlite3
import smtplib
from datetime import datetime, timedelta, date
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.oauth2 import service_account

# ── Load .env ────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

# ── Configuration ─────────────────────────────────────────────────────────────
CONFIG = {
    "email_to":       "info@atozadvert.com",
    "email_cc":       "ziarandhawa841@gmail.com",
    "email_from":     os.getenv("EMAIL_FROM", ""),
    "email_password": os.getenv("EMAIL_PASSWORD", ""),
    "smtp_server":    os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port":      587,
    "slack_webhook":  os.getenv("SLACK_WEBHOOK_URL", ""),
    "token_file":     "token.pickle",
    "db_path":        os.getenv("DB_PATH", "seo_guardian.db"),
    "drop_alert_threshold": 5,      # alert if position drops by this many spots
    "opportunity_min_impressions": 50,  # min impressions to be an opportunity
    "opportunity_pos_min": 4,       # positions 4-20 are "quick win" opportunities
    "opportunity_pos_max": 20,
}

# ── Target Keywords to Track ──────────────────────────────────────────────────
# Add/edit keywords per site. These are tracked daily for position changes.
TARGET_KEYWORDS = {
    "atozappliancesrepair.com": [
        "appliance repair dubai",
        "washing machine repair dubai",
        "refrigerator repair dubai",
        "ac repair dubai",
        "dryer repair dubai",
        "dishwasher repair dubai",
        "oven repair dubai",
        "appliance repair near me",
    ],
    "atozadvert.com": [
        "digital marketing dubai",
        "seo services dubai",
        "ppc agency dubai",
        "social media marketing dubai",
    ],
    "silverservicesae.com": [
        "cleaning services dubai",
        "maid service dubai",
        "deep cleaning dubai",
    ],
    "silverpainters.com": [
        "painting services dubai",
        "wall painting dubai",
        "painters dubai",
    ],
    "ppcexpertsdubai.com": [
        "ppc expert dubai",
        "google ads dubai",
        "pay per click dubai",
    ],
    "atiflawfirm.com": [
        "law firm dubai",
        "lawyer dubai",
        "legal services dubai",
    ],
    "nacl.pk": [
        "chemical supplier pakistan",
        "nacl pakistan",
    ],
}


# ── Database ──────────────────────────────────────────────────────────────────
def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rank_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT NOT NULL,
            site        TEXT NOT NULL,
            keyword     TEXT NOT NULL,
            position    REAL,
            clicks      INTEGER,
            impressions INTEGER,
            ctr         REAL,
            UNIQUE(date, site, keyword)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rank_alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            site        TEXT NOT NULL,
            keyword     TEXT NOT NULL,
            old_pos     REAL,
            new_pos     REAL,
            change      REAL,
            alert_type  TEXT
        )
    """)
    conn.commit()
    return conn


# ── Google Auth ───────────────────────────────────────────────────────────────
def get_gsc_service():
    service_account_b64 = os.getenv("GSC_SERVICE_ACCOUNT_JSON", "").strip()
    if service_account_b64:
        service_account_info = json.loads(base64.b64decode(service_account_b64).decode("utf-8"))
        creds = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
        )
        return build("webmasters", "v3", credentials=creds)

    token_file = CONFIG["token_file"]
    if not Path(token_file).exists():
        raise FileNotFoundError(
            "No GSC credentials found. Set GSC_SERVICE_ACCOUNT_JSON or run setup_google_auth.py first."
        )
    with open(token_file, "rb") as f:
        creds = pickle.load(f)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_file, "wb") as f:
            pickle.dump(creds, f)
    return build("webmasters", "v3", credentials=creds)


# ── Fetch GSC Data ─────────────────────────────────────────────────────────────
def fetch_keyword_positions(service, site_url: str, days: int = 7) -> dict:
    """Returns dict of keyword -> {position, clicks, impressions, ctr}"""
    end   = date.today() - timedelta(days=2)
    start = end - timedelta(days=days - 1)
    try:
        resp = service.searchanalytics().query(
            siteUrl=site_url,
            body={
                "startDate": start.isoformat(),
                "endDate":   end.isoformat(),
                "dimensions": ["query"],
                "rowLimit": 5000,
            }
        ).execute()
    except Exception as e:
        print(f"   ⚠️  Error fetching {site_url}: {e}")
        return {}

    result = {}
    for row in resp.get("rows", []):
        kw = row["keys"][0].lower()
        result[kw] = {
            "position":   round(row.get("position", 0), 1),
            "clicks":     row.get("clicks", 0),
            "impressions":row.get("impressions", 0),
            "ctr":        round(row.get("ctr", 0) * 100, 2),
        }
    return result


def get_verified_sites(service) -> dict:
    """Returns dict of domain -> full site URL"""
    sites_list = service.sites().list().execute()
    mapping = {}
    for s in sites_list.get("siteEntry", []):
        url = s["siteUrl"]
        domain = url.replace("https://", "").replace("http://", "").replace("sc-domain:", "").rstrip("/").replace("www.", "")
        mapping[domain] = url
    return mapping


# ── Save & Compare ─────────────────────────────────────────────────────────────
def save_and_compare(conn: sqlite3.Connection, site: str, keyword: str, data: dict) -> dict | None:
    today = date.today().isoformat()
    pos   = data.get("position")
    clicks = data.get("clicks", 0)
    imps   = data.get("impressions", 0)
    ctr    = data.get("ctr", 0)

    # Save today's rank
    conn.execute("""
        INSERT OR REPLACE INTO rank_history (date, site, keyword, position, clicks, impressions, ctr)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (today, site, keyword, pos, clicks, imps, ctr))
    conn.commit()

    # Get yesterday's rank
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    row = conn.execute(
        "SELECT position FROM rank_history WHERE date=? AND site=? AND keyword=?",
        (yesterday, site, keyword)
    ).fetchone()

    if row and row[0] and pos:
        old_pos = row[0]
        change  = pos - old_pos  # positive = dropped (worse), negative = improved
        if abs(change) >= CONFIG["drop_alert_threshold"]:
            alert_type = "DROP" if change > 0 else "GAIN"
            conn.execute("""
                INSERT INTO rank_alerts (timestamp, site, keyword, old_pos, new_pos, change, alert_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (datetime.now().isoformat(), site, keyword, old_pos, pos, change, alert_type))
            conn.commit()
            return {"keyword": keyword, "old": old_pos, "new": pos, "change": change, "type": alert_type}
    return None


# ── Find Opportunities ─────────────────────────────────────────────────────────
def find_opportunities(all_keywords: dict) -> list:
    """Keywords ranking 4-20 with high impressions = quick CTR wins."""
    opportunities = []
    for kw, data in all_keywords.items():
        pos  = data.get("position", 0)
        imps = data.get("impressions", 0)
        ctr  = data.get("ctr", 0)
        if (CONFIG["opportunity_pos_min"] <= pos <= CONFIG["opportunity_pos_max"]
                and imps >= CONFIG["opportunity_min_impressions"]):
            potential_clicks = int(imps * 0.10) - int(imps * (ctr / 100))
            opportunities.append({
                "keyword":    kw,
                "position":   pos,
                "impressions":imps,
                "ctr":        ctr,
                "potential_extra_clicks": max(0, potential_clicks),
            })
    opportunities.sort(key=lambda x: x["impressions"], reverse=True)
    return opportunities[:20]


# ── Email Builder ─────────────────────────────────────────────────────────────
def build_email(site_reports: list) -> str:
    now = datetime.now().strftime("%A, %d %b %Y")
    total_drops = sum(len(r["drops"]) for r in site_reports)
    total_gains = sum(len(r["gains"]) for r in site_reports)
    total_opps  = sum(len(r["opportunities"]) for r in site_reports)

    status_color = "#e74c3c" if total_drops > 0 else "#27ae60"
    status_icon  = "⚠️ Rank Drops Detected" if total_drops > 0 else "✅ All Rankings Stable"

    rows_html = ""
    for r in site_reports:
        if not r["tracked"] and not r["opportunities"]:
            continue
        site_name = r["site"]

        # Tracked keywords table
        tracked_rows = ""
        for kw, data in r["tracked"].items():
            pos    = data.get("position", "N/A")
            clicks = data.get("clicks", 0)
            imps   = data.get("impressions", 0)
            ctr    = data.get("ctr", 0)
            # Color-code position
            if isinstance(pos, (int, float)):
                if pos <= 3:   pos_color = "#27ae60"
                elif pos <= 10: pos_color = "#f39c12"
                else:           pos_color = "#e74c3c"
                pos_str = f'<span style="color:{pos_color};font-weight:bold">#{pos}</span>'
            else:
                pos_str = str(pos)
            tracked_rows += f"""
            <tr style="border-bottom:1px solid #f0f0f0">
                <td style="padding:8px 12px">{kw}</td>
                <td style="padding:8px 12px;text-align:center">{pos_str}</td>
                <td style="padding:8px 12px;text-align:center">{clicks}</td>
                <td style="padding:8px 12px;text-align:center">{imps:,}</td>
                <td style="padding:8px 12px;text-align:center">{ctr}%</td>
            </tr>"""

        # Alerts
        alerts_html = ""
        for alert in r["drops"] + r["gains"]:
            icon  = "🔴" if alert["type"] == "DROP" else "🟢"
            arrow = f"+{alert['change']:.1f}" if alert["change"] > 0 else f"{alert['change']:.1f}"
            alerts_html += f"""
            <tr style="background:#fff5f5">
                <td style="padding:6px 12px">{icon} {alert['keyword']}</td>
                <td style="padding:6px 12px;text-align:center">#{alert['old']}</td>
                <td style="padding:6px 12px;text-align:center">#{alert['new']}</td>
                <td style="padding:6px 12px;text-align:center;font-weight:bold">{arrow}</td>
            </tr>"""

        # Opportunities
        opps_html = ""
        for opp in r["opportunities"][:5]:
            opps_html += f"""
            <tr style="background:#f0fff4">
                <td style="padding:6px 12px">💡 {opp['keyword']}</td>
                <td style="padding:6px 12px;text-align:center">#{opp['position']}</td>
                <td style="padding:6px 12px;text-align:center">{opp['impressions']:,}</td>
                <td style="padding:6px 12px;text-align:center">+{opp['potential_extra_clicks']} clicks potential</td>
            </tr>"""

        rows_html += f"""
        <div style="margin:20px 0;background:#fff;border-radius:10px;border:1px solid #e0e0e0;overflow:hidden">
            <div style="background:#2c3e50;color:#fff;padding:14px 20px;font-size:16px;font-weight:bold">
                🌐 {site_name}
                <span style="float:right;font-size:13px;font-weight:normal;opacity:0.8">
                    {len(r['tracked'])} keywords tracked · {len(r['drops'])} drops · {len(r['gains'])} gains
                </span>
            </div>

            {"" if not r['drops'] and not r['gains'] else f'''
            <div style="padding:0 20px 10px">
                <p style="font-size:13px;font-weight:bold;color:#555;margin:14px 0 6px">POSITION CHANGES</p>
                <table style="width:100%;border-collapse:collapse;font-size:13px">
                    <tr style="background:#f8f8f8;color:#666">
                        <th style="padding:8px 12px;text-align:left">Keyword</th>
                        <th style="padding:8px 12px">Was</th>
                        <th style="padding:8px 12px">Now</th>
                        <th style="padding:8px 12px">Change</th>
                    </tr>{alerts_html}
                </table>
            </div>'''}

            <div style="padding:0 20px 10px">
                <p style="font-size:13px;font-weight:bold;color:#555;margin:14px 0 6px">TRACKED KEYWORDS</p>
                <table style="width:100%;border-collapse:collapse;font-size:13px">
                    <tr style="background:#f8f8f8;color:#666">
                        <th style="padding:8px 12px;text-align:left">Keyword</th>
                        <th style="padding:8px 12px">Position</th>
                        <th style="padding:8px 12px">Clicks</th>
                        <th style="padding:8px 12px">Impressions</th>
                        <th style="padding:8px 12px">CTR</th>
                    </tr>{tracked_rows}
                </table>
            </div>

            {"" if not r['opportunities'] else f'''
            <div style="padding:0 20px 14px">
                <p style="font-size:13px;font-weight:bold;color:#27ae60;margin:14px 0 6px">💡 CTR OPPORTUNITIES (positions 4-20 with high impressions)</p>
                <table style="width:100%;border-collapse:collapse;font-size:13px">
                    <tr style="background:#f0fff4;color:#666">
                        <th style="padding:6px 12px;text-align:left">Keyword</th>
                        <th style="padding:6px 12px">Position</th>
                        <th style="padding:6px 12px">Impressions</th>
                        <th style="padding:6px 12px">Opportunity</th>
                    </tr>{opps_html}
                </table>
            </div>'''}
        </div>"""

    return f"""<!DOCTYPE html>
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
</style><title>Rank Tracker Report</title></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:Arial,sans-serif">
<div class="outer" style="max-width:800px;margin:0 auto;padding:20px">

    <!-- Header -->
    <div style="background:{status_color};color:#fff;padding:30px;border-radius:12px 12px 0 0;text-align:center">
        <h1 style="margin:0;font-size:26px">📈 Rank Tracker Report</h1>
        <p style="margin:8px 0 0;opacity:0.9">{now}</p>
    </div>

    <!-- Summary -->
    <div class="inner" style="background:#fff;padding:20px;border-left:1px solid #e0e0e0;border-right:1px solid #e0e0e0">
        <p style="font-size:18px;font-weight:bold;color:{status_color};margin:0 0 15px">{status_icon}</p>
        <div style="display:flex;gap:15px;flex-wrap:wrap">
            <div class="stat-card" class="stat-card" style="background:#fff5f5;border-radius:8px;padding:15px 25px;text-align:center;flex:1;min-width:120px">
                <div style="font-size:28px;font-weight:bold;color:#e74c3c">{total_drops}</div>
                <div style="font-size:12px;color:#888">DROPS</div>
            </div>
            <div class="stat-card" class="stat-card" style="background:#f0fff4;border-radius:8px;padding:15px 25px;text-align:center;flex:1;min-width:120px">
                <div style="font-size:28px;font-weight:bold;color:#27ae60">{total_gains}</div>
                <div style="font-size:12px;color:#888">GAINS</div>
            </div>
            <div class="stat-card" class="stat-card" style="background:#fffbf0;border-radius:8px;padding:15px 25px;text-align:center;flex:1;min-width:120px">
                <div style="font-size:28px;font-weight:bold;color:#f39c12">{total_opps}</div>
                <div style="font-size:12px;color:#888">OPPORTUNITIES</div>
            </div>
        </div>
    </div>

    <!-- Site Reports -->
    {rows_html}

    <!-- Footer -->
    <div style="background:#2c3e50;color:#aaa;padding:20px;border-radius:0 0 12px 12px;text-align:center;font-size:12px">
        SEO Guardian Rank Tracker · Auto-generated daily at 9:00 AM PKT
    </div>
</div>
</body>
</html>"""


# ── Send Email ────────────────────────────────────────────────────────────────
def send_email(html: str, total_drops: int):
    email_from = CONFIG["email_from"]
    email_to   = CONFIG["email_to"]
    password   = CONFIG["email_password"]
    if not email_from or not password:
        print("   ⚠️  Email not configured (EMAIL_FROM / EMAIL_PASSWORD)")
        return
    subject = f"📈 Rank Tracker — {'⚠️ ' + str(total_drops) + ' drops detected' if total_drops else '✅ All rankings stable'} — {date.today().strftime('%b %d')}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = email_from
    msg["To"]      = email_to
    msg["Cc"]      = CONFIG["email_cc"]
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        with smtplib.SMTP(CONFIG["smtp_server"], CONFIG["smtp_port"]) as s:
            s.starttls()
            s.login(email_from, password)
            s.sendmail(email_from, [email_to, CONFIG["email_cc"]], msg.as_bytes())
        print(f"   ✅ Email sent to {email_to}")
    except Exception as e:
        print(f"   ❌ Email failed: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────
def run():
    print("=" * 60)
    print("  RANK TRACKER — Daily Keyword Monitor")
    print(f"  {datetime.now().strftime('%A, %d %b %Y — %I:%M %p')}")
    print("=" * 60)

    conn    = init_db(CONFIG["db_path"])
    service = get_gsc_service()

    # Get all verified sites
    site_map = get_verified_sites(service)

    site_reports = []

    # Auto-detect new sites not yet in TARGET_KEYWORDS
    for domain in site_map:
        if domain not in TARGET_KEYWORDS:
            TARGET_KEYWORDS[domain] = []  # will track top GSC keywords automatically

    for domain, keywords in TARGET_KEYWORDS.items():
        # Find matching verified site URL
        site_url = site_map.get(domain)
        if not site_url:
            print(f"   ⚠️  {domain} not found in GSC — skipping")
            continue

        print(f"\n   🔍 {domain}")
        all_keywords = fetch_keyword_positions(service, site_url, days=3)

        # Auto-populate top keywords for new sites with no configured keywords
        if not keywords and all_keywords:
            auto_kws = sorted(all_keywords.items(), key=lambda x: -x[1].get("impressions", 0))[:5]
            keywords  = [k for k, _ in auto_kws]
            TARGET_KEYWORDS[domain] = keywords
            print(f"      ℹ️  Auto-tracking top {len(keywords)} keywords")

        tracked = {}
        drops   = []
        gains   = []

        for kw in keywords:
            kw_lower = kw.lower()
            data = all_keywords.get(kw_lower, {})
            if data:
                tracked[kw] = data
                alert = save_and_compare(conn, domain, kw, data)
                if alert:
                    if alert["type"] == "DROP":
                        drops.append(alert)
                        print(f"      🔴 DROP: '{kw}' #{alert['old']} → #{alert['new']}")
                    else:
                        gains.append(alert)
                        print(f"      🟢 GAIN: '{kw}' #{alert['old']} → #{alert['new']}")
                else:
                    pos = data.get("position", "N/A")
                    print(f"      ✅ '{kw}' → #{pos}")
            else:
                print(f"      ⚪ '{kw}' → not ranking (no data)")

        opportunities = find_opportunities(all_keywords)
        if opportunities:
            print(f"      💡 {len(opportunities)} CTR opportunities found")

        site_reports.append({
            "site":          domain,
            "tracked":       tracked,
            "drops":         drops,
            "gains":         gains,
            "opportunities": opportunities,
        })

    total_drops = sum(len(r["drops"]) for r in site_reports)
    total_gains = sum(len(r["gains"]) for r in site_reports)

    print(f"\n📧 Building rank report email...")
    html = build_email(site_reports)

    preview = f"rank_preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(preview, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"   💾 Preview saved: {preview}")

    send_email(html, total_drops)

    # ── Rich Slack summary ────────────────────────────────────────
    webhook = CONFIG.get("slack_webhook","")
    if webhook:
        today = date.today().strftime("%d %b %Y")
        site_lines = []
        for r in site_reports:
            drops_n = len(r["drops"])
            gains_n = len(r["gains"])
            opps_n  = len(r["opportunities"])
            icon    = ":red_circle:" if drops_n > 0 else ":large_green_circle:"
            site_lines.append(
                f"{icon} `{r['site']}` — "
                f":chart_with_downwards_trend: {drops_n} drops  "
                f":chart_with_upwards_trend: {gains_n} gains  "
                f":bulb: {opps_n} opps"
            )
        rank_icon = '\U0001f4c9' if total_drops else '\u2705'
        blocks = [
            {"type":"header","text":{"type":"plain_text",
                "text":f"{rank_icon} Rank Tracker — {today}"}},
            {"type":"section","fields":[
                {"type":"mrkdwn","text":f"*Sites:*\n{len(site_reports)}"},
                {"type":"mrkdwn","text":f"*Rank Drops:*\n{'`'+str(total_drops)+'` :rotating_light:' if total_drops else '`0` :white_check_mark:'}"},
                {"type":"mrkdwn","text":f"*Rank Gains:*\n`{total_gains}` :chart_with_upwards_trend:"},
                {"type":"mrkdwn","text":f"*Opportunities:*\n`{sum(len(r['opportunities']) for r in site_reports)}` :bulb:"},
            ]},
            {"type":"divider"},
            {"type":"section","text":{"type":"mrkdwn",
                "text":"*Per-Site Rankings:*\n" + "\n".join(site_lines)}},
            {"type":"context","elements":[
                {"type":"mrkdwn","text":f":email: Full report emailed to `{CONFIG['email_to']}`"}
            ]}
        ]
        try:
            requests.post(webhook, json={"blocks":blocks,"text":f"Rank Tracker Report — {today}"}, timeout=10)
            print("   \u2705 Slack summary sent")
        except Exception as e:
            print(f"   \u26a0\ufe0f  Slack failed: {e}")

    print(f"\n{'='*60}")
    print(f"  DONE — {len(site_reports)} sites | {total_drops} drops | {total_gains} gains")
    print(f"{'='*60}")
    conn.close()


if __name__ == "__main__":
    run()
