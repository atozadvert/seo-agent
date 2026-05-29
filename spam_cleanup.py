#!/usr/bin/env python3
"""
WordPress Spam Cleanup Agent
Scans ALL posts/pages for injected gambling/spam keywords and cleans them.
Uses WordPress XML-RPC API (works on Hostinger and other hosts that block REST API Basic Auth).
Also detects rogue admin users and PHP file injections.
Run: python spam_cleanup.py           (dry-run, scan only)
     python spam_cleanup.py --fix     (live cleanup)
"""

import os
import re
import sys
import json
import sqlite3
import smtplib
import requests
import xmlrpc.client
from datetime import datetime
from pathlib import Path
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
    "wp_url":         os.getenv("WP_SITE_URL", "").rstrip("/"),
    "wp_user":        os.getenv("WP_USERNAME", ""),
    "wp_pass":        os.getenv("WP_PASSWORD", ""),
    "email_to":       "info@atozadvert.com",
    "email_cc":       "ziarandhawa841@gmail.com",
    "email_from":     os.getenv("EMAIL_FROM", ""),
    "email_password": os.getenv("EMAIL_PASSWORD", ""),
    "smtp_server":    os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port":      587,
    "slack_webhook":  os.getenv("SLACK_WEBHOOK_URL", ""),
    "db_path":        "seo_guardian.db",
}

# ── Spam patterns to detect and remove ───────────────────────────────────────
SPAM_PATTERNS = [
    # Gambling / slot spam (Indonesian/Japanese SEO hack)
    r'slot\s*gacor', r'togel', r'toto\s*\d*', r'jackpot', r'maxwin',
    r'bocoran\s*slot', r'judi\s*online', r'casino\s*online', r'poker\s*online',
    r'kicau\s*toto', r'bacan\s*toto', r'sengtoto', r'watitoto', r'agen\s*slot',
    r'link\s*slot', r'demo\s*slot', r'situs\s*slot', r'rtp\s*slot',
    # Pharma hack
    r'cheap\s*(viagra|cialis|levitra)', r'buy\s*(viagra|cialis|levitra)',
    r'online\s*pharmacy', r'prescription\s*drugs',
    # Common injected anchor patterns
    r'<a[^>]+>(slot|togel|casino|judi|toto)[^<]*</a>',
    r'href=["\']https?://[^"\']*(?:slot|togel|casino|judi)[^"\']*["\']',
]

# Known WP admin users on this site (anyone NOT in this list is suspicious)
KNOWN_ADMINS = ["ATIFatozapp"]

# ── XML-RPC Client ────────────────────────────────────────────────────────────
def get_wp_client():
    url  = f"{CONFIG['wp_url']}/xmlrpc.php"
    user = CONFIG["wp_user"]
    pw   = CONFIG["wp_pass"]
    transport = xmlrpc.client.SafeTransport() if url.startswith("https") else None
    server = xmlrpc.client.ServerProxy(url, transport=transport, allow_none=True)
    return server, user, pw


def wp_get_posts(post_type: str = "post", page: int = 1, per_page: int = 50) -> list:
    """Fetch posts/pages via XML-RPC wp.getPosts."""
    server, user, pw = get_wp_client()
    try:
        posts = server.wp.getPosts(
            0, user, pw,
            {
                "post_type":   post_type,
                "post_status": "any",
                "number":      per_page,
                "offset":      (page - 1) * per_page,
            },
            ["post_id", "post_title", "post_content", "post_excerpt", "post_status", "post_type"]
        )
        return posts if isinstance(posts, list) else []
    except Exception as e:
        print(f"   ⚠️  XML-RPC getPosts failed: {e}")
        return []


def wp_edit_post(post_id: int, content: str, excerpt: str) -> bool:
    """Update post content via XML-RPC."""
    server, user, pw = get_wp_client()
    try:
        result = server.wp.editPost(
            0, user, pw,
            post_id,
            {"post_content": content, "post_excerpt": excerpt}
        )
        return bool(result)
    except Exception as e:
        print(f"   ⚠️  XML-RPC editPost failed: {e}")
        return False


def wp_get_users() -> list:
    """Get all WordPress users via XML-RPC."""
    server, user, pw = get_wp_client()
    try:
        users = server.wp.getUsers(0, user, pw, {"number": 100})
        return users if isinstance(users, list) else []
    except Exception as e:
        print(f"   ⚠️  XML-RPC getUsers failed: {e}")
        return []


def contains_spam(content: str) -> list:
    """Returns list of matched spam patterns found in content."""
    matches = []
    content_lower = content.lower()
    for pattern in SPAM_PATTERNS:
        if re.search(pattern, content_lower, re.IGNORECASE):
            matches.append(pattern)
    return matches


def clean_spam(content: str) -> tuple[str, int]:
    """Remove injected spam links and text. Returns (cleaned_content, count_removed)."""
    count = 0
    cleaned = content

    # Remove injected anchor tags linking to spam sites
    before = cleaned
    cleaned = re.sub(
        r'<a[^>]+href=["\']https?://[^"\']*(?:slot|togel|casino|judi|toto|gacor|poker)[^"\']*["\'][^>]*>.*?</a>',
        '', cleaned, flags=re.IGNORECASE | re.DOTALL
    )
    count += len(re.findall(r'<a', before)) - len(re.findall(r'<a', cleaned))

    # Remove hidden spam divs/spans (common injection technique)
    cleaned = re.sub(
        r'<(?:div|span|p)[^>]*style=["\'][^"\']*(?:display\s*:\s*none|visibility\s*:\s*hidden)[^"\']*["\'][^>]*>.*?</(?:div|span|p)>',
        '', cleaned, flags=re.IGNORECASE | re.DOTALL
    )

    # Remove inline spam keyword injections (not in real content)
    for pattern in [
        r'\b(slot gacor|togel online|judi online|casino online|poker online)\b[^\n]{0,200}',
        r'https?://[^\s<>"\']+(?:slot|togel|gacor|judi|casino)[^\s<>"\']*',
    ]:
        new = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        if new != cleaned:
            count += 1
            cleaned = new

    return cleaned, count


# ── DB Logging ────────────────────────────────────────────────────────────────
def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS spam_cleanup_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp     TEXT NOT NULL,
            site          TEXT NOT NULL,
            post_id       INTEGER,
            post_title    TEXT,
            post_type     TEXT,
            action        TEXT,
            patterns_found TEXT,
            items_removed  INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    return conn


def log_action(conn, post_id, title, ptype, action, patterns, removed=0):
    conn.execute("""
        INSERT INTO spam_cleanup_log (timestamp, site, post_id, post_title, post_type, action, patterns_found, items_removed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().isoformat(), CONFIG["wp_url"], post_id, title, ptype, action,
          json.dumps(patterns), removed))
    conn.commit()


# ── Scan & Clean Posts ────────────────────────────────────────────────────────
def scan_content_type(conn, post_type: str, dry_run: bool, fix: bool) -> dict:
    print(f"\n   📄 Scanning {post_type}s...")
    page      = 1
    per_page  = 50
    total_scanned  = 0
    total_infected = 0
    total_cleaned  = 0
    infected_list  = []

    while True:
        items = wp_get_posts(post_type, page, per_page)
        if not items:
            break

        for item in items:
            post_id    = int(item.get("post_id", 0))
            title      = item.get("post_title", f"#{post_id}")
            title_text = re.sub(r'<[^>]+>', '', str(title))
            content    = item.get("post_content", "")
            excerpt    = item.get("post_excerpt", "")
            combined   = str(content) + " " + str(excerpt)

            total_scanned += 1
            matches = contains_spam(combined)

            if matches:
                total_infected += 1
                infected_list.append({"id": post_id, "title": title_text, "patterns": matches})
                print(f"      🚨 [{post_id}] {title_text[:50]} — {len(matches)} pattern(s)")

                log_action(conn, post_id, title_text, post_type,
                           "DETECTED" if dry_run else "CLEANING", matches)

                if fix and not dry_run:
                    cleaned_content, removed  = clean_spam(str(content))
                    cleaned_excerpt, removed2 = clean_spam(str(excerpt))
                    total_removed = removed + removed2

                    if cleaned_content != content or cleaned_excerpt != excerpt:
                        ok = wp_edit_post(post_id, cleaned_content, cleaned_excerpt)
                        if ok:
                            total_cleaned += 1
                            print(f"      ✅ Cleaned {total_removed} injections from [{post_id}]")
                            log_action(conn, post_id, title_text, post_type,
                                       "CLEANED", matches, total_removed)
                        else:
                            print(f"      ❌ Failed to update [{post_id}]")

        if len(items) < per_page:
            break
        page += 1

    print(f"      Total: {total_scanned} scanned | {total_infected} infected | {total_cleaned} cleaned")
    return {
        "type":     post_type,
        "scanned":  total_scanned,
        "infected": total_infected,
        "cleaned":  total_cleaned,
        "list":     infected_list,
    }


# ── Check Users ───────────────────────────────────────────────────────────────
def check_users() -> dict:
    print("\n   👤 Checking admin users...")
    users = wp_get_users()
    if not users:
        print("      ⚠️  Could not fetch users")
        return {"error": True, "rogue": []}

    rogue = []
    for u in users:
        username = u.get("username", u.get("user_login", ""))
        email    = u.get("email", u.get("user_email", "unknown"))
        uid      = u.get("user_id", u.get("id", "?"))
        registered = str(u.get("registered", ""))[:10]
        roles    = u.get("roles", [])

        if "administrator" in roles and username not in KNOWN_ADMINS:
            rogue.append({"id": uid, "username": username, "email": email, "registered": registered})
            print(f"      🚨 ROGUE ADMIN: {username} ({email}) — registered {registered}")
        elif "administrator" in roles:
            print(f"      ✅ Known admin: {username}")

    return {"total": len(users), "rogue": rogue}


# ── PHP File Injection Check ──────────────────────────────────────────────────
def check_php_injection() -> dict:
    """
    Checks for known symptoms of PHP file injection via plain HTTP request.
    (Actual file editing requires FTP/SSH — flagged here for manual review)
    """
    print("\n   🔍 Checking for PHP injection symptoms...")
    issues = []

    try:
        r = requests.get(
            f"{CONFIG['wp_url']}/",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=20
        )
        if "Warning" in r.text or "Fatal error" in r.text:
            warnings = re.findall(r'<b>Warning</b>:[^<]+', r.text)[:5]
            includes = re.findall(r'include\([\'"]([^\'"]+)[\'"]\)', r.text)
            issues.append({
                "type":        "PHP Injection (Active)",
                "description": f"PHP warnings on homepage — injected file include detected. Warnings: {len(warnings)}",
                "evidence":    warnings,
                "injected_files": includes,
                "action":      "Check index.php for unexpected include() calls. Remove the injected line and delete the referenced file.",
            })
            print(f"      🚨 PHP injection confirmed! {len(warnings)} warning(s), files: {includes}")
        else:
            print("      ✅ No PHP warnings on homepage")
    except Exception as e:
        print(f"      ⚠️  Could not check homepage: {e}")

    return {"issues": issues}


# ── Notifications ─────────────────────────────────────────────────────────────
def send_slack(message: str):
    if not CONFIG["slack_webhook"]:
        return
    try:
        requests.post(CONFIG["slack_webhook"], json={"text": message}, timeout=10)
    except Exception:
        pass


def send_email(html: str, subject: str):
    efrom = CONFIG["email_from"]
    epw   = CONFIG["email_password"]
    if not efrom or not epw:
        print("   ⚠️  Email not configured")
        return
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
        print(f"   ✅ Report emailed to {CONFIG['email_to']}")
    except Exception as e:
        print(f"   ❌ Email failed: {e}")


def build_report_email(results: dict, dry_run: bool) -> str:
    mode    = "DRY RUN (no changes made)" if dry_run else "LIVE CLEANUP"
    ts      = datetime.now().strftime("%A, %d %b %Y — %I:%M %p")
    site    = CONFIG["wp_url"].replace("https://", "")
    total_infected = sum(r.get("infected", 0) for r in results.get("content", []))
    total_cleaned  = sum(r.get("cleaned", 0) for r in results.get("content", []))
    rogue_admins   = results.get("users", {}).get("rogue", [])
    php_issues     = results.get("php", {}).get("issues", [])

    severity_color = "#e74c3c" if total_infected > 0 or rogue_admins or php_issues else "#27ae60"
    severity_label = "🚨 SPAM DETECTED" if total_infected > 0 else "✅ CLEAN"

    # Content rows
    content_rows = ""
    for r in results.get("content", []):
        content_rows += f"""
        <tr>
            <td style="padding:10px 15px">{r['type'].title()}s</td>
            <td style="padding:10px 15px;text-align:center">{r['scanned']}</td>
            <td style="padding:10px 15px;text-align:center;color:#e74c3c;font-weight:bold">{r['infected']}</td>
            <td style="padding:10px 15px;text-align:center;color:#27ae60;font-weight:bold">{r['cleaned']}</td>
        </tr>"""

    # Infected list
    infected_rows = ""
    for r in results.get("content", []):
        for item in r.get("list", [])[:20]:
            infected_rows += f"""
            <tr style="border-bottom:1px solid #f0f0f0">
                <td style="padding:8px 12px">#{item['id']}</td>
                <td style="padding:8px 12px">{item['title'][:60]}</td>
                <td style="padding:8px 12px;font-size:12px;color:#e74c3c">{len(item['patterns'])} pattern(s)</td>
            </tr>"""

    # Rogue admin rows
    rogue_rows = ""
    for u in rogue_admins:
        rogue_rows += f"""
        <tr style="background:#fff5f5">
            <td style="padding:8px 12px;color:#e74c3c;font-weight:bold">⚠️ {u['username']}</td>
            <td style="padding:8px 12px">{u['email']}</td>
            <td style="padding:8px 12px">{u.get('registered','')[:10]}</td>
        </tr>"""

    # PHP issues
    php_rows = ""
    for issue in php_issues:
        php_rows += f"""
        <div style="background:#fff5f5;border-left:4px solid #e74c3c;padding:12px 15px;margin:8px 0;border-radius:4px">
            <strong style="color:#e74c3c">{issue['type']}</strong><br>
            <span style="font-size:13px;color:#555">{issue['description']}</span><br>
            <span style="font-size:12px;color:#e74c3c;margin-top:5px;display:block">
                ⚡ Action: {issue['action']}
            </span>
        </div>"""

    manual_steps = ""
    if php_issues:
        manual_steps = """
        <div style="background:#fff8e1;border:1px solid #f39c12;border-radius:8px;padding:20px;margin:20px 0">
            <h3 style="color:#f39c12;margin:0 0 12px">⚡ Manual Action Required (PHP Files)</h3>
            <p style="font-size:13px;color:#555;margin:0 0 10px">
                The spam agent cannot edit server PHP files directly. Please do these steps manually:
            </p>
            <ol style="font-size:13px;color:#555;margin:0;padding-left:20px">
                <li style="margin-bottom:8px">Log into cPanel → File Manager → <code>public_html/index.php</code><br>
                    Remove any line with <code>include('old.php')</code> or similar unknown includes</li>
                <li style="margin-bottom:8px">Check <code>.htaccess</code> for unauthorized redirect rules</li>
                <li style="margin-bottom:8px">Check <code>wp-config.php</code> for injected code at top/bottom</li>
                <li style="margin-bottom:8px">Search all PHP files for <code>eval(base64_decode(</code> — delete those lines</li>
                <li style="margin-bottom:8px">Install <strong>Wordfence</strong> plugin and run a full scan</li>
                <li>In Google Search Console → Request <strong>Re-crawl</strong> after cleanup</li>
            </ol>
        </div>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
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
</style><title>Spam Cleanup Report</title></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:Arial,sans-serif">
<div class="outer" style="max-width:800px;margin:0 auto;padding:20px">

    <div style="background:{severity_color};color:#fff;padding:30px;border-radius:12px 12px 0 0;text-align:center">
        <h1 style="margin:0;font-size:24px">🛡️ WordPress Spam Cleanup Report</h1>
        <p style="margin:6px 0 0;opacity:0.9">{site} — {ts}</p>
        <div style="background:rgba(0,0,0,0.2);display:inline-block;padding:6px 18px;border-radius:20px;margin-top:10px;font-size:14px">
            {mode}
        </div>
    </div>

    <!-- Summary -->
    <div style="background:#fff;border:1px solid #e0e0e0;padding:25px">
        <p style="font-size:20px;font-weight:bold;color:{severity_color};margin:0 0 20px">{severity_label}</p>
        <div style="display:flex;gap:12px;flex-wrap:wrap">
            <div class="stat-card" class="stat-card" style="background:#fff5f5;border-radius:8px;padding:15px 20px;text-align:center;flex:1;min-width:100px">
                <div style="font-size:28px;font-weight:bold;color:#e74c3c">{total_infected}</div>
                <div style="font-size:11px;color:#888;text-transform:uppercase">Infected Pages</div>
            </div>
            <div class="stat-card" class="stat-card" style="background:#f0fff4;border-radius:8px;padding:15px 20px;text-align:center;flex:1;min-width:100px">
                <div style="font-size:28px;font-weight:bold;color:#27ae60">{total_cleaned}</div>
                <div style="font-size:11px;color:#888;text-transform:uppercase">Cleaned</div>
            </div>
            <div class="stat-card" class="stat-card" style="background:#{'fff5f5' if rogue_admins else 'f0fff4'};border-radius:8px;padding:15px 20px;text-align:center;flex:1;min-width:100px">
                <div style="font-size:28px;font-weight:bold;color:#{'e74c3c' if rogue_admins else '27ae60'}">{len(rogue_admins)}</div>
                <div style="font-size:11px;color:#888;text-transform:uppercase">Rogue Admins</div>
            </div>
            <div class="stat-card" class="stat-card" style="background:#{'fff5f5' if php_issues else 'f0fff4'};border-radius:8px;padding:15px 20px;text-align:center;flex:1;min-width:100px">
                <div style="font-size:28px;font-weight:bold;color:#{'e74c3c' if php_issues else '27ae60'}">{len(php_issues)}</div>
                <div style="font-size:11px;color:#888;text-transform:uppercase">PHP Issues</div>
            </div>
        </div>
    </div>

    <!-- Content Scan Results -->
    <div style="background:#fff;border:1px solid #e0e0e0;border-top:none;padding:0 25px 20px">
        <h3 style="color:#2c3e50;padding-top:20px">📄 Content Scan Results</h3>
        <div style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin-bottom:4px"><div style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin-bottom:4px"><table style="width:100%;border-collapse:collapse;font-size:14px">
            <tr style="background:#f8f8f8;color:#666">
                <th style="white-space:nowrap" style="padding:10px 15px;text-align:left">Content Type</th>
                <th style="white-space:nowrap" style="padding:10px 15px">Scanned</th>
                <th style="white-space:nowrap" style="padding:10px 15px">Infected</th>
                <th style="white-space:nowrap" style="padding:10px 15px">Cleaned</th>
            </tr>
            {content_rows}
        </table></div></div>

        {"" if not infected_rows else f'''
        <h3 style="color:#e74c3c;margin-top:25px">🚨 Infected Pages/Posts</h3>
        <div style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin-bottom:4px"><div style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin-bottom:4px"><table style="width:100%;border-collapse:collapse;font-size:13px">
            <tr style="background:#fff5f5;color:#666">
                <th style="white-space:nowrap" style="padding:8px 12px;text-align:left">ID</th>
                <th style="white-space:nowrap" style="padding:8px 12px;text-align:left">Title</th>
                <th style="white-space:nowrap" style="padding:8px 12px;text-align:left">Patterns</th>
            </tr>{infected_rows}
        </table></div></div>'''}
    </div>

    <!-- Admin Users -->
    {"" if not rogue_admins else f'''
    <div style="background:#fff;border:1px solid #e0e0e0;border-top:none;padding:20px 25px">
        <h3 style="color:#e74c3c;margin:0 0 12px">⚠️ Rogue Admin Users Detected!</h3>
        <p style="font-size:13px;color:#666;margin:0 0 12px">
            These admin accounts were NOT in your known admins list. 
            Delete them immediately from WP Admin → Users.
        </p>
        <div style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin-bottom:4px"><div style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin-bottom:4px"><table style="width:100%;border-collapse:collapse;font-size:13px">
            <tr style="background:#f8f8f8;color:#666">
                <th style="white-space:nowrap" style="padding:8px 12px;text-align:left">Username</th>
                <th style="white-space:nowrap" style="padding:8px 12px;text-align:left">Email</th>
                <th style="white-space:nowrap" style="padding:8px 12px;text-align:left">Registered</th>
            </tr>{rogue_rows}
        </table></div></div>
    </div>'''}

    <!-- PHP Issues -->
    {"" if not php_issues else f'''
    <div style="background:#fff;border:1px solid #e0e0e0;border-top:none;padding:20px 25px">
        <h3 style="color:#e74c3c;margin:0 0 12px">💉 PHP File Injection Detected</h3>
        {php_rows}
    </div>'''}

    {manual_steps}

    <div style="background:#2c3e50;color:#aaa;padding:20px;border-radius:0 0 12px 12px;text-align:center;font-size:12px">
        SEO Guardian Spam Cleanup Agent · {ts}
    </div>
</div>
</body></html>"""


# ── Main ──────────────────────────────────────────────────────────────────────
def run(dry_run: bool = True, fix: bool = False):
    print("=" * 60)
    print("  WORDPRESS SPAM CLEANUP AGENT")
    print(f"  {datetime.now().strftime('%A, %d %b %Y — %I:%M %p')}")
    print(f"  Mode: {'DRY RUN (scan only)' if dry_run else 'LIVE CLEANUP'}")
    print(f"  Site: {CONFIG['wp_url']}")
    print("=" * 60)

    if not CONFIG["wp_url"] or not CONFIG["wp_user"]:
        print("❌ WP_SITE_URL / WP_USERNAME / WP_PASSWORD not set in .env")
        return

    conn    = init_db(CONFIG["db_path"])
    results = {}

    # 1. Scan posts and pages
    content_results = []
    for ptype in ["post", "page"]:
        r = scan_content_type(conn, ptype, dry_run, fix)
        content_results.append(r)
    results["content"] = content_results

    # 2. Check admin users
    results["users"] = check_users()

    # 3. Check PHP injection symptoms
    results["php"] = check_php_injection()

    # ── Summary ──────────────────────────────────────────────
    total_infected = sum(r["infected"] for r in content_results)
    total_cleaned  = sum(r["cleaned"] for r in content_results)
    rogue_count    = len(results["users"].get("rogue", []))
    php_count      = len(results["php"].get("issues", []))

    print(f"\n{'='*60}")
    print(f"  SCAN COMPLETE")
    print(f"  🚨 Infected content: {total_infected}")
    print(f"  ✅ Cleaned:          {total_cleaned}")
    print(f"  👤 Rogue admins:     {rogue_count}")
    print(f"  💉 PHP issues:       {php_count}")
    print(f"{'='*60}")

    if dry_run and total_infected > 0:
        print(f"\n⚡ To apply cleanup, run:  python spam_cleanup.py --fix")

    # ── Notifications ────────────────────────────────────────
    print("\n📣 Sending report...")

    # Slack summary
    emoji = "🚨" if total_infected > 0 or rogue_count > 0 else "✅"
    send_slack(
        f"{emoji} *Spam Cleanup — {CONFIG['wp_url'].replace('https://','')}'*\n"
        f">Infected content: {total_infected} | Cleaned: {total_cleaned}\n"
        f">Rogue admins: {rogue_count} | PHP issues: {php_count}\n"
        f">Mode: {'DRY RUN' if dry_run else 'LIVE CLEANUP'}"
    )

    # Email report
    html    = build_report_email(results, dry_run)
    subject = f"🛡️ Spam Cleanup {'(Dry Run)' if dry_run else '(Live)'} — {total_infected} infected, {total_cleaned} cleaned"
    preview = f"spam_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(preview, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"   💾 Preview saved: {preview}")
    send_email(html, subject)

    conn.close()
    return results


if __name__ == "__main__":
    dry_run = "--fix" not in sys.argv
    fix     = "--fix" in sys.argv
    if dry_run:
        print("\n💡 Running in DRY RUN mode — no changes will be made.")
        print("   To apply fixes, run:  python spam_cleanup.py --fix\n")
    run(dry_run=dry_run, fix=fix)
