#!/usr/bin/env python3
"""
Advanced SEO Monitor — 3 new daily checks:
  1. Redirect Tracker     — detect pages redirecting to wrong/spam domains
  2. Indexing Monitor     — alert on >30% daily change in indexed page count
  3. External Links Monitor — detect new outbound links (spam injection) on your pages

Run daily via Task Scheduler at 9:15 AM.
"""

import os
import re
import json
import base64
import pickle
import sqlite3
import smtplib
import requests
from datetime import datetime, timedelta, date
from pathlib import Path
from urllib.parse import urlparse, urljoin
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.oauth2 import service_account

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

# ── Configuration ─────────────────────────────────────────────────────────────
DEFAULT_DB_PATH = "/tmp/seo_guardian.db" if os.getenv("RAILWAY_ENVIRONMENT") else "seo_guardian.db"

CONFIG = {
    "email_to":       "info@atozadvert.com",
    "email_cc":       "ziarandhawa841@gmail.com",
    "email_from":     os.getenv("EMAIL_FROM", ""),
    "email_password": os.getenv("EMAIL_PASSWORD", ""),
    "smtp_server":    os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port":      587,
    "slack_webhook":  os.getenv("SLACK_WEBHOOK_URL", ""),
    "token_file":     "token.pickle",
    "db_path":        os.getenv("DB_PATH", DEFAULT_DB_PATH),
    "indexing_threshold": 30,     # % daily change to trigger alert
    "redirect_timeout":   8,      # seconds
    "crawl_timeout":      8,
    "top_pages":          10,     # pages to check per site (reduced for speed)
    "redirect_check_pages": 5,    # only check top 5 pages for redirects
}

SUSPICIOUS_LINK_PATTERNS = [
    "slot", "gacor", "togel", "casino", "judi", "poker", "toto",
    "porn", "xxx", "escort", "adult",
    "buy-viagra", "pharmacy", "cialis",
    "bitcoin", "crypto", "nft", "forex",
    "hack", "crack", "keygen", "warez", "nulled",
]

def get_sites_from_gsc(service) -> list:
    """Fetch all verified site URLs from GSC, convert sc-domain: to https://."""
    try:
        entries = service.sites().list().execute().get("siteEntry", [])
        sites = []
        for e in entries:
            url = e["siteUrl"]
            if url.startswith("sc-domain:"):
                url = "https://" + url.replace("sc-domain:", "")
            if url.startswith("http"):
                sites.append(url.rstrip("/"))
        print(f"  Auto-detected {len(sites)} GSC properties")
        return sites
    except Exception as ex:
        print(f"  ⚠️  GSC site list failed: {ex}")
        return []

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ── Database ──────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(CONFIG["db_path"])
    conn.execute("""
        CREATE TABLE IF NOT EXISTS index_tracking (
            site TEXT,
            date TEXT,
            page_count INTEGER,
            PRIMARY KEY (site, date)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS external_links_baseline (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            site  TEXT,
            link_url TEXT,
            first_seen TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS redirect_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site TEXT,
            page_url TEXT,
            final_url TEXT,
            redirect_hops INTEGER,
            issues TEXT,
            detected_date TEXT,
            UNIQUE(site, page_url, detected_date)
        )
    """)
    conn.commit()
    return conn


# ── Google Auth ───────────────────────────────────────────────────────────────
def get_gsc_service():
    service_account_b64 = os.getenv("GSC_SERVICE_ACCOUNT_JSON", "").strip()
    if service_account_b64:
        try:
            service_account_info = json.loads(base64.b64decode(service_account_b64).decode("utf-8"))
            creds = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
            )
            return build("webmasters", "v3", credentials=creds)
        except Exception as ex:
            print(f"⚠️  Invalid GSC_SERVICE_ACCOUNT_JSON ({ex}) — trying token.pickle")

    token_path = Path(CONFIG["token_file"])
    if not token_path.exists():
        print("❌ No GSC credentials found. Set GSC_SERVICE_ACCOUNT_JSON or run: python setup_google_auth.py")
        return None
    with open(token_path, "rb") as f:
        creds = pickle.load(f)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)
    if not creds or not creds.valid:
        print("❌ Credentials invalid. Run: python setup_google_auth.py")
        return None
    return build("webmasters", "v3", credentials=creds)


def get_top_pages(service, site_url, n=15):
    """Return top N page URLs from GSC (last 7 days)."""
    try:
        end   = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        result = service.searchanalytics().query(
            siteUrl=site_url,
            body={
                "startDate": start,
                "endDate":   end,
                "dimensions": ["page"],
                "rowLimit":  n,
                "orderBy":   [{"fieldName": "impressions", "sortOrder": "DESCENDING"}],
            }
        ).execute()
        return [row["keys"][0] for row in result.get("rows", [])]
    except Exception as e:
        print(f"   ⚠️  GSC pages fetch failed for {site_url}: {e}")
        return [site_url]  # fallback to homepage


def get_daily_page_count(service, site_url, date_str):
    """Count unique pages with impressions on a given date via GSC."""
    try:
        result = service.searchanalytics().query(
            siteUrl=site_url,
            body={
                "startDate": date_str,
                "endDate":   date_str,
                "dimensions": ["page"],
                "rowLimit":  5000,
            }
        ).execute()
        return len(result.get("rows", []))
    except:
        return 0


# ── 1. REDIRECT TRACKER ───────────────────────────────────────────────────────
def check_redirects(site_url, pages, db):
    """Follow each page URL and flag redirect anomalies."""
    domain     = urlparse(site_url).netloc.replace("www.", "")
    today      = date.today().isoformat()
    issues_found = []

    for page_url in pages:
        try:
            resp = requests.get(
                page_url,
                timeout=CONFIG["redirect_timeout"],
                allow_redirects=True,
                headers=HEADERS,
            )
            final_url     = resp.url
            final_netloc  = urlparse(final_url).netloc.replace("www.", "")
            redirect_hops = len(resp.history)
            problems      = []

            # Cross-domain redirect?
            if final_netloc and final_netloc != domain and not final_netloc.endswith("." + domain):
                problems.append(f"Cross-domain redirect → {final_netloc}")

            # Too many hops?
            if redirect_hops > 2:
                problems.append(f"Redirect chain: {redirect_hops} hops")

            # Suspicious destination content?
            if any(p in final_url.lower() for p in SUSPICIOUS_LINK_PATTERNS):
                problems.append(f"Suspicious destination URL")

            if problems:
                issue_str = " | ".join(problems)
                issues_found.append({
                    "original":  page_url,
                    "final":     final_url,
                    "hops":      redirect_hops,
                    "issues":    issue_str,
                    "status":    resp.status_code,
                })
                try:
                    db.execute(
                        "INSERT OR IGNORE INTO redirect_log "
                        "(site, page_url, final_url, redirect_hops, issues, detected_date) "
                        "VALUES (?,?,?,?,?,?)",
                        (domain, page_url, final_url, redirect_hops, issue_str, today)
                    )
                except:
                    pass

        except Exception:
            pass

    db.commit()
    return issues_found


# ── 2. INDEXING CHANGE MONITOR ────────────────────────────────────────────────
def check_indexing(service, site_url, db):
    """Compare today vs yesterday page counts. Alert if change >= threshold."""
    domain = urlparse(site_url).netloc.replace("www.", "")
    today  = date.today().isoformat()

    # Find the most recent date with data (GSC lags 1-3 days)
    today_count  = 0
    actual_date  = None
    for days_back in range(0, 4):
        d = (date.today() - timedelta(days=days_back)).isoformat()
        cnt = get_daily_page_count(service, site_url, d)
        if cnt > 0:
            today_count = cnt
            actual_date = d
            break

    if today_count == 0:
        # No GSC data available — skip alert, just record 0
        db.execute(
            "INSERT OR REPLACE INTO index_tracking (site, date, page_count) VALUES (?,?,?)",
            (domain, today, 0)
        )
        db.commit()
        return {"site": domain, "today": 0, "prev": 0, "change_pct": 0.0, "alert": False,
                "note": "No GSC data available yet"}

    compare_date = (date.fromisoformat(actual_date) - timedelta(days=1)).isoformat()

    # Previous count from DB (fallback: GSC)
    row = db.execute(
        "SELECT page_count FROM index_tracking WHERE site=? AND date=?",
        (domain, compare_date)
    ).fetchone()
    prev_count = row[0] if row else get_daily_page_count(service, site_url, compare_date)

    # Store today's count
    db.execute(
        "INSERT OR REPLACE INTO index_tracking (site, date, page_count) VALUES (?,?,?)",
        (domain, today, today_count)
    )
    db.commit()

    if prev_count == 0:
        # No previous baseline — first run, just store for tomorrow
        return {"site": domain, "today": today_count, "prev": 0, "change_pct": 0.0, "alert": False,
                "note": "Baseline established"}

    change_pct = round(((today_count - prev_count) / prev_count) * 100, 1)
    alert      = abs(change_pct) >= CONFIG["indexing_threshold"]
    direction  = "📉 DROP" if change_pct < 0 else "📈 SURGE"

    return {
        "site":       domain,
        "today":      today_count,
        "prev":       prev_count,
        "change_pct": change_pct,
        "direction":  direction,
        "alert":      alert,
    }


# ── 3. EXTERNAL LINKS MONITOR ─────────────────────────────────────────────────
def scan_outbound_links(site_url, pages):
    """Crawl pages and extract all external outbound links."""
    domain = urlparse(site_url).netloc.replace("www.", "")
    found  = set()

    for page_url in pages[:10]:
        try:
            resp = requests.get(page_url, timeout=CONFIG["crawl_timeout"], headers=HEADERS)
            hrefs = re.findall(r'href=["\']([^"\'#\s]{5,})["\']', resp.text, re.IGNORECASE)
            for href in hrefs:
                # Resolve relative URLs
                abs_url = urljoin(page_url, href)
                parsed  = urlparse(abs_url)
                if parsed.scheme not in ("http", "https"):
                    continue
                link_domain = parsed.netloc.replace("www.", "")
                if link_domain and link_domain != domain and not link_domain.endswith("." + domain):
                    found.add(abs_url[:300])  # cap length
        except Exception:
            pass

    return list(found)


def check_external_links(site_url, pages, db):
    """Detect new outbound external links since last run."""
    domain = urlparse(site_url).netloc.replace("www.", "")
    today  = date.today().isoformat()

    current_links = set(scan_outbound_links(site_url, pages))

    # Load stored baseline
    rows      = db.execute(
        "SELECT link_url FROM external_links_baseline WHERE site=?", (domain,)
    ).fetchall()
    prev_links = {r[0] for r in rows}

    new_links  = current_links - prev_links
    gone_links = prev_links - current_links

    # Update baseline
    db.execute("DELETE FROM external_links_baseline WHERE site=?", (domain,))
    for link in current_links:
        db.execute(
            "INSERT INTO external_links_baseline (site, link_url, first_seen) VALUES (?,?,?)",
            (domain, link, today)
        )
    db.commit()

    # Classify new links
    suspicious_new = []
    clean_new      = []
    for link in new_links:
        if any(p in link.lower() for p in SUSPICIOUS_LINK_PATTERNS):
            suspicious_new.append(link)
        else:
            clean_new.append(link)

    return {
        "site":           domain,
        "total_current":  len(current_links),
        "new_count":      len(new_links),
        "gone_count":     len(gone_links),
        "suspicious_new": suspicious_new,
        "clean_new":      clean_new[:10],  # show max 10 clean new links
        "alert":          len(suspicious_new) > 0,
    }


# ── EMAIL HTML ────────────────────────────────────────────────────────────────
def build_email(redirect_results, indexing_results, link_results, run_date):
    total_redirect_issues = sum(len(r["issues"]) for r in redirect_results)
    total_index_alerts    = sum(1 for r in indexing_results if r.get("alert"))
    total_link_alerts     = sum(1 for r in link_results if r.get("alert"))
    any_alert             = total_redirect_issues or total_index_alerts or total_link_alerts

    status_color = "#e74c3c" if any_alert else "#27ae60"
    status_label = "🚨 ALERTS DETECTED" if any_alert else "✅ ALL CLEAR"

    # ── Redirect section ──────────────────────────────────────────────────────
    redir_rows = ""
    for r in redirect_results:
        color = "#e74c3c" if r["issues"] else "#27ae60"
        icon  = "🚨" if r["issues"] else "✅"
        for issue in r["issues"]:
            redir_rows += f"""
            <tr style="border-bottom:1px solid #f0f0f0">
                <td style="padding:10px 12px">{icon} <strong>{r['site']}</strong></td>
                <td style="padding:10px 12px;font-size:12px;color:#666;word-break:break-all">{issue['original'][:70]}</td>
                <td style="padding:10px 12px;font-size:12px;word-break:break-all">{issue['final'][:70]}</td>
                <td style="padding:10px 12px;color:{color};font-size:12px">{issue['issues']}</td>
            </tr>"""
        if not r["issues"]:
            redir_rows += f"""
            <tr style="border-bottom:1px solid #f0f0f0">
                <td style="padding:10px 12px">✅ <strong>{r['site']}</strong></td>
                <td colspan="3" style="padding:10px 12px;color:#27ae60">No redirect issues found</td>
            </tr>"""

    # ── Indexing section ──────────────────────────────────────────────────────
    idx_rows = ""
    for r in indexing_results:
        alert_color = "#e74c3c" if r.get("alert") else "#27ae60"
        change_str  = f"{r['change_pct']:+.1f}%" if r.get("change_pct") else "N/A"
        direction   = r.get("direction", "")
        idx_rows += f"""
            <tr style="border-bottom:1px solid #f0f0f0">
                <td style="padding:10px 12px"><strong>{r['site']}</strong></td>
                <td style="padding:10px 12px;text-align:center">{r.get('prev', 0)}</td>
                <td style="padding:10px 12px;text-align:center">{r.get('today', 0)}</td>
                <td style="padding:10px 12px;text-align:center;color:{alert_color};font-weight:bold">{direction} {change_str}</td>
                <td style="padding:10px 12px;text-align:center">{'🚨 ALERT' if r.get('alert') else '✅ Normal'}</td>
            </tr>"""

    # ── External links section ────────────────────────────────────────────────
    link_rows = ""
    for r in link_results:
        if r.get("suspicious_new"):
            for link in r["suspicious_new"]:
                link_rows += f"""
                <tr style="border-bottom:1px solid #f0f0f0;background:#fff5f5">
                    <td style="padding:8px 12px">🚨 <strong>{r['site']}</strong></td>
                    <td style="padding:8px 12px;color:#e74c3c">SUSPICIOUS</td>
                    <td style="padding:8px 12px;font-size:12px;word-break:break-all">{link[:100]}</td>
                </tr>"""
        if r.get("clean_new"):
            for link in r["clean_new"][:5]:
                link_rows += f"""
                <tr style="border-bottom:1px solid #f0f0f0">
                    <td style="padding:8px 12px">🔗 <strong>{r['site']}</strong></td>
                    <td style="padding:8px 12px;color:#f39c12">New Link</td>
                    <td style="padding:8px 12px;font-size:12px;word-break:break-all">{link[:100]}</td>
                </tr>"""
        if not r.get("suspicious_new") and not r.get("clean_new") and r.get("new_count", 0) == 0:
            link_rows += f"""
                <tr style="border-bottom:1px solid #f0f0f0">
                    <td style="padding:8px 12px">✅ <strong>{r['site']}</strong></td>
                    <td style="padding:8px 12px;color:#27ae60">No new links</td>
                    <td style="padding:8px 12px;color:#999">{r.get('total_current', 0)} outbound links total</td>
                </tr>"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
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
<body style="margin:0;padding:0;background:#f4f6f9;font-family:'Segoe UI',Arial,sans-serif">
<div class="outer" style="max-width:900px;margin:20px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,.1)">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);padding:35px 40px;text-align:center">
    <h1 style="color:#fff;margin:0;font-size:26px;font-weight:700">🔬 Advanced SEO Monitor</h1>
    <p style="color:#a0b4d0;margin:10px 0 0;font-size:15px">{run_date}</p>
    <div style="display:inline-block;margin-top:15px;padding:8px 24px;border-radius:20px;background:{status_color};color:#fff;font-weight:700;font-size:14px">{status_label}</div>
  </div>

  <!-- Summary Bar -->
  <div class="flex-bar" class="flex-bar" style="display:flex;background:#f8f9fa;border-bottom:1px solid #eee;padding:0">
    <div class="flex-cell" class="flex-cell" style="flex:1;padding:20px;text-align:center;border-right:1px solid #eee">
      <div style="font-size:28px;font-weight:700;color:{'#e74c3c' if total_redirect_issues else '#27ae60'}">{total_redirect_issues}</div>
      <div style="font-size:12px;color:#666;margin-top:4px">Redirect Issues</div>
    </div>
    <div class="flex-cell" class="flex-cell" style="flex:1;padding:20px;text-align:center;border-right:1px solid #eee">
      <div style="font-size:28px;font-weight:700;color:{'#e74c3c' if total_index_alerts else '#27ae60'}">{total_index_alerts}</div>
      <div style="font-size:12px;color:#666;margin-top:4px">Indexing Alerts</div>
    </div>
    <div class="flex-cell" class="flex-cell" style="flex:1;padding:20px;text-align:center">
      <div style="font-size:28px;font-weight:700;color:{'#e74c3c' if total_link_alerts else '#27ae60'}">{total_link_alerts}</div>
      <div style="font-size:12px;color:#666;margin-top:4px">Suspicious Links</div>
    </div>
  </div>

  <div style="padding:30px 40px">

    <!-- Section 1: Redirect Tracker -->
    <h2 style="color:#1a1a2e;border-left:4px solid #3498db;padding-left:12px;margin-top:0">
      🔀 Redirect Tracker
    </h2>
    <p style="color:#666;font-size:13px;margin:0 0 15px">Checks top pages for cross-domain redirects, redirect chains, and spam destinations.</p>
    <div style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin-bottom:4px"><div style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin-bottom:4px"><table style="width:100%;border-collapse:collapse;font-size:13px">
      <thead>
        <tr style="background:#f8f9fa">
          <th style="white-space:nowrap" style="padding:10px 12px;text-align:left;color:#555;font-weight:600">Site</th>
          <th style="white-space:nowrap" style="padding:10px 12px;text-align:left;color:#555;font-weight:600">Original URL</th>
          <th style="white-space:nowrap" style="padding:10px 12px;text-align:left;color:#555;font-weight:600">Final URL</th>
          <th style="white-space:nowrap" style="padding:10px 12px;text-align:left;color:#555;font-weight:600">Issue</th>
        </tr>
      </thead>
      <tbody>{redir_rows}</tbody>
    </table></div></div>

    <div style="height:1px;background:#eee;margin:30px 0"></div>

    <!-- Section 2: Indexing Monitor -->
    <h2 style="color:#1a1a2e;border-left:4px solid #9b59b6;padding-left:12px">
      📊 Indexing Change Monitor
    </h2>
    <p style="color:#666;font-size:13px;margin:0 0 15px">Alerts when daily indexed page count changes by more than 30% vs previous day.</p>
    <div style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin-bottom:4px"><div style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin-bottom:4px"><table style="width:100%;border-collapse:collapse;font-size:13px">
      <thead>
        <tr style="background:#f8f9fa">
          <th style="white-space:nowrap" style="padding:10px 12px;text-align:left;color:#555;font-weight:600">Site</th>
          <th style="white-space:nowrap" style="padding:10px 12px;text-align:center;color:#555;font-weight:600">Yesterday</th>
          <th style="white-space:nowrap" style="padding:10px 12px;text-align:center;color:#555;font-weight:600">Today</th>
          <th style="white-space:nowrap" style="padding:10px 12px;text-align:center;color:#555;font-weight:600">Change</th>
          <th style="white-space:nowrap" style="padding:10px 12px;text-align:center;color:#555;font-weight:600">Status</th>
        </tr>
      </thead>
      <tbody>{idx_rows}</tbody>
    </table></div></div>

    <div style="height:1px;background:#eee;margin:30px 0"></div>

    <!-- Section 3: External Links -->
    <h2 style="color:#1a1a2e;border-left:4px solid #e67e22;padding-left:12px">
      🔗 External Links Monitor
    </h2>
    <p style="color:#666;font-size:13px;margin:0 0 15px">Detects new outbound external links on your pages — suspicious links may indicate spam injection.</p>
    <div style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin-bottom:4px"><div style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin-bottom:4px"><table style="width:100%;border-collapse:collapse;font-size:13px">
      <thead>
        <tr style="background:#f8f9fa">
          <th style="white-space:nowrap" style="padding:10px 12px;text-align:left;color:#555;font-weight:600">Site</th>
          <th style="white-space:nowrap" style="padding:10px 12px;text-align:left;color:#555;font-weight:600">Type</th>
          <th style="white-space:nowrap" style="padding:10px 12px;text-align:left;color:#555;font-weight:600">Link URL</th>
        </tr>
      </thead>
      <tbody>{link_rows}</tbody>
    </table></div></div>

    <!-- Note about incoming backlinks -->
    <div style="margin-top:20px;padding:15px 20px;background:#fff8e1;border-radius:8px;border-left:4px solid #f1c40f">
      <strong>💡 Incoming Backlinks:</strong> To track new backlinks <em>to</em> your sites, 
      connect an Ahrefs, SEMrush, or Moz API key. This is currently monitoring outbound links on your pages.
    </div>

  </div>

  <!-- Footer -->
  <div style="background:#1a1a2e;color:#a0b4d0;padding:20px 40px;text-align:center;font-size:12px">
    Advanced SEO Monitor &nbsp;|&nbsp; Auto-generated daily at 9:15 AM PKT &nbsp;|&nbsp; Reply to this chat in VS Code Copilot
  </div>
</div>
</body>
</html>"""
    return html


# ── Email ─────────────────────────────────────────────────────────────────────
def send_email(html: str, any_alert: bool):
    efrom = CONFIG["email_from"]
    epw   = CONFIG["email_password"]
    if not efrom or not epw:
        print("   ⚠️  Email not configured.")
        return
    icon    = "🚨 ALERT" if any_alert else "✅ All Clear"
    subject = f"{icon} — Advanced SEO Monitor ({date.today().strftime('%d %b %Y')})"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = efrom
    msg["To"]      = CONFIG["email_to"]
    msg["Cc"]      = CONFIG["email_cc"]
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        with smtplib.SMTP(CONFIG["smtp_server"], CONFIG["smtp_port"]) as s:
            s.starttls()
            s.login(efrom, epw)
            s.sendmail(efrom, [CONFIG["email_to"], CONFIG["email_cc"]], msg.as_bytes())
        print(f"   ✅ Email sent to {CONFIG['email_to']} (CC: {CONFIG['email_cc']})")
    except Exception as e:
        print(f"   ❌ Email failed: {e}")


def send_slack_blocks(blocks: list, fallback: str):
    webhook = CONFIG["slack_webhook"]
    if not webhook:
        return
    try:
        requests.post(webhook, json={"blocks": blocks, "text": fallback}, timeout=10)
        print("   \u2705 Slack summary sent")
    except Exception as e:
        print(f"   \u26a0\ufe0f  Slack failed: {e}")


def send_slack(text: str):
    webhook = CONFIG["slack_webhook"]
    if not webhook:
        return
    try:
        requests.post(webhook, json={"text": text}, timeout=10)
    except Exception:
        pass


# ── Main ──────────────────────────────────────────────────────────────────────
def run():
    run_date = datetime.now().strftime("%A, %d %B %Y — %I:%M %p")
    print("=" * 60)
    print("  ADVANCED SEO MONITOR")
    print(f"  {run_date}")
    print("=" * 60)

    db      = init_db()
    service = get_gsc_service()
    if not service:
        return

    SITES = get_sites_from_gsc(service)
    redirect_results  = []
    indexing_results  = []
    link_results      = []

    for site_url in SITES:
        domain = urlparse(site_url).netloc.replace("www.", "")
        print(f"\n🔍 {domain}")

        # Get top pages from GSC
        print(f"   Fetching top pages...", end=" ", flush=True)
        pages = get_top_pages(service, site_url, n=CONFIG["top_pages"])
        print(f"{len(pages)} pages")

        # 1. Redirects (only check top 5 pages for speed)
        print(f"   Checking redirects...", end=" ", flush=True)
        redir = check_redirects(site_url, pages[:CONFIG["redirect_check_pages"]], db)
        redirect_results.append({"site": domain, "issues": redir})
        print(f"{len(redir)} issues")

        # 2. Indexing
        print(f"   Checking indexing changes...", end=" ", flush=True)
        idx = check_indexing(service, site_url, db)
        indexing_results.append(idx)
        change_str = f"{idx.get('change_pct', 0):+.1f}%"
        alert_str  = " 🚨 ALERT" if idx.get("alert") else ""
        print(f"{idx.get('today', 0)} pages ({change_str}){alert_str}")

        # 3. External links
        print(f"   Scanning external links...", end=" ", flush=True)
        links = check_external_links(site_url, pages, db)
        link_results.append(links)
        new_label = f" | {len(links['suspicious_new'])} SUSPICIOUS 🚨" if links["suspicious_new"] else ""
        print(f"{links['total_current']} outbound, {links['new_count']} new{new_label}")

    # Summary
    total_redir  = sum(len(r["issues"]) for r in redirect_results)
    total_idx    = sum(1 for r in indexing_results if r.get("alert"))
    total_sus    = sum(1 for r in link_results if r.get("alert"))
    any_alert    = bool(total_redir or total_idx or total_sus)

    print("\n" + "=" * 60)
    print(f"  Redirect Issues:   {total_redir}")
    print(f"  Indexing Alerts:   {total_idx}")
    print(f"  Suspicious Links:  {total_sus}")
    print("=" * 60)

    # Build & send email
    print("\n📧 Sending email report...")
    html = build_email(redirect_results, indexing_results, link_results, run_date)
    send_email(html, any_alert)

    # Slack summary
    icon = "🚨" if any_alert else "✅"
    send_slack(
        f"{icon} *Advanced SEO Monitor — {date.today().strftime('%d %b %Y')}*\n"
        f"Redirect Issues: {total_redir} | Indexing Alerts: {total_idx} | Suspicious Links: {total_sus}\n"
        f"_Full report emailed to {CONFIG['email_to']}_"
    )

    db.close()
    print("\n✅ Advanced Monitor complete.")


if __name__ == "__main__":
    run()
