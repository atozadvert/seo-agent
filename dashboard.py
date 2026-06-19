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
import streamlit.components.v1 as components
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


def copy_button(label: str, command: str, key: str):
        safe_cmd = command.replace("\\", "\\\\").replace("'", "\\'")
        safe_key = key.replace("'", "")
        components.html(
                f"""
                <button id='btn-{safe_key}' style='width:100%;padding:8px 10px;border:1px solid #d7dce5;border-radius:8px;background:#f8fafc;cursor:pointer'>
                    {label}
                </button>
                <script>
                    const btn = document.getElementById('btn-{safe_key}');
                    btn.addEventListener('click', async () => {{
                        try {{
                            await navigator.clipboard.writeText('{safe_cmd}');
                            btn.innerText = 'Copied';
                            setTimeout(() => btn.innerText = '{label}', 1200);
                        }} catch (e) {{
                            btn.innerText = 'Copy failed';
                        }}
                    }});
                </script>
                """,
                height=45,
        )


def pct_change(current, previous):
        if previous in (None, 0):
                return None
        return round(((current - previous) / previous) * 100, 1)


def delta_text(current, previous, suffix=""):
        if previous in (None, 0):
                return "No previous baseline"
        pct = pct_change(current, previous)
        sign = "+" if current - previous >= 0 else ""
        return f"{sign}{current - previous:,.0f}{suffix} ({pct:+.1f}%)"


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
copy_button("Copy: python seo_guardian.py", "python seo_guardian.py", "sb-seo")
copy_button("Copy: python rank_tracker.py", "python rank_tracker.py", "sb-rank")
copy_button("Copy: python uptime_monitor.py", "python uptime_monitor.py", "sb-up")


# ═══════════════════════════════════════════════════════════════════
# PAGE: OVERVIEW
# ═══════════════════════════════════════════════════════════════════
if page == "📊 Overview":
    st.title("📊 SEO Guardian — Overview")
    st.caption(f"Data from: {DB_PATH}")
    if table_exists(conn, "daily_stats"):
        global_7 = q(conn, """
            SELECT COALESCE(SUM(total_keywords),0) keywords,
                   COALESCE(SUM(total_clicks),0) clicks,
                   COALESCE(SUM(suspicious_count),0) suspicious
            FROM daily_stats
            WHERE date BETWEEN date('now','-6 days') AND date('now')
        """)
        prev_7 = q(conn, """
            SELECT COALESCE(SUM(total_keywords),0) keywords,
                   COALESCE(SUM(total_clicks),0) clicks,
                   COALESCE(SUM(suspicious_count),0) suspicious
            FROM daily_stats
            WHERE date BETWEEN date('now','-13 days') AND date('now','-7 days')
        """)
        global_30 = q(conn, """
            SELECT COALESCE(SUM(total_keywords),0) keywords,
                   COALESCE(SUM(total_clicks),0) clicks,
                   COALESCE(SUM(suspicious_count),0) suspicious
            FROM daily_stats
            WHERE date BETWEEN date('now','-29 days') AND date('now')
        """)
        prev_30 = q(conn, """
            SELECT COALESCE(SUM(total_keywords),0) keywords,
                   COALESCE(SUM(total_clicks),0) clicks,
                   COALESCE(SUM(suspicious_count),0) suspicious
            FROM daily_stats
            WHERE date BETWEEN date('now','-59 days') AND date('now','-30 days')
        """)
    else:
        global_7 = prev_7 = global_30 = prev_30 = pd.DataFrame([{"keywords": 0, "clicks": 0, "suspicious": 0}])

    if table_exists(conn, "rank_history"):
        rank_7 = q(conn, """
            SELECT COALESCE(SUM(impressions),0) impressions,
                   COALESCE(AVG(position),0) avg_position
            FROM rank_history
            WHERE date BETWEEN date('now','-6 days') AND date('now')
        """)
        rank_prev_7 = q(conn, """
            SELECT COALESCE(SUM(impressions),0) impressions,
                   COALESCE(AVG(position),0) avg_position
            FROM rank_history
            WHERE date BETWEEN date('now','-13 days') AND date('now','-7 days')
        """)
        rank_30 = q(conn, """
            SELECT COALESCE(SUM(impressions),0) impressions,
                   COALESCE(AVG(position),0) avg_position
            FROM rank_history
            WHERE date BETWEEN date('now','-29 days') AND date('now')
        """)
        rank_prev_30 = q(conn, """
            SELECT COALESCE(SUM(impressions),0) impressions,
                   COALESCE(AVG(position),0) avg_position
            FROM rank_history
            WHERE date BETWEEN date('now','-59 days') AND date('now','-30 days')
        """)
    else:
        rank_7 = rank_prev_7 = rank_30 = rank_prev_30 = pd.DataFrame([{"impressions": 0, "avg_position": 0}])

    st.subheader("Growth Cards — 7 Days vs Previous 7 Days")
    g1, g2, g3, g4 = st.columns(4)
    with g1:
        st.metric("Keywords (7d)", f"{int(global_7['keywords'].iloc[0]):,}", delta=delta_text(float(global_7['keywords'].iloc[0]), float(prev_7['keywords'].iloc[0])))
    with g2:
        st.metric("Clicks (7d)", f"{int(global_7['clicks'].iloc[0]):,}", delta=delta_text(float(global_7['clicks'].iloc[0]), float(prev_7['clicks'].iloc[0])))
    with g3:
        st.metric("Impressions (7d)", f"{int(rank_7['impressions'].iloc[0]):,}", delta=delta_text(float(rank_7['impressions'].iloc[0]), float(rank_prev_7['impressions'].iloc[0])))
    with g4:
        st.metric("Avg Position (7d)", f"{float(rank_7['avg_position'].iloc[0]):.1f}", delta=delta_text(float(rank_7['avg_position'].iloc[0]), float(rank_prev_7['avg_position'].iloc[0])))

    st.subheader("Growth Cards — 30 Days vs Previous 30 Days")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Keywords (30d)", f"{int(global_30['keywords'].iloc[0]):,}", delta=delta_text(float(global_30['keywords'].iloc[0]), float(prev_30['keywords'].iloc[0])))
    with m2:
        st.metric("Clicks (30d)", f"{int(global_30['clicks'].iloc[0]):,}", delta=delta_text(float(global_30['clicks'].iloc[0]), float(prev_30['clicks'].iloc[0])))
    with m3:
        st.metric("Impressions (30d)", f"{int(rank_30['impressions'].iloc[0]):,}", delta=delta_text(float(rank_30['impressions'].iloc[0]), float(rank_prev_30['impressions'].iloc[0])))
    with m4:
        st.metric("Avg Position (30d)", f"{float(rank_30['avg_position'].iloc[0]):.1f}", delta=delta_text(float(rank_30['avg_position'].iloc[0]), float(rank_prev_30['avg_position'].iloc[0])))

    st.markdown("---")

    if table_exists(conn, "daily_stats"):
        st.subheader("All Sites — Keyword Tracking Trend (Last 30 Days)")
        trend_df = q(conn, """
            SELECT date, site, SUM(total_keywords) total_keywords
            FROM daily_stats
            WHERE date >= date('now','-30 days')
            GROUP BY date, site
            ORDER BY date ASC
        """)
        if not trend_df.empty:
            fig = px.line(trend_df, x="date", y="total_keywords", color="site", markers=False)
            fig.update_layout(height=360, legend_title_text="Site")
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Site-Wise Growth Comparison")
    site_compare = q(conn, """
        SELECT
            site,
            SUM(CASE WHEN date BETWEEN date('now','-6 days') AND date('now') THEN total_clicks ELSE 0 END) clicks_7d,
            SUM(CASE WHEN date BETWEEN date('now','-13 days') AND date('now','-7 days') THEN total_clicks ELSE 0 END) clicks_prev_7d,
            SUM(CASE WHEN date BETWEEN date('now','-29 days') AND date('now') THEN total_clicks ELSE 0 END) clicks_30d,
            SUM(CASE WHEN date BETWEEN date('now','-59 days') AND date('now','-30 days') THEN total_clicks ELSE 0 END) clicks_prev_30d,
            SUM(CASE WHEN date BETWEEN date('now','-6 days') AND date('now') THEN total_keywords ELSE 0 END) keywords_7d,
            SUM(CASE WHEN date BETWEEN date('now','-29 days') AND date('now') THEN total_keywords ELSE 0 END) keywords_30d
        FROM daily_stats
        GROUP BY site
        ORDER BY clicks_7d DESC
    """) if table_exists(conn, "daily_stats") else pd.DataFrame()

    if not site_compare.empty:
        site_compare["clicks_7d_delta"] = site_compare["clicks_7d"] - site_compare["clicks_prev_7d"]
        site_compare["clicks_30d_delta"] = site_compare["clicks_30d"] - site_compare["clicks_prev_30d"]

        c1, c2 = st.columns(2)
        with c1:
            fig_up = px.bar(site_compare.head(15), x="site", y="clicks_7d_delta", title="7d Click Growth by Site")
            st.plotly_chart(fig_up, use_container_width=True)
        with c2:
            fig_up30 = px.bar(site_compare.head(15), x="site", y="clicks_30d_delta", title="30d Click Growth by Site")
            st.plotly_chart(fig_up30, use_container_width=True)

        st.dataframe(site_compare, use_container_width=True, hide_index=True)

        site_pick = st.selectbox("Site Growth Cards", site_compare["site"].tolist())
        row = site_compare[site_compare["site"] == site_pick].iloc[0]
        s1, s2, s3, s4 = st.columns(4)
        with s1:
            st.metric("Site Clicks 7d", int(row["clicks_7d"]), delta=int(row["clicks_7d_delta"]))
        with s2:
            st.metric("Site Clicks 30d", int(row["clicks_30d"]), delta=int(row["clicks_30d_delta"]))
        with s3:
            st.metric("Site Keywords 7d", int(row["keywords_7d"]))
        with s4:
            st.metric("Site Keywords 30d", int(row["keywords_30d"]))

    st.markdown("---")
    st.subheader("Uptime Snapshot (Minimal)")
    if table_exists(conn, "uptime_status"):
        up_df = q(conn, "SELECT COUNT(*) total, SUM(is_up) up FROM uptime_status")
        total_sites = int(up_df["total"].iloc[0]) if not up_df.empty else 0
        up_sites = int(up_df["up"].iloc[0] or 0) if not up_df.empty else 0
        down_sites = total_sites - up_sites
    else:
        total_sites = up_sites = down_sites = 0

    avg_rt = q(conn, "SELECT AVG(response_time) rt FROM uptime_log WHERE timestamp >= datetime('now','-24 hours')") if table_exists(conn, "uptime_log") else pd.DataFrame([{"rt": 0}])
    u1, u2, u3 = st.columns(3)
    with u1:
        st.metric("UP", up_sites)
    with u2:
        st.metric("DOWN", down_sites)
    with u3:
        st.metric("Avg Response (24h)", f"{float(avg_rt['rt'].iloc[0] or 0):.2f}s")

    if table_exists(conn, "uptime_log"):
        slow = q(conn, """
            SELECT site, ROUND(AVG(response_time),2) avg_rt
            FROM uptime_log
            WHERE timestamp >= datetime('now','-24 hours')
              AND response_time IS NOT NULL
            GROUP BY site
            ORDER BY avg_rt DESC
            LIMIT 5
        """)
        spark = q(conn, """
            SELECT strftime('%Y-%m-%d %H:00', timestamp) as hour,
                   ROUND(SUM(is_up) * 100.0 / COUNT(*), 1) as uptime_pct
            FROM uptime_log
            WHERE timestamp >= datetime('now','-24 hours')
            GROUP BY strftime('%Y-%m-%d %H:00', timestamp)
            ORDER BY hour
        """)

        ucol1, ucol2 = st.columns(2)
        with ucol1:
            st.caption("Top 5 Slowest Sites (24h)")
            st.dataframe(slow, use_container_width=True, hide_index=True)
        with ucol2:
            fig_spark = px.line(spark, x="hour", y="uptime_pct", title="24h Uptime Trend")
            fig_spark.update_layout(height=220, margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig_spark, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════
# PAGE: SUSPICIOUS KEYWORDS
# ═══════════════════════════════════════════════════════════════════
elif page == "🚨 Suspicious Keywords":
    st.title("🚨 Suspicious Keywords Monitor")

    if table_exists(conn, "suspicious_log"):
        sites = q(conn, "SELECT DISTINCT site FROM suspicious_log ORDER BY site")
        selected = st.selectbox("Select Site", ["All Sites"] + list(sites["site"]) if not sites.empty else ["All Sites"])

        df = q(conn, """
            SELECT site, keyword, category, clicks, impressions, position, date as detected_date
            FROM suspicious_log
            ORDER BY clicks DESC
        """) if selected == "All Sites" else q(conn, """
            SELECT site, keyword, category, clicks, impressions, position, date as detected_date
            FROM suspicious_log WHERE site=?
            ORDER BY clicks DESC
        """, (selected,))

        if not df.empty:
            st.metric("Total Suspicious Keywords", len(df))

            df["category"] = (
                df["category"].astype(str)
                .str.replace("ðŸ’€ ", "", regex=False)
                .str.replace("ðŸ˜¤ ", "", regex=False)
                .str.replace("ðŸŽ° ", "", regex=False)
            )

            # By category
            cat_counts = df["category"].value_counts().reset_index()
            cat_counts.columns = ["Category", "Count"]
            fig = px.pie(cat_counts, values="Count", names="Category",
                         title="By Category", color_discrete_sequence=px.colors.qualitative.Set3)
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No suspicious keywords stored yet. Run `python seo_guardian.py` first.")
            copy_button("Copy: python seo_guardian.py", "python seo_guardian.py", "sus-empty")
    else:
        st.warning("No suspicious keywords data found. Run `python seo_guardian.py` to populate data.")
        copy_button("Copy: python seo_guardian.py", "python seo_guardian.py", "sus-missing")


# ═══════════════════════════════════════════════════════════════════
# PAGE: RANK TRACKER
# ═══════════════════════════════════════════════════════════════════
elif page == "📈 Rank Tracker":
    st.title("📈 Rank Tracker")

    if not table_exists(conn, "rank_history"):
        st.warning("No rank history yet. Run `python rank_tracker.py` first.")
        copy_button("Copy: python rank_tracker.py", "python rank_tracker.py", "rank-missing")
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

                df_latest["position"] = pd.to_numeric(df_latest["position"], errors="coerce").round(0).astype("Int64")
                df_latest["ctr"] = pd.to_numeric(df_latest["ctr"], errors="coerce").fillna(0).round(2)
                df_latest["clicks"] = pd.to_numeric(df_latest["clicks"], errors="coerce").fillna(0).astype(int)
                df_latest["impressions"] = pd.to_numeric(df_latest["impressions"], errors="coerce").fillna(0).astype(int)

                def style_position(val):
                    if pd.isna(val): return ""
                    if val <= 3:   return "color: #27ae60; font-weight: bold"
                    if val <= 10:  return "color: #f39c12; font-weight: bold"
                    return "color: #e74c3c"

                display_latest = df_latest.copy()
                display_latest["ctr"] = display_latest["ctr"].map(lambda v: f"{v:.2f}%")

                st.dataframe(
                    display_latest.style.applymap(style_position, subset=["position"]).format({"position": "{:.0f}"}),
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
                    for col in ["old_pos", "new_pos", "change"]:
                        alerts[col] = pd.to_numeric(alerts[col], errors="coerce").round(0).astype("Int64")
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
        copy_button("Copy: python uptime_monitor.py", "python uptime_monitor.py", "uptime-missing")
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
        copy_button("Copy: python seo_guardian.py", "python seo_guardian.py", "allsites-missing")
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
        copy_button("Copy: python seo_guardian.py", "python seo_guardian.py", "all-cmd-seo")
        st.caption("Full SEO scan + email report")
    with col2:
        copy_button("Copy: python rank_tracker.py", "python rank_tracker.py", "all-cmd-rank")
        st.caption("Track keyword positions")
    with col3:
        copy_button("Copy: python uptime_monitor.py", "python uptime_monitor.py", "all-cmd-up")
        st.caption("Check all sites are live")
