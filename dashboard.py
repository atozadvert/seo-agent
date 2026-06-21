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

DEFAULT_DB_PATH = "/tmp/seo_guardian.db" if os.getenv("RAILWAY_ENVIRONMENT") else "seo_guardian.db"
DB_PATH = os.getenv("DB_PATH", DEFAULT_DB_PATH)

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
    .mini-chip {
        display: inline-block;
        padding: 8px 12px;
        border-radius: 999px;
        font-weight: 700;
        margin-right: 8px;
        font-size: 12px;
    }
    .chip-blue { background:#e8f1ff; color:#1f4fa8; }
    .chip-red { background:#ffecec; color:#b03a2e; }
    .chip-amber { background:#fff5db; color:#8a5a00; }
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
    "🧾 All Keywords",
    "📈 Rank Tracker",
    "🟢 Uptime Monitor",
    "🔬 Advanced Monitor",
])

if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("**Quick Actions**")
st.sidebar.code("python seo_guardian.py", language="bash")
st.sidebar.code("python rank_tracker.py", language="bash")
st.sidebar.code("python uptime_monitor.py", language="bash")


# ═══════════════════════════════════════════════════════════════════
# PAGE: OVERVIEW
# ═══════════════════════════════════════════════════════════════════
if page == "📊 Overview":
    st.title("📊 SEO Guardian — Overview")
    st.caption(f"Data from: {DB_PATH}")
    # tiny global summary chips only
    total_sites = int(q(conn, "SELECT COUNT(DISTINCT domain) c FROM managed_sites WHERE is_active=1").iloc[0]["c"]) if table_exists(conn, "managed_sites") else 0
    down_sites = int(q(conn, "SELECT COUNT(*) c FROM uptime_status WHERE is_up=0").iloc[0]["c"]) if table_exists(conn, "uptime_status") else 0
    suspicious_sites = int(q(conn, "SELECT COUNT(DISTINCT site) c FROM daily_stats WHERE date BETWEEN date('now','-6 days') AND date('now') AND suspicious_count > 0").iloc[0]["c"]) if table_exists(conn, "daily_stats") else 0

    st.markdown(
        f"""
        <span class='mini-chip chip-blue'>Total Sites: {total_sites}</span>
        <span class='mini-chip chip-red'>Down Sites: {down_sites}</span>
        <span class='mini-chip chip-amber'>Suspicious Sites (7d): {suspicious_sites}</span>
        """,
        unsafe_allow_html=True,
    )

    # site-wise dataset for cards (all sites, worst first)
    site_rows = q(conn, """
        WITH ds AS (
            SELECT
                site,
                SUM(CASE WHEN date BETWEEN date('now','-6 days') AND date('now') THEN total_keywords ELSE 0 END) keywords_7d,
                SUM(CASE WHEN date BETWEEN date('now','-13 days') AND date('now','-7 days') THEN total_keywords ELSE 0 END) keywords_prev_7d,
                SUM(CASE WHEN date BETWEEN date('now','-29 days') AND date('now') THEN total_keywords ELSE 0 END) keywords_30d,
                SUM(CASE WHEN date BETWEEN date('now','-59 days') AND date('now','-30 days') THEN total_keywords ELSE 0 END) keywords_prev_30d,
                SUM(CASE WHEN date BETWEEN date('now','-6 days') AND date('now') THEN total_clicks ELSE 0 END) clicks_7d,
                SUM(CASE WHEN date BETWEEN date('now','-13 days') AND date('now','-7 days') THEN total_clicks ELSE 0 END) clicks_prev_7d,
                SUM(CASE WHEN date BETWEEN date('now','-29 days') AND date('now') THEN total_clicks ELSE 0 END) clicks_30d,
                SUM(CASE WHEN date BETWEEN date('now','-59 days') AND date('now','-30 days') THEN total_clicks ELSE 0 END) clicks_prev_30d,
                SUM(CASE WHEN date BETWEEN date('now','-6 days') AND date('now') THEN suspicious_count ELSE 0 END) suspicious_7d
            FROM daily_stats
            GROUP BY site
        ),
        rk AS (
            SELECT
                site,
                SUM(CASE WHEN date BETWEEN date('now','-6 days') AND date('now') THEN impressions ELSE 0 END) impressions_7d,
                SUM(CASE WHEN date BETWEEN date('now','-13 days') AND date('now','-7 days') THEN impressions ELSE 0 END) impressions_prev_7d,
                SUM(CASE WHEN date BETWEEN date('now','-29 days') AND date('now') THEN impressions ELSE 0 END) impressions_30d,
                SUM(CASE WHEN date BETWEEN date('now','-59 days') AND date('now','-30 days') THEN impressions ELSE 0 END) impressions_prev_30d,
                AVG(CASE WHEN date BETWEEN date('now','-6 days') AND date('now') THEN position END) avg_pos_7d,
                AVG(CASE WHEN date BETWEEN date('now','-29 days') AND date('now') THEN position END) avg_pos_30d
            FROM rank_history
            GROUP BY site
        ),
        up AS (
            SELECT
                REPLACE(REPLACE(site, 'https://', ''), 'http://', '') site_clean,
                is_up,
                last_checked
            FROM uptime_status
        )
        SELECT
            ds.site,
            COALESCE(ms.category, 'Uncategorized') category,
            COALESCE(ms.location, 'Unknown') location,
            COALESCE(ds.keywords_7d, 0) keywords_7d,
            COALESCE(ds.keywords_prev_7d, 0) keywords_prev_7d,
            COALESCE(ds.keywords_30d, 0) keywords_30d,
            COALESCE(ds.keywords_prev_30d, 0) keywords_prev_30d,
            COALESCE(ds.clicks_7d, 0) clicks_7d,
            COALESCE(ds.clicks_prev_7d, 0) clicks_prev_7d,
            COALESCE(ds.clicks_30d, 0) clicks_30d,
            COALESCE(ds.clicks_prev_30d, 0) clicks_prev_30d,
            COALESCE(rk.impressions_7d, 0) impressions_7d,
            COALESCE(rk.impressions_prev_7d, 0) impressions_prev_7d,
            COALESCE(rk.impressions_30d, 0) impressions_30d,
            COALESCE(rk.impressions_prev_30d, 0) impressions_prev_30d,
            COALESCE(rk.avg_pos_7d, 0) avg_pos_7d,
            COALESCE(rk.avg_pos_30d, 0) avg_pos_30d,
            COALESCE(ds.suspicious_7d, 0) suspicious_7d,
            COALESCE(up.is_up, 1) is_up,
            up.last_checked
        FROM ds
        LEFT JOIN rk ON rk.site = ds.site
        LEFT JOIN managed_sites ms ON ms.domain = ds.site
        LEFT JOIN up ON up.site_clean = ds.site
    """) if table_exists(conn, "daily_stats") else pd.DataFrame()

    if site_rows.empty:
        st.info("No site-wise metrics yet. Run scanners from sidebar Quick Actions.")
    else:
        site_rows["risk_score"] = (
            (1 - site_rows["is_up"]) * 1000
            + (site_rows["suspicious_7d"] > 0).astype(int) * 100
            + (site_rows["clicks_7d"] - site_rows["clicks_prev_7d"] < 0).astype(int) * 10
        )
        site_rows = site_rows.sort_values(["risk_score", "suspicious_7d", "clicks_7d"], ascending=[False, False, False])

        st.markdown("---")
        st.subheader("Site-Wise Overview")

        for _, row in site_rows.iterrows():
            status_icon = "🔴" if int(row["is_up"]) == 0 else "🟢"
            with st.expander(f"{status_icon} {row['site']}  |  {row['category']}  |  {row['location']}", expanded=True):
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("Keywords (7d)", f"{int(row['keywords_7d']):,}", delta=delta_text(float(row["keywords_7d"]), float(row["keywords_prev_7d"])))
                with c2:
                    st.metric("Clicks (7d)", f"{int(row['clicks_7d']):,}", delta=delta_text(float(row["clicks_7d"]), float(row["clicks_prev_7d"])))
                with c3:
                    st.metric("Impressions (7d)", f"{int(row['impressions_7d']):,}", delta=delta_text(float(row["impressions_7d"]), float(row["impressions_prev_7d"])))
                with c4:
                    st.metric("Avg Position (7d)", f"{float(row['avg_pos_7d']):.1f}", delta=delta_text(float(row["avg_pos_7d"]), float(row["avg_pos_30d"])))

                d1, d2, d3, d4 = st.columns(4)
                with d1:
                    st.metric("Keywords (30d)", f"{int(row['keywords_30d']):,}", delta=delta_text(float(row["keywords_30d"]), float(row["keywords_prev_30d"])))
                with d2:
                    st.metric("Clicks (30d)", f"{int(row['clicks_30d']):,}", delta=delta_text(float(row["clicks_30d"]), float(row["clicks_prev_30d"])))
                with d3:
                    st.metric("Impressions (30d)", f"{int(row['impressions_30d']):,}", delta=delta_text(float(row["impressions_30d"]), float(row["impressions_prev_30d"])))
                with d4:
                    st.metric("Suspicious (7d)", int(row["suspicious_7d"]))

                st.caption(f"Uptime: {'UP' if int(row['is_up']) == 1 else 'DOWN'} | Last checked: {row['last_checked'] if pd.notna(row['last_checked']) else 'N/A'}")


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
    else:
        st.warning("No suspicious keywords data found. Run `python seo_guardian.py` to populate data.")


# ═══════════════════════════════════════════════════════════════════
# PAGE: ALL KEYWORDS
# ═══════════════════════════════════════════════════════════════════
elif page == "🧾 All Keywords":
    st.title("🧾 All Keywords Explorer")
    st.caption("Every fetched Google Search Console query stored by site and day.")

    if not table_exists(conn, "all_keywords_history"):
        st.warning("No full keyword history table found yet. Run `python seo_guardian.py` once to start collecting all keywords.")
    else:
        sites_df = q(conn, "SELECT DISTINCT site FROM all_keywords_history ORDER BY site")
        minmax_df = q(conn, "SELECT MIN(date) as min_date, MAX(date) as max_date FROM all_keywords_history")

        all_sites = ["All Sites"] + (sites_df["site"].tolist() if not sites_df.empty else [])
        selected_site = st.selectbox("Site", all_sites)

        default_end = datetime.now().date()
        default_start = default_end - timedelta(days=29)
        if not minmax_df.empty and pd.notna(minmax_df.iloc[0]["min_date"]) and pd.notna(minmax_df.iloc[0]["max_date"]):
            db_min = datetime.strptime(str(minmax_df.iloc[0]["min_date"]), "%Y-%m-%d").date()
            db_max = datetime.strptime(str(minmax_df.iloc[0]["max_date"]), "%Y-%m-%d").date()
            default_start = max(db_min, default_start)
            default_end = db_max

        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            start_date = st.date_input("From", value=default_start)
        with c2:
            end_date = st.date_input("To", value=default_end)
        with c3:
            search_term = st.text_input("Keyword contains", value="").strip().lower()

        c4, c5 = st.columns([1, 1])
        with c4:
            min_impressions = st.number_input("Min impressions", min_value=0, value=0, step=1)
        with c5:
            rows_per_page = st.selectbox("Rows per page", [100, 250, 500, 1000, 5000], index=2)

        where_clauses = ["date BETWEEN ? AND ?", "impressions >= ?"]
        params = [str(start_date), str(end_date), int(min_impressions)]

        if selected_site != "All Sites":
            where_clauses.append("site = ?")
            params.append(selected_site)
        if search_term:
            where_clauses.append("LOWER(keyword) LIKE ?")
            params.append(f"%{search_term}%")

        where_sql = " WHERE " + " AND ".join(where_clauses)

        total_df = q(conn, f"SELECT COUNT(*) as c FROM all_keywords_history{where_sql}", tuple(params))
        total_rows = int(total_df.iloc[0]["c"]) if not total_df.empty else 0
        st.metric("Matching Keywords", f"{total_rows:,}")

        if total_rows == 0:
            st.info("No matching keywords found for current filters.")
        else:
            max_page = max(1, (total_rows + int(rows_per_page) - 1) // int(rows_per_page))
            page_num = st.number_input("Page", min_value=1, max_value=max_page, value=1, step=1)
            offset = (int(page_num) - 1) * int(rows_per_page)

            data_sql = f"""
                SELECT date, site, keyword, clicks, impressions, position, ctr
                FROM all_keywords_history
                {where_sql}
                ORDER BY date DESC, impressions DESC, clicks DESC
                LIMIT ? OFFSET ?
            """
            page_df = q(conn, data_sql, tuple(params + [int(rows_per_page), int(offset)]))
            st.dataframe(page_df, use_container_width=True, hide_index=True)

            st.caption(f"Showing page {int(page_num)} of {max_page}")

            csv_page = page_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download current page CSV",
                data=csv_page,
                file_name=f"all_keywords_page_{int(page_num)}.csv",
                mime="text/csv",
            )

            if st.button("Prepare full filtered CSV"):
                full_sql = f"""
                    SELECT date, site, keyword, clicks, impressions, position, ctr
                    FROM all_keywords_history
                    {where_sql}
                    ORDER BY date DESC, impressions DESC, clicks DESC
                """
                full_df = q(conn, full_sql, tuple(params))
                st.download_button(
                    "Download full filtered CSV",
                    data=full_df.to_csv(index=False).encode("utf-8"),
                    file_name="all_keywords_full_filtered.csv",
                    mime="text/csv",
                )


# ═══════════════════════════════════════════════════════════════════
# PAGE: RANK TRACKER
# ═══════════════════════════════════════════════════════════════════
elif page == "📈 Rank Tracker":
    st.title("📈 Rank Tracker")

    if not table_exists(conn, "rank_history"):
        st.warning("No rank history yet. Run `python rank_tracker.py` first.")
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
                    display_latest,
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


