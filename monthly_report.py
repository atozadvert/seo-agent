#!/usr/bin/env python3
"""
Monthly SEO Report Generator
Generates comprehensive monthly summary and emails to info@atozadvert.com
"""

import os
import sqlite3
import smtplib
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load .env
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

CONFIG = {
    "email_to": "info@atozadvert.com",
    "email_cc": "ziarandhawa841@gmail.com",
    "email_from": os.getenv("EMAIL_FROM", ""),
    "email_password": os.getenv("EMAIL_PASSWORD", ""),
    "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port": 587,
    "db_path": os.getenv("DB_PATH", "seo_guardian.db"),
}


def get_monthly_stats(conn):
    """Gather all monthly statistics from database."""
    cursor = conn.cursor()
    
    # Date range (last 30 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    stats = {
        "period": f"{start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')}",
        "month": end_date.strftime('%B %Y'),
    }
    
    # Total suspicious keywords detected
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM suspicious_log 
            WHERE date >= date('now', '-30 days')
        """)
        stats["total_suspicious"] = cursor.fetchone()[0] or 0
    except:
        stats["total_suspicious"] = 0
    
    # Sites monitored
    try:
        cursor.execute("SELECT COUNT(DISTINCT site) FROM daily_stats")
        stats["sites_monitored"] = cursor.fetchone()[0] or 0
    except:
        stats["sites_monitored"] = 0
    
    # Total clicks (last 30 days)
    try:
        cursor.execute("""
            SELECT SUM(total_clicks) FROM daily_stats 
            WHERE date >= date('now', '-30 days')
        """)
        stats["total_clicks"] = cursor.fetchone()[0] or 0
    except:
        stats["total_clicks"] = 0
    
    # Average daily clicks
    stats["avg_daily_clicks"] = round(stats["total_clicks"] / 30, 1) if stats["total_clicks"] > 0 else 0
    
    # Top performing sites (by clicks)
    try:
        cursor.execute("""
            SELECT site, SUM(total_clicks) as clicks 
            FROM daily_stats 
            WHERE date >= date('now', '-30 days')
            GROUP BY site 
            ORDER BY clicks DESC 
            LIMIT 5
        """)
        stats["top_sites"] = cursor.fetchall()
    except:
        stats["top_sites"] = []
    
    # Most problematic sites (by suspicious keywords)
    try:
        cursor.execute("""
            SELECT site, COUNT(*) as sus_count 
            FROM suspicious_log 
            WHERE date >= date('now', '-30 days')
            GROUP BY site 
            ORDER BY sus_count DESC 
            LIMIT 5
        """)
        stats["problem_sites"] = cursor.fetchall()
    except:
        stats["problem_sites"] = []
    
    # Uptime statistics
    try:
        cursor.execute("""
            SELECT site, 
                   SUM(is_up)*100.0/COUNT(*) as uptime_pct,
                   COUNT(*) as checks
            FROM uptime_log 
            WHERE timestamp >= datetime('now', '-30 days')
            GROUP BY site 
            ORDER BY uptime_pct ASC
        """)
        stats["uptime_stats"] = cursor.fetchall()
    except:
        stats["uptime_stats"] = []
    
    # Rank changes
    try:
        cursor.execute("""
            SELECT COUNT(*) as drops 
            FROM rank_alerts 
            WHERE alert_type='DROP' AND timestamp >= datetime('now', '-30 days')
        """)
        stats["rank_drops"] = cursor.fetchone()[0] or 0
        
        cursor.execute("""
            SELECT COUNT(*) as gains 
            FROM rank_alerts 
            WHERE alert_type='GAIN' AND timestamp >= datetime('now', '-30 days')
        """)
        stats["rank_gains"] = cursor.fetchone()[0] or 0
    except:
        stats["rank_drops"] = 0
        stats["rank_gains"] = 0
    
    return stats


def build_monthly_email(stats):
    """Build HTML email for monthly report."""
    
    # Top sites table
    top_sites_rows = ""
    for i, (site, clicks) in enumerate(stats["top_sites"], 1):
        top_sites_rows += f"""
        <tr style="background:{'#f9f9f9' if i % 2 == 0 else '#fff'};">
            <td style="padding:8px;">{i}. {site}</td>
            <td style="padding:8px;text-align:right;font-weight:700;">{int(clicks):,}</td>
        </tr>"""
    
    # Problem sites table
    problem_sites_rows = ""
    for i, (site, count) in enumerate(stats["problem_sites"], 1):
        problem_sites_rows += f"""
        <tr style="background:{'#fef9f9' if i % 2 == 0 else '#fff'};">
            <td style="padding:8px;">{i}. {site}</td>
            <td style="padding:8px;text-align:right;font-weight:700;color:#e74c3c;">{int(count)}</td>
        </tr>"""
    
    # Uptime table
    uptime_rows = ""
    for site, uptime_pct, checks in stats["uptime_stats"][:10]:
        site_clean = site.replace("https://", "").rstrip("/")
        color = "#27ae60" if uptime_pct >= 99 else "#e67e22" if uptime_pct >= 95 else "#e74c3c"
        uptime_rows += f"""
        <tr>
            <td style="padding:8px;">{site_clean}</td>
            <td style="padding:8px;text-align:right;font-weight:700;color:{color};">{uptime_pct:.1f}%</td>
            <td style="padding:8px;text-align:right;color:#888;">{int(checks)}</td>
        </tr>"""
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif;">
<div style="max-width:700px;margin:30px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.1);">

  <!-- HEADER -->
  <div style="background:linear-gradient(135deg, #667eea 0%, #764ba2 100%);padding:40px 30px;text-align:center;">
    <div style="font-size:48px;margin-bottom:10px;">📊</div>
    <h1 style="margin:0;color:#fff;font-size:28px;letter-spacing:0.5px;">
        Monthly SEO Report
    </h1>
    <p style="margin:10px 0 0;color:rgba(255,255,255,0.9);font-size:16px;">
        {stats['month']}
    </p>
    <p style="margin:5px 0 0;color:rgba(255,255,255,0.7);font-size:13px;">
        {stats['period']}
    </p>
  </div>

  <!-- BODY -->
  <div style="padding:30px;">

    <!-- EXECUTIVE SUMMARY -->
    <h2 style="margin:0 0 20px;font-size:18px;color:#333;border-bottom:2px solid #667eea;padding-bottom:8px;">
        📈 Executive Summary
    </h2>
    
    <table style="width:100%;margin-bottom:30px;">
      <tr>
        <td style="padding:15px;background:#f0f4ff;border-radius:8px;text-align:center;width:25%;">
            <div style="font-size:32px;font-weight:700;color:#667eea;">{stats['sites_monitored']}</div>
            <div style="font-size:12px;color:#666;margin-top:5px;">Sites Monitored</div>
        </td>
        <td width="10"></td>
        <td style="padding:15px;background:#f0fdf4;border-radius:8px;text-align:center;width:25%;">
            <div style="font-size:32px;font-weight:700;color:#27ae60;">{stats['total_clicks']:,}</div>
            <div style="font-size:12px;color:#666;margin-top:5px;">Total Clicks</div>
        </td>
        <td width="10"></td>
        <td style="padding:15px;background:#fef9f9;border-radius:8px;text-align:center;width:25%;">
            <div style="font-size:32px;font-weight:700;color:#e74c3c;">{stats['total_suspicious']}</div>
            <div style="font-size:12px;color:#666;margin-top:5px;">Suspicious Keywords</div>
        </td>
        <td width="10"></td>
        <td style="padding:15px;background:#fff8f0;border-radius:8px;text-align:center;width:25%;">
            <div style="font-size:32px;font-weight:700;color:#f39c12;">{stats['avg_daily_clicks']}</div>
            <div style="font-size:12px;color:#666;margin-top:5px;">Avg Daily Clicks</div>
        </td>
      </tr>
    </table>

    <!-- TOP PERFORMING SITES -->
    <h2 style="margin:30px 0 15px;font-size:18px;color:#333;border-bottom:2px solid #27ae60;padding-bottom:8px;">
        🏆 Top Performing Sites
    </h2>
    <table style="width:100%;border-collapse:collapse;margin-bottom:30px;">
      <tr style="background:#f0fdf4;">
        <th style="padding:10px;text-align:left;border-bottom:2px solid #27ae60;">Site</th>
        <th style="padding:10px;text-align:right;border-bottom:2px solid #27ae60;">Total Clicks</th>
      </tr>
      {top_sites_rows if top_sites_rows else '<tr><td colspan="2" style="padding:15px;text-align:center;color:#888;">No data available</td></tr>'}
    </table>

    <!-- RANK CHANGES -->
    <h2 style="margin:30px 0 15px;font-size:18px;color:#333;border-bottom:2px solid #f39c12;padding-bottom:8px;">
        📊 Ranking Performance
    </h2>
    <div style="background:#fff8f0;border-radius:8px;padding:20px;margin-bottom:30px;">
        <table style="width:100%;">
          <tr>
            <td style="text-align:center;padding:10px;">
                <div style="font-size:36px;font-weight:700;color:#27ae60;">↑ {stats['rank_gains']}</div>
                <div style="font-size:13px;color:#666;">Position Gains</div>
            </td>
            <td style="text-align:center;padding:10px;">
                <div style="font-size:36px;font-weight:700;color:#e74c3c;">↓ {stats['rank_drops']}</div>
                <div style="font-size:13px;color:#666;">Position Drops</div>
            </td>
          </tr>
        </table>
    </div>

    <!-- PROBLEM SITES -->
    {f'''
    <h2 style="margin:30px 0 15px;font-size:18px;color:#333;border-bottom:2px solid #e74c3c;padding-bottom:8px;">
        🚨 Sites Requiring Attention
    </h2>
    <table style="width:100%;border-collapse:collapse;margin-bottom:30px;">
      <tr style="background:#fef9f9;">
        <th style="padding:10px;text-align:left;border-bottom:2px solid #e74c3c;">Site</th>
        <th style="padding:10px;text-align:right;border-bottom:2px solid #e74c3c;">Suspicious Keywords</th>
      </tr>
      {problem_sites_rows}
    </table>
    ''' if stats['problem_sites'] else ''}

    <!-- UPTIME PERFORMANCE -->
    <h2 style="margin:30px 0 15px;font-size:18px;color:#333;border-bottom:2px solid #3498db;padding-bottom:8px;">
        🟢 Uptime Performance
    </h2>
    <table style="width:100%;border-collapse:collapse;margin-bottom:30px;">
      <tr style="background:#f0f8ff;">
        <th style="padding:10px;text-align:left;border-bottom:2px solid #3498db;">Site</th>
        <th style="padding:10px;text-align:right;border-bottom:2px solid #3498db;">Uptime %</th>
        <th style="padding:10px;text-align:right;border-bottom:2px solid #3498db;">Checks</th>
      </tr>
      {uptime_rows if uptime_rows else '<tr><td colspan="3" style="padding:15px;text-align:center;color:#888;">No uptime data available</td></tr>'}
    </table>

    <!-- RECOMMENDATIONS -->
    <div style="background:#fff8f0;border:2px solid #f39c12;border-radius:8px;padding:20px;margin-top:30px;">
      <h3 style="margin:0 0 15px;color:#f39c12;font-size:16px;">💡 Key Recommendations</h3>
      <ol style="margin:0;padding-left:20px;font-size:14px;color:#444;line-height:1.8;">
        <li>Continue monitoring suspicious keywords and investigate any hacked sites immediately</li>
        <li>Focus SEO efforts on top-performing sites to maximize ROI</li>
        <li>Address any sites with uptime below 99% - investigate hosting issues</li>
        <li>Review rank drops and optimize content for affected keywords</li>
        <li>Maintain regular backups and security scans for all sites</li>
      </ol>
    </div>

    <!-- FOOTER -->
    <div style="margin-top:40px;padding-top:20px;border-top:2px solid #eee;text-align:center;color:#999;font-size:12px;">
        <p style="margin:5px 0;">SEO Guardian — Automated Monthly Report</p>
        <p style="margin:5px 0;">Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p PKT')}</p>
        <p style="margin:5px 0;">Questions? Reply to this email for support.</p>
    </div>

  </div>
</div>
</body>
</html>"""
    
    return html


def send_monthly_report():
    """Generate and send monthly report."""
    print("=" * 60)
    print("  MONTHLY SEO REPORT GENERATOR")
    print(f"  {datetime.now().strftime('%B %Y')}")
    print("=" * 60)
    
    # Connect to database
    if not Path(CONFIG["db_path"]).exists():
        print(f"❌ Database not found: {CONFIG['db_path']}")
        return
    
    conn = sqlite3.connect(CONFIG["db_path"])
    
    # Gather statistics
    print("\n📊 Gathering monthly statistics...")
    stats = get_monthly_stats(conn)
    conn.close()
    
    print(f"   ✅ {stats['sites_monitored']} sites monitored")
    print(f"   ✅ {stats['total_clicks']:,} total clicks")
    print(f"   ✅ {stats['total_suspicious']} suspicious keywords detected")
    
    # Build email
    print("\n📧 Building monthly report email...")
    html = build_monthly_email(stats)
    
    # Save preview
    preview_file = f"monthly_report_{datetime.now().strftime('%Y%m')}.html"
    with open(preview_file, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"   💾 Preview saved: {preview_file}")
    
    # Send email
    if not CONFIG["email_from"] or not CONFIG["email_password"]:
        print("\n⚠️  Email not configured. Set EMAIL_FROM and EMAIL_PASSWORD in .env")
        return
    
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = CONFIG["email_from"]
        msg['To'] = CONFIG["email_to"]
        msg['Cc'] = CONFIG["email_cc"]
        msg['Subject'] = f"📊 SEO Guardian Monthly Report — {stats['month']}"
        msg.attach(MIMEText(html, 'html', 'utf-8'))
        
        server = smtplib.SMTP(CONFIG["smtp_server"], CONFIG["smtp_port"])
        server.starttls()
        server.login(CONFIG["email_from"], CONFIG["email_password"])
        recipients = [CONFIG["email_to"], CONFIG["email_cc"]]
        server.sendmail(CONFIG["email_from"], recipients, msg.as_string())
        server.quit()
        
        print(f"\n✅ Monthly report sent to {CONFIG['email_to']}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Email failed: {e}")


if __name__ == "__main__":
    send_monthly_report()
