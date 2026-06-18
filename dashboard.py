#!/usr/bin/env python3
"""
SEO Guardian Dashboard — Streamlit web app
Shows all site metrics, uptime, rank history, and suspicious keyword alerts.
Run with: streamlit run dashboard.py
"""

import os
import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
from pathlib import Path

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

DB_PATH = os.getenv("DB_PATH", "seo_guardian.db")

st.set_page_config(
    page_title="SEO Guardian Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: white;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        text-align: center;
    }
    .alert-red    { color: #e74c3c; font-weight: bold; }
    .alert-green  { color: #27ae60; font-weight: bold; }
    .alert-orange { color: #f39c12; font-weight: bold; }
    div[data-testid="metric-container"] {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 15px;
    }
</style>
""", unsafe_allow_html=True)


# ── DB helpers ────────────────────────────────────────────────────────────────
@st.cache_resource
def get_conn():
    db_exists = Path(DB_PATH).exists()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    if not db_exists:
        st.warning(
            f"Database initialized at {DB_PATH}. No scan data yet - run seo_guardian.py to populate reports."
        )
    return conn


def table_exists(conn, name):
    return conn.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()[0] > 0


def q(conn, sql, params=()):
    try:
        return pd.read_sql_query(sql, conn, params=params)
    except Exception:
        return pd.DataFrame()


# ── Sidebar ───────────────────────────────────────────────────────────────────
conn = get_conn()

st.sidebar.image("https://img.icons8.com/fluency/96/shield.png", width=60)
st.sidebar.title("SEO Guardian")
st.sidebar.caption(f"Last refreshed: {datetime.now().strftime('%I:%M %p')}")

page = st.sidebar.radio("Navigate", [
    "📊 Overview",
    "🚨 Suspicious Keywords",
    "📈 Rank Tracker",
    "🟢 Uptime Monitor",
    "🔬 Advanced Monitor",
    "📋 All Sites",
])

if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("**Quick Actions**")
st.sidebar.markdown("```\npython seo_guardian.py\npython rank_tracker.py\npython uptime_monitor.py\n```")


# ═══════════════════════════════════════════════════════════════════
# PAGE: OVERVIEW
# ═══════════════════════════════════════════════════════════════════
if page == "📊 Overview":
    st.title("📊 SEO Guardian — Overview")
    st.caption(f"Data from: {DB_PATH}")

    # ── Top metrics ─────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)

    # Suspicious keywords count
    if table_exists(conn, "site_scans"):
        sus_df = q(conn, "SELECT SUM(suspicious_count) as total FROM site_scans WHERE date(scan_date) >= date('now','-7 days')")
        total_sus = int(sus_df["total"].iloc[0] or 0) if not sus_df.empty else 0
    else:
        total_sus = 0

    # Uptime
    if table_exists(conn, "uptime_status"):
        up_df   = q(conn, "SELECT COUNT(*) as total, SUM(is_up) as up FROM uptime_status")
        total_s = int(up_df["total"].iloc[0]) if not up_df.empty else 0
        total_up= int(up_df["up"].iloc[0] or 0) if not up_df.empty else 0
        down_count = total_s - total_up
    else:
        total_s = len([
            "atozappliancesrepair.com","atozadvert.com","silverservicesae.com",
            "silverpainters.com","ppcexpertsdubai.com","atiflawfirm.com",
            "nacl.pk","premadedropshippingstores.com","pre-made-shopify-store.blogspot.com"
        ])
        down_count = 0

    # Rank alerts
    if table_exists(conn, "rank_alerts"):
        drops_df = q(conn, "SELECT COUNT(*) as c FROM rank_alerts WHERE alert_type='DROP' AND date(timestamp)=date('now')")
        rank_drops = int(drops_df["c"].iloc[0]) if not drops_df.empty else 0
    else:
        rank_drops = 0

    with col1:
        st.metric("🚨 Suspicious Keywords", f"{total_sus:,}", help="Last 7 days across all sites")
    with col2:
        color = "normal" if down_count == 0 else "inverse"
        st.metric("🔴 Sites Down", down_count, delta=f"{total_s - down_count} up", delta_color=color)
    with col3:
        st.metric("📉 Rank Drops Today", rank_drops)
    with col4:
        if table_exists(conn, "uptime_log"):
            checks = q(conn, "SELECT COUNT(*) as c FROM uptime_log WHERE date(timestamp)>=date('now','-1 days')")
            st.metric("✅ Uptime Checks (24h)", int(checks["c"].iloc[0]) if not checks.empty else 0)
        else:
            st.metric("✅ Uptime Checks (24h)", 0)

    st.markdown("---")

    # ── Suspicious keywords per site bar chart ─────────────────
    if table_exists(conn, "site_scans"):
        df = q(conn, """
            SELECT site, suspicious_count, total_keywords, scan_date
            FROM site_scans
            WHERE scan_date = (SELECT MAX(scan_date) FROM site_scans)
            ORDER BY suspicious_count DESC
        """)
        if not df.empty and df["suspicious_count"].sum() > 0:
            st.subheader("🚨 Suspicious Keywords by Site (Latest Scan)")
            fig = px.bar(df, x="site", y="suspicious_count",
                         color="suspicious_count",
                         color_continuous_scale=["#27ae60","#f39c12","#e74c3c"],
                         labels={"site": "Site", "suspicious_count": "Suspicious Keywords"},
                         text="suspicious_count")
            fig.update_layout(showlegend=False, height=350)
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

    # ── Uptime last 24h ────────────────────────────────────────
    if table_exists(conn, "uptime_log"):
        st.subheader("🟢 Uptime — Last 24 Hours")
        df = q(conn, """
            SELECT site, AVG(response_time) as avg_rt, 
                   SUM(is_up)*100.0/COUNT(*) as uptime_pct,
                   COUNT(*) as checks
            FROM uptime_log
            WHERE timestamp >= datetime('now','-24 hours')
            GROUP BY site ORDER BY uptime_pct ASC
        """)
        if not df.empty:
            df["site"] = df["site"].str.replace("https://","").str.rstrip("/")
            df["uptime_pct"] = df["uptime_pct"].round(1)
            df["avg_rt"] = df["avg_rt"].round(2)
            df.columns = ["Site", "Avg Response (s)", "Uptime %", "Checks"]
            st.dataframe(df, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════
# PAGE: SUSPICIOUS KEYWORDS
# ═══════════════════════════════════════════════════════════════════
elif page == "🚨 Suspicious Keywords":
    st.title("🚨 Suspicious Keywords Monitor")

    if table_exists(conn, "suspicious_keywords"):
        sites = q(conn, "SELECT DISTINCT site FROM suspicious_keywords ORDER BY site")
        selected = st.selectbox("Select Site", ["All Sites"] + list(sites["site"]) if not sites.empty else ["All Sites"])

        df = q(conn, """
            SELECT site, keyword, category, clicks, impressions, position, detected_date
            FROM suspicious_keywords
            ORDER BY clicks DESC
        """) if selected == "All Sites" else q(conn, """
            SELECT site, keyword, category, clicks, impressions, position, detected_date
            FROM suspicious_keywords WHERE site=?
            ORDER BY clicks DESC
        """, (selected,))

        if not df.empty:
            st.metric("Total Suspicious Keywords", len(df))

            # By category
            cat_counts = df["category"].value_counts().reset_index()
            cat_counts.columns = ["Category", "Count"]
            fig = px.pie(cat_counts, values="Count", names="Category",
                         title="By Category", color_discrete_sequence=px.colors.qualitative.Set3)
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No suspicious keywords stored yet. Run `python seo_guardian.py` first.")
    else:
        st.warning("No suspicious keywords table found. Run `python seo_guardian.py` to populate data.")
        st.code("python seo_guardian.py")


# ═══════════════════════════════════════════════════════════════════
# PAGE: RANK TRACKER
# ═══════════════════════════════════════════════════════════════════
elif page == "📈 Rank Tracker":
    st.title("📈 Rank Tracker")

    if not table_exists(conn, "rank_history"):
        st.warning("No rank history yet. Run `python rank_tracker.py` first.")
        st.code("python rank_tracker.py")
    else:
        sites = q(conn, "SELECT DISTINCT site FROM rank_history ORDER BY site")
        if sites.empty:
            st.info("No data yet.")
        else:
            selected_site = st.selectbox("Select Site", sites["site"].tolist())

            # Latest rankings table
            df_latest = q(conn, """
                SELECT keyword, position, clicks, impressions, ctr, date
                FROM rank_history
                WHERE site=? AND date=(SELECT MAX(date) FROM rank_history WHERE site=?)
                ORDER BY position ASC
            """, (selected_site, selected_site))

            if not df_latest.empty:
                st.subheader(f"Current Rankings — {selected_site}")

                def style_position(val):
                    if pd.isna(val): return ""
                    if val <= 3:   return "color: #27ae60; font-weight: bold"
                    if val <= 10:  return "color: #f39c12; font-weight: bold"
                    return "color: #e74c3c"

                st.dataframe(
                    df_latest.style.applymap(style_position, subset=["position"]),
                    use_container_width=True, hide_index=True
                )

                # Position history chart
                kw_list = df_latest["keyword"].tolist()
                selected_kw = st.selectbox("Track keyword over time", kw_list)

                df_hist = q(conn, """
                    SELECT date, position FROM rank_history
                    WHERE site=? AND keyword=?
                    ORDER BY date ASC
                """, (selected_site, selected_kw))

                if len(df_hist) > 1:
                    fig = px.line(df_hist, x="date", y="position",
                                  title=f"Position History: '{selected_kw}'",
                                  markers=True)
                    fig.update_yaxes(autorange="reversed", title="Position (lower = better)")
                    fig.add_hline(y=3, line_dash="dot", line_color="green", annotation_text="Top 3")
                    fig.add_hline(y=10, line_dash="dot", line_color="orange", annotation_text="Top 10")
                    st.plotly_chart(fig, use_container_width=True)

            # Rank alerts
            st.subheader("📢 Recent Position Changes")
            if table_exists(conn, "rank_alerts"):
                alerts = q(conn, """
                    SELECT timestamp, site, keyword, old_pos, new_pos, change, alert_type
                    FROM rank_alerts WHERE site=?
                    ORDER BY timestamp DESC LIMIT 50
                """, (selected_site,))
                if not alerts.empty:
                    st.dataframe(alerts, use_container_width=True, hide_index=True)
                else:
                    st.success("No significant rank changes recorded yet.")


# ═══════════════════════════════════════════════════════════════════
# PAGE: UPTIME MONITOR
# ═══════════════════════════════════════════════════════════════════
elif page == "🟢 Uptime Monitor":
    st.title("🟢 Uptime Monitor")

    if not table_exists(conn, "uptime_status"):
        st.warning("No uptime data yet. Run `python uptime_monitor.py` first.")
        st.code("python uptime_monitor.py")
    else:
        # Current status
        status_df = q(conn, "SELECT site, is_up, last_checked, down_since, consecutive_fails FROM uptime_status")
        if not status_df.empty:
            st.subheader("Current Status")
            status_df["site"] = status_df["site"].str.replace("https://","").str.rstrip("/")
            status_df["Status"] = status_df["is_up"].apply(lambda x: "🟢 UP" if x else "🔴 DOWN")
            status_df["last_checked"] = pd.to_datetime(status_df["last_checked"]).dt.strftime("%d %b %I:%M %p")
            display_df = status_df[["site","Status","last_checked","consecutive_fails","down_since"]]
            display_df.columns = ["Site", "Status", "Last Checked", "Consecutive Fails", "Down Since"]
            st.dataframe(display_df, use_container_width=True, hide_index=True)

        # Response time chart
        if table_exists(conn, "uptime_log"):
            st.subheader("Response Times — Last 24h")
            rt_df = q(conn, """
                SELECT timestamp, site, response_time, is_up
                FROM uptime_log
                WHERE timestamp >= datetime('now','-24 hours') AND response_time IS NOT NULL
                ORDER BY timestamp ASC
            """)
            if not rt_df.empty:
                rt_df["site"] = rt_df["site"].str.replace("https://","").str.rstrip("/")
                sites = rt_df["site"].unique().tolist()
                sel = st.multiselect("Select sites", sites, default=sites[:3])
                filtered = rt_df[rt_df["site"].isin(sel)]
                if not filtered.empty:
                    fig = px.line(filtered, x="timestamp", y="response_time", color="site",
                                  labels={"response_time": "Response Time (s)", "timestamp": "Time"})
                    fig.add_hline(y=3, line_dash="dot", line_color="orange", annotation_text="Slow threshold (3s)")
                    st.plotly_chart(fig, use_container_width=True)

            # Downtime incidents
            st.subheader("📋 Downtime Incidents")
            incidents = q(conn, """
                SELECT timestamp, site, status_code, response_time, error
                FROM uptime_log WHERE is_up=0
                ORDER BY timestamp DESC LIMIT 100
            """)
            if not incidents.empty:
                incidents["site"] = incidents["site"].str.replace("https://","").str.rstrip("/")
                st.dataframe(incidents, use_container_width=True, hide_index=True)
            else:
                st.success("✅ No downtime incidents recorded!")


# ═══════════════════════════════════════════════════════════════════
# PAGE: ADVANCED MONITOR
# ═══════════════════════════════════════════════════════════════════
elif page == "🔬 Advanced Monitor":
    st.title("🔬 Advanced SEO Monitor")
    st.caption("Redirects • Indexing Changes • Suspicious External Links")

    col1, col2, col3 = st.columns(3)
    with col1:
        if table_exists(conn, "redirect_log"):
            n = q(conn, "SELECT COUNT(*) as c FROM redirect_log WHERE date(detected_date)>=date('now','-7 days') AND issues != ''")
            st.metric("🔀 Redirect Issues (7d)", int(n["c"].iloc[0]) if not n.empty else 0)
        else:
            st.metric("🔀 Redirect Issues (7d)", "No data")
    with col2:
        if table_exists(conn, "index_tracking"):
            n = q(conn, "SELECT COUNT(DISTINCT site) as c FROM index_tracking WHERE date(date)=date('now','-1 day')")
            st.metric("📊 Sites Tracked (indexing)", int(n["c"].iloc[0]) if not n.empty else 0)
        else:
            st.metric("📊 Sites Tracked (indexing)", "No data")
    with col3:
        if table_exists(conn, "external_links_baseline"):
            n = q(conn, "SELECT COUNT(*) as c FROM external_links_baseline WHERE date(first_seen)>=date('now','-7 days')")
            st.metric("🔗 New External Links (7d)", int(n["c"].iloc[0]) if not n.empty else 0)
        else:
            st.metric("🔗 New External Links (7d)", "No data")

    st.markdown("---")

    # ── Indexing history chart ────────────────────────────────────
    if table_exists(conn, "index_tracking"):
        st.subheader("📊 Indexed Pages Over Time")
        idx_df = q(conn, """
            SELECT site, date, page_count FROM index_tracking
            ORDER BY site, date ASC
        """)
        if not idx_df.empty:
            idx_df["site"] = idx_df["site"].str.replace("https://","").str.replace("sc-domain:","").str.rstrip("/")
            sel_sites = st.multiselect("Select sites", idx_df["site"].unique().tolist(), default=idx_df["site"].unique().tolist()[:4])
            filtered = idx_df[idx_df["site"].isin(sel_sites)]
            if not filtered.empty:
                fig = px.line(filtered, x="date", y="page_count", color="site",
                              markers=True, labels={"page_count":"Indexed Pages","date":"Date"})
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Run `python advanced_monitor.py` to populate indexing data.")
    else:
        st.warning("No indexing data yet. Run `python advanced_monitor.py` first.")

    # ── Redirect log ─────────────────────────────────────────────
    st.subheader("🔀 Redirect Log")
    if table_exists(conn, "redirect_log"):
        redir_df = q(conn, """
            SELECT site, page_url, final_url, redirect_hops, issues, detected_date
            FROM redirect_log ORDER BY detected_date DESC LIMIT 100
        """)
        if not redir_df.empty:
            redir_df["site"] = redir_df["site"].str.replace("https://","").str.rstrip("/")
            st.dataframe(redir_df, use_container_width=True, hide_index=True)
        else:
            st.success("✅ No redirect issues logged.")
    else:
        st.info("No redirect log yet.")

    # ── External links ────────────────────────────────────────────
    st.subheader("🔗 External Links Baseline")
    if table_exists(conn, "external_links_baseline"):
        links_df = q(conn, """
            SELECT site, link_url, first_seen FROM external_links_baseline
            ORDER BY first_seen DESC LIMIT 200
        """)
        if not links_df.empty:
            links_df["site"] = links_df["site"].str.replace("https://","").str.rstrip("/")
            st.dataframe(links_df, use_container_width=True, hide_index=True)
        else:
            st.info("No external links recorded yet.")
    else:
        st.info("No external links data yet.")


# ═══════════════════════════════════════════════════════════════════
# PAGE: ALL SITES
# ═══════════════════════════════════════════════════════════════════
elif page == "📋 All Sites":
    st.title("📋 All Sites Overview")

    # ── Add New Site Form ─────────────────────────────────────────
    with st.expander("➕ Add New Site to Monitoring", expanded=False):
        st.markdown("Add a new website to SEO Guardian monitoring system.")
        
        with st.form("add_site_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                new_domain = st.text_input("Domain (e.g., example.com)", placeholder="example.com")
                new_category = st.selectbox("Category", [
                    "Digital Marketing", "E-Commerce", "Legal", "Cleaning", 
                    "Painting", "Appliance Repair", "PPC / Google Ads",
                    "Chemical Supply", "Blog", "Other"
                ])
            
            with col2:
                new_location = st.selectbox("Location", ["Dubai", "UAE", "Pakistan", "Global", "Other"])
                gsc_url = st.text_input("Google Search Console URL", 
                                       placeholder="https://example.com or sc-domain:example.com",
                                       help="The exact URL as it appears in Google Search Console")
            
            keywords_raw = st.text_area("Target Keywords (one per line)", 
                                       placeholder="keyword 1\nkeyword 2\nkeyword 3",
                                       height=100)
            
            submitted = st.form_submit_button("✅ Add Site", use_container_width=True)
            
            if submitted:
                if not new_domain:
                    st.error("❌ Please enter a domain name")
                else:
                    try:
                        # Create managed_sites table if it doesn't exist
                        conn.execute("""
                            CREATE TABLE IF NOT EXISTS managed_sites (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                domain TEXT UNIQUE NOT NULL,
                                category TEXT,
                                location TEXT,
                                gsc_url TEXT,
                                added_date DATE DEFAULT CURRENT_DATE,
                                is_active INTEGER DEFAULT 1
                            )
                        """)
                        
                        # Create site_keywords table if it doesn't exist
                        conn.execute("""
                            CREATE TABLE IF NOT EXISTS site_keywords (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                site TEXT NOT NULL,
                                keyword TEXT NOT NULL,
                                added_date DATE DEFAULT CURRENT_DATE,
                                UNIQUE(site, keyword)
                            )
                        """)
                        
                        # Insert site
                        conn.execute("""
                            INSERT OR REPLACE INTO managed_sites (domain, category, location, gsc_url, added_date)
                            VALUES (?, ?, ?, ?, date('now'))
                        """, (new_domain, new_category, new_location, gsc_url or f"https://{new_domain}"))
                        
                        # Insert keywords
                        keywords = [k.strip() for k in keywords_raw.splitlines() if k.strip()]
                        for kw in keywords:
                            conn.execute("""
                                INSERT OR IGNORE INTO site_keywords (site, keyword, added_date)
                                VALUES (?, ?, date('now'))
                            """, (new_domain, kw))
                        
                        conn.commit()
                        st.success(f"✅ {new_domain} added successfully! Added {len(keywords)} keywords.")
                        st.info("💡 The site will be included in the next automated scan. You can also verify it in Google Search Console.")
                        
                    except Exception as e:
                        st.error(f"❌ Error adding site: {e}")

    st.markdown("---")

    # ── Sites List (auto-synced from managed_sites / GSC) ────────────────────
    sites_info = []

    if table_exists(conn, "managed_sites"):
        managed_df = q(conn, "SELECT domain, category, location FROM managed_sites WHERE is_active=1 ORDER BY domain")
        if not managed_df.empty:
            for _, row in managed_df.iterrows():
                sites_info.append({
                    "Site": row["domain"],
                    "Category": row["category"] or "Uncategorized",
                    "Location": row["location"] or "Unknown"
                })

    if not sites_info and table_exists(conn, "uptime_status"):
        up_seed = q(conn, "SELECT DISTINCT site FROM uptime_status")
        if not up_seed.empty:
            for s in up_seed["site"].tolist():
                clean = s.replace("https://", "").replace("http://", "").rstrip("/")
                sites_info.append({"Site": clean, "Category": "Uncategorized", "Location": "Unknown"})

    if not sites_info:
        st.info("No managed sites found yet. Run `python seo_guardian.py` after granting GSC owner access to the service account.")
        st.code("python seo_guardian.py")
        df_sites = pd.DataFrame(columns=["Site", "Category", "Location", "Uptime"])
    else:
        df_sites = pd.DataFrame(sites_info)

    # Merge uptime status if available
    if table_exists(conn, "uptime_status"):
        up_df = q(conn, "SELECT site, is_up FROM uptime_status")
        up_df["site_clean"] = up_df["site"].str.replace("https://","").str.rstrip("/")
        up_map = dict(zip(up_df["site_clean"], up_df["is_up"]))
        df_sites["Uptime"] = df_sites["Site"].map(lambda s: "🟢 UP" if up_map.get(s, 1) else "🔴 DOWN")
    else:
        df_sites["Uptime"] = "⚪ Unknown"

    st.dataframe(df_sites, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("🔧 Run Commands")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.code("python seo_guardian.py", language="bash")
        st.caption("Full SEO scan + email report")
    with col2:
        st.code("python rank_tracker.py", language="bash")
        st.caption("Track keyword positions")
    with col3:
        st.code("python uptime_monitor.py", language="bash")
        st.caption("Check all sites are live")
