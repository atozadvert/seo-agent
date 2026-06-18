# SEO Guardian — Master Implementation Plan

**Owner:** atozadvert.com  
**Stack:** Python + Streamlit + SQLite  
**Target:** Railway hosting + Slack + WhatsApp + Competitor tracking + Android APK  
**Report email:** info@atozadvert.com

---

## PHASE 1 — Live Hosting on Railway (Do This First)

Railway is the fastest path to a live URL. It gives you HTTPS, custom domain, always-on, and free tier ($5/mo free credits).

### Step 1 — Prepare your project for Railway

Create a `Procfile` in your project root:
```
web: streamlit run dashboard.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
```

Create `requirements.txt` if not already complete:
```
streamlit
plotly
pandas
requests
python-dotenv
google-auth
google-auth-oauthlib
google-auth-httplib2
google-api-python-client
```

Create `runtime.txt`:
```
python-3.11
```

### Step 2 — Push to GitHub

```bash
git init
git add .
git commit -m "Initial SEO Guardian commit"
git remote add origin https://github.com/YOURUSERNAME/seo-guardian.git
git push -u origin main
```

> Important: Add `.env` and `token.pickle` and `*.json` (OAuth secrets) to `.gitignore`. Never push secrets.

### Step 3 — Deploy on Railway

1. Go to https://railway.app → Sign in with GitHub
2. Click **New Project → Deploy from GitHub repo**
3. Select your `seo-guardian` repo
4. Railway auto-detects Python and runs your `Procfile`
5. Click **Variables** tab → add all your `.env` values:
   - `EMAIL_FROM`
   - `EMAIL_PASSWORD`
   - `SLACK_WEBHOOK`
   - `SMTP_SERVER`
   - `SMTP_PORT`
   - etc.

### Step 4 — Google OAuth on Railway (critical step)

Your `token.pickle` file is a local OAuth token. On Railway (cloud server), you can't run the browser flow. Convert to Service Account instead:

1. Go to https://console.cloud.google.com/apis/credentials
2. Create a **Service Account** → Download JSON key
3. In Google Search Console → Settings → Users and permissions → Add the service account email as Owner
4. In your code, replace `token.pickle` auth with:

```python
from google.oauth2 import service_account
SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']
creds = service_account.Credentials.from_service_account_file(
    'service_account.json', scopes=SCOPES
)
```

5. Upload `service_account.json` to Railway as an environment variable (base64-encode the JSON):
```bash
base64 -i service_account.json | tr -d '\n'
```
Then in Railway Variables: `GSC_SERVICE_ACCOUNT_JSON = <base64 string>`

In code, decode at runtime:
```python
import base64, json, os
sa_json = json.loads(base64.b64decode(os.environ['GSC_SERVICE_ACCOUNT_JSON']))
creds = service_account.Credentials.from_service_account_info(sa_json, scopes=SCOPES)
```

### Step 5 — Custom Domain (optional)

In Railway → Settings → Domains → Add Custom Domain → Point your DNS CNAME to Railway's URL.

Example: `seo.atozadvert.com`

### Step 6 — Schedule your scripts on Railway (Cron Jobs)

Railway supports cron jobs. Add additional services in your `railway.toml`:

```toml
[deploy]
startCommand = "streamlit run dashboard.py --server.port $PORT --server.address 0.0.0.0 --server.headless true"

[[cronJobs]]
schedule = "0 6 * * *"
command = "python seo_guardian.py"

[[cronJobs]]
schedule = "0 7 * * *"
command = "python rank_tracker.py"

[[cronJobs]]
schedule = "*/30 * * * *"
command = "python uptime_monitor.py"
```

> This replaces Windows Task Scheduler. Scripts run daily at 6 AM and 7 AM PKT (UTC+5 = 1 AM and 2 AM UTC).

---

## PHASE 2 — Slack Bot (already partially working)

Your project already sends Slack webhooks. Upgrade it to a full two-way bot with slash commands.

### What to build

| Command | Action |
|---|---|
| `/seo audit [site]` | Triggers `seo_guardian.py` for one site |
| `/seo alerts` | Returns current alert summary |
| `/seo report` | Generates and emails the weekly report |
| `/seo uptime` | Returns live uptime status for all sites |
| `/seo add [domain]` | Adds a new site to monitoring |
| `/seo rank [site]` | Shows current keyword positions for a site |

### Setup Steps

**1. Create a Slack App**
- Go to https://api.slack.com/apps → Create New App → From Scratch
- Name: "SEO Guardian"
- Select your workspace

**2. Enable Slash Commands**
- In your app → Features → Slash Commands → Create New Command
- Command: `/seo`
- Request URL: `https://YOUR-RAILWAY-URL/slack/command`
- Description: "SEO Guardian agent commands"

**3. Add a Flask endpoint to your project (`slack_bot.py`):**

```python
from flask import Flask, request, jsonify
import subprocess, threading, os

app = Flask(__name__)
SLACK_TOKEN = os.environ.get("SLACK_SIGNING_SECRET")

@app.route("/slack/command", methods=["POST"])
def slack_command():
    text = request.form.get("text", "").strip()
    response_url = request.form.get("response_url")
    
    if text.startswith("audit"):
        site = text.replace("audit", "").strip()
        threading.Thread(target=run_audit, args=(site, response_url)).start()
        return jsonify({"text": f"🔍 Starting audit for {site or 'all sites'}... I'll respond shortly."})
    
    elif text == "alerts":
        return jsonify({"text": get_alerts_summary()})
    
    elif text == "uptime":
        return jsonify({"text": get_uptime_summary()})
    
    elif text == "report":
        threading.Thread(target=send_report, args=(response_url,)).start()
        return jsonify({"text": "📧 Generating report and sending to info@atozadvert.com..."})
    
    elif text.startswith("add"):
        domain = text.replace("add", "").strip()
        add_site_to_monitoring(domain)
        return jsonify({"text": f"✅ Added {domain} to monitoring."})
    
    return jsonify({"text": "Unknown command. Try: audit, alerts, uptime, report, add [domain]"})

if __name__ == "__main__":
    app.run(port=5001)
```

**4. Run both Streamlit and Flask**

In Railway, use a startup script `start.sh`:
```bash
#!/bin/bash
python slack_bot.py &
streamlit run dashboard.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
```

Update your `Procfile`:
```
web: bash start.sh
```

**5. Add Bot Token Scopes in Slack App**
- `commands` — slash commands
- `chat:write` — send messages
- `incoming-webhook` — existing webhook notifications

**6. Install to Workspace**
- OAuth & Permissions → Install to Workspace → Copy Bot Token
- Add `SLACK_BOT_TOKEN` to Railway environment variables

---

## PHASE 3 — WhatsApp Notifications (Safest Method)

The safest, most stable WhatsApp integration without getting banned is **Twilio WhatsApp API** (official Meta partner, fully legal).

### Why Twilio and not other methods
- No risk of ban (official WhatsApp Business API)
- Free sandbox for testing (20 messages/day free)
- Paid: ~$0.005 per message (very cheap)
- Works reliably in Pakistan/UAE

### Setup Steps

**1. Sign up at https://twilio.com**
- Create a free account
- Go to Messaging → Try WhatsApp → WhatsApp Sandbox

**2. Activate your sandbox**
- Send the join code from your WhatsApp to the sandbox number
- Add `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `MY_WHATSAPP_NUMBER` to Railway env vars

**3. Add WhatsApp alerts to your project (`whatsapp_alerts.py`):**

```python
from twilio.rest import Client
import os

def send_whatsapp_alert(message: str):
    """Send WhatsApp alert for critical events."""
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token  = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
    to_number   = os.environ.get("MY_WHATSAPP_NUMBER")  # e.g. whatsapp:+923001234567
    
    if not all([account_sid, auth_token, to_number]):
        return
    
    client = Client(account_sid, auth_token)
    client.messages.create(
        body=message,
        from_=from_number,
        to=to_number
    )

# Example usage in uptime_monitor.py when site goes down:
# send_whatsapp_alert(f"🚨 SITE DOWN: {domain} has been unreachable for 5+ minutes.")
```

**4. Trigger WhatsApp for these events:**

| Event | Message |
|---|---|
| Site down | 🚨 SITE DOWN: `{domain}` — down for 5+ min |
| Site back up | ✅ SITE UP: `{domain}` — back online |
| Rank drop >5 positions | 📉 RANK DROP: `{keyword}` on `{site}` dropped from #{old} to #{new} |
| Suspicious keyword detected | ⚠️ SUSPICIOUS: `{keyword}` on `{site}` |

**5. Go live (beyond sandbox)**
- Apply for WhatsApp Business API access in Twilio console (~1-3 days approval)
- Use your own business number as sender
- Cost: ~$0.005/message + $5-15/month for WhatsApp Business API

---

## PHASE 4 — Competitor Tracking (Suggestion #5)

Track 2-3 competitor domains per site automatically alongside your own rankings.

### Add to `rank_tracker.py`

```python
COMPETITOR_MAP = {
    "atozappliancesrepair.com": ["dubaiappliancerepair.com", "fixit.ae"],
    "ppcexpertsdubai.com":      ["digitallinks.ae", "nexa.ae"],
    "silverpainters.com":       ["dubaipainters.ae", "houseofpainting.ae"],
    # Add more as needed
}

def track_competitor_rankings(keyword, competitor_domain):
    """Use SERP API or ScrapingBee to check competitor position."""
    # Option A: ValueSERP API (free tier: 100 searches/month)
    # Option B: ScrapingBee (cheaper, scrape Google results)
    # Option C: DataForSEO (most accurate, ~$0.001/request)
    pass
```

Recommended free API: **ValueSERP** — 100 free searches/month, enough for basic competitor tracking.

Add `COMPETITOR_ENABLED=true` and `VALUESERP_API_KEY=xxx` to your `.env`.

---

## PHASE 5 — AI-Powered Improvement Suggestions (Suggestion #7)

After every audit, auto-generate "what to fix this week" recommendations using Claude API.

### Add `ai_recommendations.py`:

```python
import anthropic, os

def generate_recommendations(site_data: dict) -> str:
    """Generate actionable SEO recommendations from audit data."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
    prompt = f"""
    You are an SEO expert. Based on this audit data for {site_data['site']}, 
    give me exactly 5 specific, actionable improvement steps ranked by priority.
    
    Data:
    - Average keyword position: {site_data.get('avg_position', 'N/A')}
    - Rank drops this week: {site_data.get('drops', [])}
    - Technical issues: {site_data.get('technical_issues', [])}
    - Page speed: {site_data.get('page_speed', 'N/A')}s
    - Suspicious keywords: {site_data.get('suspicious_count', 0)}
    
    Format: numbered list, each step under 2 sentences. Be specific.
    """
    
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text
```

Add `ANTHROPIC_API_KEY` to Railway env vars. Include recommendations section in the daily email report.

---

## PHASE 6 — Add Site from Frontend (Suggestion #8)

Add a form to the Streamlit dashboard to add new sites without editing code.

### Add to `dashboard.py` (in the All Sites page):

```python
with st.expander("➕ Add new site to monitoring"):
    with st.form("add_site_form"):
        new_domain = st.text_input("Domain (e.g. example.com)")
        new_category = st.selectbox("Category", [
            "Digital Marketing", "E-Commerce", "Legal", "Cleaning", 
            "Painting", "Appliance Repair", "Other"
        ])
        new_location = st.selectbox("Location", ["Dubai", "UAE", "Pakistan", "Global"])
        keywords_raw = st.text_area("Target keywords (one per line)")
        submitted = st.form_submit_button("Add Site")
        
        if submitted and new_domain:
            keywords = [k.strip() for k in keywords_raw.splitlines() if k.strip()]
            # Save to DB
            conn.execute("""
                INSERT OR REPLACE INTO managed_sites (domain, category, location, added_date)
                VALUES (?, ?, ?, date('now'))
            """, (new_domain, new_category, new_location))
            # Save keywords
            for kw in keywords:
                conn.execute("""
                    INSERT OR IGNORE INTO site_keywords (site, keyword)
                    VALUES (?, ?)
                """, (new_domain, kw))
            conn.commit()
            st.success(f"✅ {new_domain} added. Will be included in next audit.")
```

---

## PHASE 7 — Keyword Cannibalization Detector (Suggestion #9)

Find pages on the same site competing for the same keyword.

### Add `cannibalization_checker.py`:

```python
def find_cannibalization(service, site_url: str) -> list:
    """Find keywords where multiple pages rank in top 20."""
    results = service.searchanalytics().query(
        siteUrl=site_url,
        body={
            "startDate": "2025-01-01",
            "endDate": "2025-12-31",
            "dimensions": ["query", "page"],
            "rowLimit": 5000
        }
    ).execute()
    
    keyword_pages = {}
    for row in results.get("rows", []):
        kw, page = row["keys"]
        if row.get("position", 99) <= 20:
            keyword_pages.setdefault(kw, []).append({
                "page": page, 
                "position": row["position"],
                "clicks": row.get("clicks", 0)
            })
    
    # Find keywords with 2+ competing pages
    cannibalized = {
        kw: pages for kw, pages in keyword_pages.items() 
        if len(pages) >= 2
    }
    return cannibalized
```

---

## PHASE 8 — Monthly Auto-Report to info@atozadvert.com (Suggestion #10)

Email delivery is already built. Change the schedule to also trigger a monthly summary.

### Update cron in `railway.toml`:

```toml
# Daily report
[[cronJobs]]
schedule = "0 4 * * *"
command = "python seo_guardian.py"

# Monthly report (1st of every month at 7 AM)
[[cronJobs]]
schedule = "0 7 1 * *"
command = "python monthly_report.py"
```

### Create `monthly_report.py`:

```python
"""
Generates and emails a full monthly summary to info@atozadvert.com
Covers: all sites, rank trends, top keywords, technical health, recommendations
"""

def generate_monthly_report():
    # Pull 30 days of data from SQLite
    # Generate HTML with charts (use matplotlib inline as base64 images)
    # Email to info@atozadvert.com
    # Subject: "SEO Guardian Monthly Report — [Month Year]"
    pass
```

---

## PHASE 9 — Core Web Vitals History Charts (Suggestion #11)

Track LCP, CLS, FID across time using Google PageSpeed Insights API (free).

### Add to `technical_audit.py`:

```python
def fetch_core_web_vitals(domain: str, api_key: str) -> dict:
    url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {
        "url": f"https://{domain}",
        "key": api_key,
        "strategy": "mobile",
        "category": "performance"
    }
    r = requests.get(url, params=params)
    data = r.json()
    metrics = data.get("loadingExperience", {}).get("metrics", {})
    return {
        "lcp": metrics.get("LARGEST_CONTENTFUL_PAINT_MS", {}).get("percentile"),
        "fid": metrics.get("FIRST_INPUT_DELAY_MS", {}).get("percentile"),
        "cls": metrics.get("CUMULATIVE_LAYOUT_SHIFT_SCORE", {}).get("percentile"),
        "timestamp": datetime.now().isoformat()
    }
```

Save to a `core_web_vitals` table and chart in dashboard.

---

## PHASE 10 — Native Android APK

### Architecture

The cleanest approach: host Streamlit on Railway (done in Phase 1), then wrap it in a native Android WebView app using **Android Studio**.

This gives you a real `.apk` that opens your dashboard like a native app, with:
- App icon on home screen
- Push notifications (via Firebase)
- Offline "last loaded" caching
- No app store required (side-load via APK)

### Step-by-Step APK Build

**1. Install required tools**
- Download Android Studio: https://developer.android.com/studio
- Install Java JDK 17: https://adoptium.net

**2. Create new Android project**
- Open Android Studio → New Project → Empty Views Activity
- Language: Java (simpler for webview)
- Minimum SDK: API 24 (Android 7.0)
- Package name: `com.atozadvert.seoguardian`

**3. Replace `MainActivity.java` with:**

```java
package com.atozadvert.seoguardian;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebChromeClient;

public class MainActivity extends Activity {

    private WebView webView;
    private static final String DASHBOARD_URL = "https://YOUR-RAILWAY-URL.up.railway.app";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        webView = findViewById(R.id.webView);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);

        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient());
        webView.loadUrl(DASHBOARD_URL);
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
```

**4. Update `activity_main.xml`:**

```xml
<?xml version="1.0" encoding="utf-8"?>
<RelativeLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent">

    <WebView
        android:id="@+id/webView"
        android:layout_width="match_parent"
        android:layout_height="match_parent"/>

</RelativeLayout>
```

**5. Update `AndroidManifest.xml` — add internet permission:**

```xml
<uses-permission android:name="android.permission.INTERNET"/>
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>

<application
    android:usesCleartextTraffic="true"
    android:hardwareAccelerated="true"
    ...>
```

**6. Add your app icon**
- In Android Studio → Right click `res` → New → Image Asset
- Upload a 1024×1024 PNG of your logo

**7. Add Firebase Push Notifications (optional but useful)**
- Go to https://console.firebase.google.com → New Project
- Add Android app → Package: `com.atozadvert.seoguardian`
- Download `google-services.json` → put in `app/` folder
- In `build.gradle (app)`:
```groovy
implementation 'com.google.firebase:firebase-messaging:23.0.0'
```
- Create `MyFirebaseMessagingService.java` to handle incoming push notifications
- In your Python backend, trigger push notifications via Firebase Admin SDK when site goes down

**8. Build the APK**
- Build → Build Bundle(s) / APK(s) → Build APK(s)
- APK saved to: `app/build/outputs/apk/debug/app-debug.apk`
- Transfer to Android device → Enable "Install from unknown sources" → Install

**9. To distribute to others (future)**
- Build → Generate Signed Bundle / APK → Create keystore
- Upload signed APK to Google Play (free app, $25 one-time developer fee)

---

## Environment Variables Checklist

Add all of these to your Railway project Variables tab:

```
# Email
EMAIL_FROM=your-gmail@gmail.com
EMAIL_PASSWORD=your-app-password
EMAIL_TO=info@atozadvert.com
EMAIL_CC=
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# Slack
SLACK_WEBHOOK=https://hooks.slack.com/services/xxx/xxx/xxx
SLACK_SIGNING_SECRET=xxx

# WhatsApp (Twilio)
TWILIO_ACCOUNT_SID=xxx
TWILIO_AUTH_TOKEN=xxx
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
MY_WHATSAPP_NUMBER=whatsapp:+923xxxxxxxxx

# Google APIs
GOOGLE_PAGESPEED_API=xxx
GSC_SERVICE_ACCOUNT_JSON=<base64 encoded JSON>

# Optional
ANTHROPIC_API_KEY=xxx
VALUESERP_API_KEY=xxx
AHREFS_API_KEY=xxx
SEMRUSH_API_KEY=xxx
```

---

## Implementation Order (Recommended)

| Week | Task | Status |
|---|---|---|
| Week 1 | Railway hosting + GitHub push + GSC service account | Start here |
| Week 1 | Update email to info@atozadvert.com in all CONFIG dicts | Quick |
| Week 2 | Slack bot Flask endpoint + slash commands | Already partial |
| Week 2 | WhatsApp Twilio setup + uptime alerts | Easy |
| Week 3 | Add site form in Streamlit frontend | Easy |
| Week 3 | Competitor tracking with ValueSERP | Medium |
| Week 4 | AI recommendations with Claude API | Medium |
| Week 4 | Monthly auto-report cron | Easy |
| Month 2 | Android Studio APK | Requires Android Studio setup |
| Month 2 | Firebase push notifications | After APK |

---

## Hosting Alternatives (if Railway has issues)

| Platform | Free Tier | Best For |
|---|---|---|
| **Railway** ✅ | $5 credit/mo | Recommended — always on, easy deploys |
| **Render.com** | Free (sleeps) | Backup option |
| **cPanel** (your existing) | Unlimited | Only if you can run Python processes — most cPanels support it via Passenger WSGI but Streamlit is tricky. Use as domain host + DNS only, let Railway run the app. |
| **hPanel** | Unlimited | Same as cPanel — better as DNS + static host |
| **Vercel** | Free | Only for static sites / Next.js — not suitable for Streamlit |

**Recommended combo:** Railway for the app → your cPanel domain (seo.atozadvert.com) pointing CNAME to Railway URL.

---

*Generated by SEO Guardian planning session — May 2026*
