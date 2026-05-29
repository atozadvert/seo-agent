#!/usr/bin/env python3
"""
Uptime Monitor — Checks all sites every 5 minutes.
Sends Slack + email alert when a site goes down, and a recovery alert when it comes back up.
Schedule via Task Scheduler to run every 5 minutes.
"""

import os
import sqlite3
import smtplib
import pickle
import requests
from datetime import datetime
from pathlib import Path
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── Load .env ─────────────────────────────────────────────────────────────────
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

# ── Config ────────────────────────────────────────────────────────────────────
CONFIG = {
    "email_to":       "info@atozadvert.com",
    "email_cc":       "ziarandhawa841@gmail.com",
    "email_from":     os.getenv("EMAIL_FROM", ""),
    "email_password": os.getenv("EMAIL_PASSWORD", ""),
    "smtp_server":    os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port":      587,
    "slack_webhook":  os.getenv("SLACK_WEBHOOK_URL", ""),
    "db_path":        "seo_guardian.db",
    "token_file":     "token.pickle",
    "timeout":        10,    # seconds before marking as down
    "slow_threshold": 3.0,   # seconds — warn if response takes longer
}

def get_sites_from_gsc() -> list:
    """Fetch all verified site URLs from Google Search Console."""
    token_path = Path(CONFIG["token_file"])
    if not token_path.exists():
        print("  ⚠️  token.pickle not found — using fallback site list")
        return [
            "https://atozappliancesrepair.com", "https://atozadvert.com",
            "https://silverservicesae.com", "https://silverpainters.com",
            "https://ppcexpertsdubai.com", "https://atiflawfirm.com",
            "https://nacl.pk", "https://www.premadedropshippingstores.com",
            "https://pre-made-shopify-store.blogspot.com",
        ]
    try:
        with open(token_path, "rb") as f:
            creds = pickle.load(f)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, "wb") as f:
                pickle.dump(creds, f)
        service = build("webmasters", "v3", credentials=creds)
        entries = service.sites().list().execute().get("siteEntry", [])
        # Convert sc-domain: entries to https:// and keep only http/https
        sites = []
        for e in entries:
            url = e["siteUrl"]
            if url.startswith("sc-domain:"):
                url = "https://" + url.replace("sc-domain:", "")
            if url.startswith("http"):
                sites.append(url.rstrip("/"))
        print(f"  ✅ Auto-detected {len(sites)} sites from GSC")
        return sites
    except Exception as ex:
        print(f"  ⚠️  GSC auto-detect failed ({ex}) — using fallback")
        return [
            "https://atozappliancesrepair.com", "https://atozadvert.com",
            "https://silverservicesae.com", "https://silverpainters.com",
            "https://ppcexpertsdubai.com", "https://atiflawfirm.com",
            "https://nacl.pk", "https://www.premadedropshippingstores.com",
            "https://pre-made-shopify-store.blogspot.com",
        ]


# ── Database ──────────────────────────────────────────────────────────────────
def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS uptime_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp     TEXT NOT NULL,
            site          TEXT NOT NULL,
            is_up         INTEGER NOT NULL,
            status_code   INTEGER,
            response_time REAL,
            error         TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS uptime_status (
            site          TEXT PRIMARY KEY,
            is_up         INTEGER NOT NULL,
            last_checked  TEXT NOT NULL,
            last_down     TEXT,
            down_since    TEXT,
            consecutive_fails INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    return conn


def get_last_status(conn, site: str) -> dict:
    row = conn.execute(
        "SELECT is_up, down_since, consecutive_fails FROM uptime_status WHERE site=?", (site,)
    ).fetchone()
    if row:
        return {"is_up": bool(row[0]), "down_since": row[1], "consecutive_fails": row[2]}
    return {"is_up": True, "down_since": None, "consecutive_fails": 0}


def save_status(conn, site: str, is_up: bool, down_since: str | None, fails: int):
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT OR REPLACE INTO uptime_status (site, is_up, last_checked, down_since, consecutive_fails)
        VALUES (?, ?, ?, ?, ?)
    """, (site, int(is_up), now, down_since, fails))
    conn.commit()


def log_check(conn, site: str, is_up: bool, status_code: int | None, response_time: float | None, error: str | None):
    conn.execute("""
        INSERT INTO uptime_log (timestamp, site, is_up, status_code, response_time, error)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (datetime.now().isoformat(), site, int(is_up), status_code, response_time, error))
    conn.commit()


# ── Check Site ────────────────────────────────────────────────────────────────
def check_site(url: str) -> dict:
    try:
        start = datetime.now()
        r = requests.get(url, timeout=CONFIG["timeout"], allow_redirects=True,
                         headers={"User-Agent": "SEO-Guardian-Uptime/1.0"})
        elapsed = (datetime.now() - start).total_seconds()
        is_up   = r.status_code < 500
        slow    = elapsed > CONFIG["slow_threshold"]
        return {
            "is_up":       is_up,
            "status_code": r.status_code,
            "response_time": round(elapsed, 2),
            "slow":        slow,
            "error":       None,
        }
    except requests.exceptions.Timeout:
        return {"is_up": False, "status_code": None, "response_time": None, "slow": False, "error": "Timeout"}
    except requests.exceptions.ConnectionError as e:
        return {"is_up": False, "status_code": None, "response_time": None, "slow": False, "error": "Connection refused"}
    except Exception as e:
        return {"is_up": False, "status_code": None, "response_time": None, "slow": False, "error": str(e)[:80]}


# ── Slack Alert ───────────────────────────────────────────────────────────────
def send_slack(message: str):
    webhook = CONFIG["slack_webhook"]
    if not webhook:
        return
    try:
        requests.post(webhook, json={"text": message}, timeout=10)
    except Exception:
        pass


# ── Email Alert ───────────────────────────────────────────────────────────────
def send_email_alert(subject: str, body_html: str):
    email_from = CONFIG["email_from"]
    password   = CONFIG["email_password"]
    if not email_from or not password:
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = email_from
    msg["To"]      = CONFIG["email_to"]
    msg["Cc"]      = CONFIG["email_cc"]
    msg.attach(MIMEText(body_html, "html", "utf-8"))
    try:
        with smtplib.SMTP(CONFIG["smtp_server"], CONFIG["smtp_port"]) as s:
            s.starttls()
            s.login(email_from, password)
            s.sendmail(email_from, [CONFIG["email_to"], CONFIG["email_cc"]], msg.as_bytes())
    except Exception as e:
        print(f"   ❌ Email failed: {e}")


def down_alert(site: str, result: dict, down_since: str):
    domain = site.replace("https://", "").replace("http://", "").rstrip("/")
    error  = result.get("error") or f"HTTP {result.get('status_code')}"
    ts     = datetime.now().strftime("%d %b %Y %I:%M %p")

    # Slack
    send_slack(
        f":red_circle: *SITE DOWN* — `{domain}`\n"
        f">Error: {error}\n"
        f">Time: {ts}\n"
        f">Check: {site}"
    )

    # Email
    html = f"""<!DOCTYPE html><html><body style="font-family:Arial;background:#f4f6f9;padding:20px">
    <div class="outer" style="max-width:600px;margin:0 auto;background:#fff;border-radius:10px;overflow:hidden">
        <div style="background:#e74c3c;color:#fff;padding:25px;text-align:center">
            <h1 style="margin:0">🔴 SITE DOWN</h1>
            <p style="margin:8px 0 0;opacity:0.9">{ts}</p>
        </div>
        <div style="padding:25px">
            <h2 style="color:#e74c3c;margin:0 0 15px">{domain}</h2>
            <div style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin-bottom:4px"><div style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin-bottom:4px"><table style="width:100%;border-collapse:collapse">
                <tr><td style="word-break:break-word;overflow-wrap:anywhere;max-width:200px" style="word-break:break-word;overflow-wrap:anywhere" style="padding:8px;color:#666;width:140px">URL</td><td style="word-break:break-word;overflow-wrap:anywhere;max-width:200px" style="word-break:break-word;overflow-wrap:anywhere" style="padding:8px;font-weight:bold">{site}</td></tr>
                <tr style="background:#fafafa"><td style="word-break:break-word;overflow-wrap:anywhere;max-width:200px" style="word-break:break-word;overflow-wrap:anywhere" style="padding:8px;color:#666">Error</td><td style="word-break:break-word;overflow-wrap:anywhere;max-width:200px" style="word-break:break-word;overflow-wrap:anywhere" style="padding:8px;color:#e74c3c;font-weight:bold">{error}</td></tr>
                <tr><td style="word-break:break-word;overflow-wrap:anywhere;max-width:200px" style="word-break:break-word;overflow-wrap:anywhere" style="padding:8px;color:#666">Down Since</td><td style="word-break:break-word;overflow-wrap:anywhere;max-width:200px" style="word-break:break-word;overflow-wrap:anywhere" style="padding:8px">{down_since}</td></tr>
            </table></div></div>
            <div style="margin-top:20px;padding:15px;background:#fff5f5;border-radius:8px;border-left:4px solid #e74c3c">
                <strong>Action Required:</strong> Check your hosting control panel immediately.
                Possible causes: hosting down, PHP error, .htaccess issue, expired domain.
            </div>
        </div>
    </div></body></html>"""
    send_email_alert(f"🔴 SITE DOWN: {domain}", html)


def recovery_alert(site: str, down_since: str, result: dict):
    domain  = site.replace("https://", "").replace("http://", "").rstrip("/")
    ts      = datetime.now().strftime("%d %b %Y %I:%M %p")
    rt      = result.get("response_time", "N/A")

    # Calculate downtime duration
    try:
        start = datetime.fromisoformat(down_since)
        dur   = datetime.now() - start
        mins  = int(dur.total_seconds() / 60)
        dur_str = f"{mins} minutes" if mins < 120 else f"{mins // 60} hours {mins % 60} min"
    except Exception:
        dur_str = "unknown"

    send_slack(
        f":large_green_circle: *SITE RECOVERED* — `{domain}`\n"
        f">Was down for: {dur_str}\n"
        f">Response time: {rt}s\n"
        f">Recovered at: {ts}"
    )

    html = f"""<!DOCTYPE html><html><body style="font-family:Arial;background:#f4f6f9;padding:20px">
    <div class="outer" style="max-width:600px;margin:0 auto;background:#fff;border-radius:10px;overflow:hidden">
        <div style="background:#27ae60;color:#fff;padding:25px;text-align:center">
            <h1 style="margin:0">🟢 SITE RECOVERED</h1>
            <p style="margin:8px 0 0;opacity:0.9">{ts}</p>
        </div>
        <div style="padding:25px">
            <h2 style="color:#27ae60;margin:0 0 15px">{domain}</h2>
            <div style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin-bottom:4px"><div style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin-bottom:4px"><table style="width:100%;border-collapse:collapse">
                <tr><td style="word-break:break-word;overflow-wrap:anywhere;max-width:200px" style="word-break:break-word;overflow-wrap:anywhere" style="padding:8px;color:#666;width:140px">URL</td><td style="word-break:break-word;overflow-wrap:anywhere;max-width:200px" style="word-break:break-word;overflow-wrap:anywhere" style="padding:8px">{site}</td></tr>
                <tr style="background:#fafafa"><td style="word-break:break-word;overflow-wrap:anywhere;max-width:200px" style="word-break:break-word;overflow-wrap:anywhere" style="padding:8px;color:#666">Total Downtime</td><td style="word-break:break-word;overflow-wrap:anywhere;max-width:200px" style="word-break:break-word;overflow-wrap:anywhere" style="padding:8px;font-weight:bold;color:#e74c3c">{dur_str}</td></tr>
                <tr><td style="word-break:break-word;overflow-wrap:anywhere;max-width:200px" style="word-break:break-word;overflow-wrap:anywhere" style="padding:8px;color:#666">Response Time</td><td style="word-break:break-word;overflow-wrap:anywhere;max-width:200px" style="word-break:break-word;overflow-wrap:anywhere" style="padding:8px">{rt}s</td></tr>
            </table></div></div>
        </div>
    </div></body></html>"""
    send_email_alert(f"🟢 SITE RECOVERED: {domain}", html)


# ── Main ──────────────────────────────────────────────────────────────────────
def run():
    print("=" * 55)
    print("  UPTIME MONITOR")
    print(f"  {datetime.now().strftime('%d %b %Y — %I:%M:%S %p')}")
    print("=" * 55)

    conn = init_db(CONFIG["db_path"])
    alerts_sent = 0

    SITES = get_sites_from_gsc()
    for site in SITES:
        domain = site.replace("https://", "").replace("http://", "").rstrip("/")
        result = check_site(site)
        last   = get_last_status(conn, site)

        status_icon = "✅" if result["is_up"] else "🔴"
        rt_str = f"{result['response_time']}s" if result["response_time"] else "N/A"
        slow_warn = " ⚡SLOW" if result.get("slow") else ""
        print(f"   {status_icon} {domain:<45} {rt_str}{slow_warn}")

        log_check(conn, site, result["is_up"], result.get("status_code"), result.get("response_time"), result.get("error"))

        if not result["is_up"]:
            fails      = last["consecutive_fails"] + 1
            down_since = last["down_since"] or datetime.now().isoformat()
            save_status(conn, site, False, down_since, fails)
            # Only alert on first failure (avoid spam on every 5-min check)
            if fails == 1:
                print(f"      🚨 ALERT SENT for {domain}")
                down_alert(site, result, down_since)
                alerts_sent += 1
        else:
            # Was it previously down? → Send recovery alert
            if not last["is_up"] and last["down_since"]:
                print(f"      🟢 RECOVERY ALERT for {domain}")
                recovery_alert(site, last["down_since"], result)
                alerts_sent += 1
            save_status(conn, site, True, None, 0)

    print(f"\n  Alerts sent: {alerts_sent}")
    print("=" * 55)
    conn.close()


if __name__ == "__main__":
    run()
