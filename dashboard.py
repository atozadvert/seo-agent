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


def get_known_sites(conn):
    tables = [
        "daily_stats",
        "rank_history",
        "all_keywords_history",
        "suspicious_log",
        "index_tracking",
        "uptime_status",
        "uptime_log",
        "external_links_baseline",
        "redirect_log",
    ]
    sites = set()
    for table in tables:
        if not table_exists(conn, table):
            continue
        try:
            df = q(conn, f"SELECT DISTINCT site FROM {table}")
            for site in df["site"].dropna().astype(str).tolist():
                if site:
                    sites.add(site)
        except Exception:
            continue
    return sorted(sites)


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
    "🚨 SEO Alerts",
    "🟢 Uptime Monitor",
    "📊 Indexing Monitor",
    "🔀 Redirect Tracker",
    "🔗 External Links Monitor",
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
    known_sites = get_known_sites(conn)
    total_sites = len(known_sites)
    down_sites = int(q(conn, "SELECT COUNT(*) c FROM uptime_status WHERE is_up=0").iloc[0]["c"]) if table_exists(conn, "uptime_status") else 0
    suspicious_sites = int(q(conn, "SELECT COUNT(DISTINCT site) c FROM suspicious_log WHERE date BETWEEN date('now','-6 days') AND date('now')").iloc[0]["c"]) if table_exists(conn, "suspicious_log") else 0
    if suspicious_sites == 0 and table_exists(conn, "suspicious_log"):
        suspicious_sites = int(q(conn, "SELECT COUNT(DISTINCT site) c FROM suspicious_log").iloc[0]["c"])

    st.markdown(
        f"""
        <span class='mini-chip chip-blue'>Total Sites: {total_sites}</span>
        <span class='mini-chip chip-red'>Down Sites: {down_sites}</span>
        <span class='mini-chip chip-amber'>Suspicious Sites (7d): {suspicious_sites}</span>
        """,
        unsafe_allow_html=True,
    )
    st.caption("This overview shows the current health of all monitored sites: keywords, clicks, impressions, rankings, suspicious activity, and uptime status.")

    # site-wise dataset for cards (all sites, worst first)
    site_rows = pd.DataFrame({"site": known_sites})
    for col in ["keywords_7d", "keywords_prev_7d", "keywords_30d", "keywords_prev_30d", "clicks_7d", "clicks_prev_7d", "clicks_30d", "clicks_prev_30d", "suspicious_7d", "impressions_7d", "impressions_prev_7d", "impressions_30d", "impressions_prev_30d", "avg_pos_7d", "avg_pos_30d"]:
        site_rows[col] = 0

    if table_exists(conn, "daily_stats"):
        ds = q(conn, """
            SELECT site, date, total_keywords, suspicious_count, total_clicks
            FROM daily_stats
        """)
        if not ds.empty:
            ds["date"] = pd.to_datetime(ds["date"]).dt.normalize()
            ds = ds.sort_values(["site", "date"])
            today = datetime.now().date()
            cutoff_7d = today - timedelta(days=6)
            cutoff_prev_7d = today - timedelta(days=13)
            cutoff_30d = today - timedelta(days=29)
            cutoff_prev_30d = today - timedelta(days=59)

            for site in known_sites:
                site_ds = ds[ds["site"] == site]
                if site_ds.empty:
                    continue

                recent_7d = site_ds[(site_ds["date"].dt.date >= cutoff_7d) & (site_ds["date"].dt.date <= today)]
                prev_7d = site_ds[(site_ds["date"].dt.date >= cutoff_prev_7d) & (site_ds["date"].dt.date < cutoff_7d)]
                recent_30d = site_ds[(site_ds["date"].dt.date >= cutoff_30d) & (site_ds["date"].dt.date <= today)]
                prev_30d = site_ds[(site_ds["date"].dt.date >= cutoff_prev_30d) & (site_ds["date"].dt.date < cutoff_30d)]
                latest_row = site_ds.iloc[-1]

                site_rows.loc[site_rows["site"] == site, "keywords_7d"] = int(recent_7d["total_keywords"].sum()) if not recent_7d.empty else int(latest_row["total_keywords"])
                site_rows.loc[site_rows["site"] == site, "keywords_prev_7d"] = int(prev_7d["total_keywords"].sum()) if not prev_7d.empty else 0
                site_rows.loc[site_rows["site"] == site, "keywords_30d"] = int(recent_30d["total_keywords"].sum()) if not recent_30d.empty else int(latest_row["total_keywords"])
                site_rows.loc[site_rows["site"] == site, "keywords_prev_30d"] = int(prev_30d["total_keywords"].sum()) if not prev_30d.empty else 0
                site_rows.loc[site_rows["site"] == site, "clicks_7d"] = int(recent_7d["total_clicks"].sum()) if not recent_7d.empty else int(latest_row["total_clicks"])
                site_rows.loc[site_rows["site"] == site, "clicks_prev_7d"] = int(prev_7d["total_clicks"].sum()) if not prev_7d.empty else 0
                site_rows.loc[site_rows["site"] == site, "clicks_30d"] = int(recent_30d["total_clicks"].sum()) if not recent_30d.empty else int(latest_row["total_clicks"])
                site_rows.loc[site_rows["site"] == site, "clicks_prev_30d"] = int(prev_30d["total_clicks"].sum()) if not prev_30d.empty else 0
                site_rows.loc[site_rows["site"] == site, "suspicious_7d"] = int(recent_7d["suspicious_count"].sum()) if not recent_7d.empty else int(latest_row["suspicious_count"])

    if table_exists(conn, "rank_history"):
        rk = q(conn, """
            SELECT site, date, impressions, position
            FROM rank_history
        """)
        if not rk.empty:
            rk["date"] = pd.to_datetime(rk["date"]).dt.normalize()
            rk = rk.sort_values(["site", "date"])
            today = datetime.now().date()
            cutoff_7d = today - timedelta(days=6)
            cutoff_prev_7d = today - timedelta(days=13)
            cutoff_30d = today - timedelta(days=29)
            cutoff_prev_30d = today - timedelta(days=59)

            for site in known_sites:
                site_rk = rk[rk["site"] == site]
                if site_rk.empty:
                    continue

                recent_7d = site_rk[(site_rk["date"].dt.date >= cutoff_7d) & (site_rk["date"].dt.date <= today)]
                prev_7d = site_rk[(site_rk["date"].dt.date >= cutoff_prev_7d) & (site_rk["date"].dt.date < cutoff_7d)]
                recent_30d = site_rk[(site_rk["date"].dt.date >= cutoff_30d) & (site_rk["date"].dt.date <= today)]
                prev_30d = site_rk[(site_rk["date"].dt.date >= cutoff_prev_30d) & (site_rk["date"].dt.date < cutoff_30d)]
                latest_row = site_rk.iloc[-1]

                site_rows.loc[site_rows["site"] == site, "impressions_7d"] = int(recent_7d["impressions"].sum()) if not recent_7d.empty else int(latest_row["impressions"])
                site_rows.loc[site_rows["site"] == site, "impressions_prev_7d"] = int(prev_7d["impressions"].sum()) if not prev_7d.empty else 0
                site_rows.loc[site_rows["site"] == site, "impressions_30d"] = int(recent_30d["impressions"].sum()) if not recent_30d.empty else int(latest_row["impressions"])
                site_rows.loc[site_rows["site"] == site, "impressions_prev_30d"] = int(prev_30d["impressions"].sum()) if not prev_30d.empty else 0
                site_rows.loc[site_rows["site"] == site, "avg_pos_7d"] = float(recent_7d["position"].mean()) if not recent_7d.empty else float(latest_row["position"])
                site_rows.loc[site_rows["site"] == site, "avg_pos_30d"] = float(recent_30d["position"].mean()) if not recent_30d.empty else float(latest_row["position"])

    if table_exists(conn, "uptime_status"):
        up = q(conn, """
            SELECT REPLACE(REPLACE(site, 'https://', ''), 'http://', '') AS site_clean,
                   is_up,
                   last_checked
            FROM uptime_status
        """)
        if not up.empty:
            up = up.rename(columns={"site_clean": "site"})
            site_rows = site_rows.merge(up, on="site", how="left")

    for col in ["keywords_7d", "keywords_prev_7d", "keywords_30d", "keywords_prev_30d", "clicks_7d", "clicks_prev_7d", "clicks_30d", "clicks_prev_30d", "suspicious_7d", "impressions_7d", "impressions_prev_7d", "impressions_30d", "impressions_prev_30d", "avg_pos_7d", "avg_pos_30d"]:
        if col in site_rows.columns:
            site_rows[col] = pd.to_numeric(site_rows[col], errors="coerce").fillna(0)
    site_rows["category"] = "Uncategorized"
    site_rows["location"] = "Unknown"
    site_rows["is_up"] = pd.to_numeric(site_rows["is_up"], errors="coerce").fillna(1)
    site_rows["last_checked"] = site_rows["last_checked"].replace({None: pd.NA})

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
    st.caption("This page lists keywords that look unusual or risky, such as sudden spikes in traffic or suspicious categories that may indicate spam or low-quality activity.")

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
    st.caption("This page shows the full keyword history collected from Google Search Console, including impressions, clicks, position, and CTR for each day.")

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
    st.caption("This page tracks how your target keywords are ranking over time, so you can see gains, drops, and recent movement for each site.")

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
# PAGE: SEO ALERTS
# ═══════════════════════════════════════════════════════════════════
elif page == "🚨 SEO Alerts":
    st.title("🚨 SEO Alerts")
    st.caption("This page brings together the main issues detected across the setup so you can quickly spot what needs attention.")

    alerts = []

    if table_exists(conn, "suspicious_log"):
        suspicious = q(conn, """
            SELECT site, keyword, category, clicks, impressions, position, date
            FROM suspicious_log
            WHERE date >= date('now','-7 days')
            ORDER BY date DESC, clicks DESC
        """)
        if not suspicious.empty:
            for _, row in suspicious.iterrows():
                severity = "High" if int(row.get("clicks", 0) or 0) > 0 or int(row.get("impressions", 0) or 0) > 100 else "Medium"
                alerts.append({
                    "date": row.get("date"),
                    "severity": severity,
                    "category": "Suspicious Keyword",
                    "site": row.get("site"),
                    "summary": row.get("keyword"),
                    "details": f"Category: {row.get('category')} | Clicks: {row.get('clicks')} | Impressions: {row.get('impressions')} | Position: {row.get('position')}"
                })

    if table_exists(conn, "redirect_log"):
        redirects = q(conn, """
            SELECT site, issues, redirect_hops, detected_date
            FROM redirect_log
            WHERE date(detected_date) >= date('now','-7 days')
            ORDER BY detected_date DESC
        """)
        if not redirects.empty:
            for _, row in redirects.iterrows():
                severity = "High" if int(row.get("redirect_hops", 0) or 0) > 2 else "Medium"
                alerts.append({
                    "date": row.get("detected_date"),
                    "severity": severity,
                    "category": "Redirect Issue",
                    "site": row.get("site"),
                    "summary": row.get("issues"),
                    "details": f"Redirect hops: {row.get('redirect_hops')}"
                })

    if table_exists(conn, "index_tracking"):
        idx = q(conn, """
            SELECT site, date, page_count FROM index_tracking
            ORDER BY site, date ASC
        """)
        if not idx.empty:
            for site in sorted(idx["site"].dropna().unique()):
                site_df = idx[idx["site"] == site].sort_values("date")
                if len(site_df) < 2:
                    continue
                prev_count = int(site_df["page_count"].iloc[-2]) if len(site_df) >= 2 else 0
                latest_count = int(site_df["page_count"].iloc[-1])
                if prev_count <= 0:
                    continue
                change_pct = round(((latest_count - prev_count) / prev_count) * 100, 1)
                if abs(change_pct) >= 30:
                    severity = "High" if abs(change_pct) >= 50 else "Medium"
                    alerts.append({
                        "date": site_df["date"].iloc[-1],
                        "severity": severity,
                        "category": "Indexing Change",
                        "site": site,
                        "summary": f"Indexed pages {change_pct:+.1f}%",
                        "details": f"Previous: {prev_count} | Latest: {latest_count}"
                    })

    if table_exists(conn, "rank_alerts"):
        rank_alerts = q(conn, """
            SELECT timestamp, site, keyword, old_pos, new_pos, change, alert_type
            FROM rank_alerts
            WHERE datetime(timestamp) >= datetime('now','-7 days')
            ORDER BY timestamp DESC
        """)
        if not rank_alerts.empty:
            for _, row in rank_alerts.iterrows():
                alerts.append({
                    "date": row.get("timestamp"),
                    "severity": "High" if abs(int(row.get("change", 0) or 0)) >= 10 else "Medium",
                    "category": "Rank Alert",
                    "site": row.get("site"),
                    "summary": row.get("keyword"),
                    "details": f"{row.get('alert_type')} | Old: {row.get('old_pos')} | New: {row.get('new_pos')} | Change: {row.get('change')}"
                })

    if table_exists(conn, "uptime_status"):
        downtime = q(conn, """
            SELECT site, consecutive_fails, last_checked
            FROM uptime_status
            WHERE is_up = 0
        """)
        if not downtime.empty:
            for _, row in downtime.iterrows():
                alerts.append({
                    "date": row.get("last_checked"),
                    "severity": "High" if int(row.get("consecutive_fails", 0) or 0) >= 3 else "Medium",
                    "category": "Uptime Issue",
                    "site": row.get("site"),
                    "summary": "Site down",
                    "details": f"Consecutive fails: {row.get('consecutive_fails')}"
                })

    if alerts:
        alerts_df = pd.DataFrame(alerts)
        severity_rank = {"High": 0, "Medium": 1, "Low": 2}
        alerts_df["severity_rank"] = alerts_df["severity"].map(severity_rank).fillna(3)
        alerts_df = alerts_df.sort_values(["severity_rank", "date"], ascending=[True, False])
        alerts_df = alerts_df.drop(columns=["severity_rank"])

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Total Alerts", len(alerts_df))
        with c2:
            st.metric("High Priority", int((alerts_df["severity"] == "High").sum()))
        with c3:
            st.metric("Alert Categories", alerts_df["category"].nunique())

        st.markdown("---")
        st.subheader("Latest Alerts")
        st.dataframe(alerts_df[["date", "severity", "category", "site", "summary", "details"]], use_container_width=True, hide_index=True)

        st.subheader("Alerts by Category")
        cat_counts = alerts_df["category"].value_counts().reset_index()
        cat_counts.columns = ["Category", "Count"]
        st.bar_chart(cat_counts.set_index("Category"))
    else:
        st.success("✅ No recent alerts found.")

# ═══════════════════════════════════════════════════════════════════
# PAGE: UPTIME MONITOR
# ═══════════════════════════════════════════════════════════════════
elif page == "🟢 Uptime Monitor":
    st.title("🟢 Uptime Monitor")
    st.caption("This page shows whether each site is currently reachable and how its response time and downtime history look over time.")

    if not table_exists(conn, "uptime_status") and not table_exists(conn, "uptime_log"):
        st.warning("No uptime data yet. Run `python uptime_monitor.py` first.")
    else:
        known_sites = get_known_sites(conn)
        status_df = q(conn, "SELECT site, is_up, last_checked, down_since, consecutive_fails FROM uptime_status")
        if status_df.empty:
            status_df = pd.DataFrame(columns=["site", "is_up", "last_checked", "down_since", "consecutive_fails"])
        else:
            for col in ["site", "is_up", "last_checked", "down_since", "consecutive_fails"]:
                if col not in status_df.columns:
                    status_df[col] = pd.NA

        status_df["site"] = status_df["site"].astype(str).str.replace("https://", "", regex=False).str.rstrip("/")
        status_df = pd.DataFrame({"site": known_sites}).merge(status_df, on="site", how="left")
        status_df["is_up"] = pd.to_numeric(status_df["is_up"], errors="coerce")
        status_df["consecutive_fails"] = pd.to_numeric(status_df["consecutive_fails"], errors="coerce").fillna(0).astype(int)
        status_df["Status"] = status_df["is_up"].apply(lambda x: "🟢 UP" if x == 1 else "🔴 DOWN" if x == 0 else "⚪ UNKNOWN")
        status_df["last_checked_display"] = status_df["last_checked"].apply(
            lambda x: "Not checked" if pd.isna(x) else pd.to_datetime(x).strftime("%d %b %I:%M %p")
        )
        display_df = status_df[["site", "Status", "last_checked_display", "consecutive_fails", "down_since"]]
        display_df.columns = ["Site", "Status", "Last Checked", "Consecutive Fails", "Down Since"]
        st.subheader("Current Status")
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        if table_exists(conn, "uptime_log"):
            st.subheader("Response Times — Last 24h")
            rt_df = q(conn, """
                SELECT timestamp, site, response_time, is_up
                FROM uptime_log
                WHERE response_time IS NOT NULL
                ORDER BY timestamp ASC
            """)
            if not rt_df.empty:
                rt_df["site"] = rt_df["site"].astype(str).str.replace("https://", "", regex=False).str.rstrip("/")
                sites = sorted(rt_df["site"].unique().tolist())
                sel = st.multiselect("Select sites", sites, default=sites)
                filtered = rt_df[rt_df["site"].isin(sel)] if sel else rt_df
                if not filtered.empty:
                    fig = px.line(filtered, x="timestamp", y="response_time", color="site",
                                  labels={"response_time": "Response Time (s)", "timestamp": "Time"})
                    fig.add_hline(y=3, line_dash="dot", line_color="orange", annotation_text="Slow threshold (3s)")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Select at least one site to view response-time history.")

            st.subheader("📋 Downtime Incidents")
            incidents = q(conn, """
                SELECT timestamp, site, status_code, response_time, error
                FROM uptime_log WHERE is_up=0
                ORDER BY timestamp DESC LIMIT 100
            """)
            if not incidents.empty:
                incidents["site"] = incidents["site"].astype(str).str.replace("https://", "", regex=False).str.rstrip("/")
                st.dataframe(incidents, use_container_width=True, hide_index=True)
            else:
                st.success("✅ No downtime incidents recorded!")


# ═══════════════════════════════════════════════════════════════════
# PAGE: ADVANCED MONITOR
# ═══════════════════════════════════════════════════════════════════
elif page == "📊 Indexing Monitor":
    st.title("📊 Indexing Monitor")
    st.caption("Daily indexed-page counts from Google Search Console")

    if not table_exists(conn, "index_tracking"):
        st.warning("No indexing data yet. Run `python advanced_monitor.py` first.")
    else:
        idx_df = q(conn, """
            SELECT site, date, page_count FROM index_tracking
            ORDER BY site, date ASC
        """)
        if idx_df.empty:
            st.info("No indexing records found yet.")
        else:
            idx_df["site"] = idx_df["site"].str.replace("https://", "", regex=False).str.replace("sc-domain:", "", regex=False).str.rstrip("/")
            idx_df["page_count"] = pd.to_numeric(idx_df["page_count"], errors="coerce").fillna(0).astype(int)

            summary_rows = []
            for site in sorted(idx_df["site"].unique()):
                site_df = idx_df[idx_df["site"] == site].sort_values("date")
                counts = site_df["page_count"].tolist()
                summary_rows.append({
                    "site": site,
                    "latest_date": site_df["date"].iloc[-1],
                    "latest_count": int(counts[-1]),
                    "first_count": int(counts[0]),
                    "change": int(counts[-1] - counts[0]),
                    "min_count": int(min(counts)),
                    "max_count": int(max(counts)),
                    "avg_count": round(sum(counts) / len(counts), 1),
                })

            summary_df = pd.DataFrame(summary_rows).sort_values(["latest_count", "change"], ascending=[False, False])
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Sites Tracked", len(summary_df))
            with c2:
                top_site = summary_df.iloc[0] if not summary_df.empty else None
                st.metric("Highest Latest Count", int(top_site["latest_count"]) if top_site is not None else 0, help=top_site["site"] if top_site is not None else None)
            with c3:
                biggest_gain = summary_df.sort_values("change", ascending=False).iloc[0] if not summary_df.empty else None
                st.metric("Biggest Change", int(biggest_gain["change"]) if biggest_gain is not None else 0, help=biggest_gain["site"] if biggest_gain is not None else None)

            st.markdown("---")
            st.subheader("Site Summary")
            st.dataframe(summary_df, use_container_width=True, hide_index=True)

            st.subheader("Indexed Pages Over Time")
            st.caption("This chart shows how many pages per site were reported in Google Search Console over time. Use the selector to compare any subset of sites.")
            all_sites = sorted(idx_df["site"].unique())
            sel_sites = st.multiselect("Select sites", all_sites, default=[])
            filtered = idx_df[idx_df["site"].isin(sel_sites)] if sel_sites else idx_df
            if not filtered.empty:
                fig = px.line(filtered, x="date", y="page_count", color="site",
                              markers=True, labels={"page_count": "Indexed Pages", "date": "Date"})
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Select at least one site to view the trend chart.")

elif page == "🔀 Redirect Tracker":
    st.title("🔀 Redirect Tracker")
    st.caption("This page highlights redirect problems such as long chains or suspicious destination URLs that may affect crawlability or trust.")

    if not table_exists(conn, "redirect_log"):
        st.info("No redirect data yet. Run `python advanced_monitor.py` first.")
    else:
        redir_df = q(conn, """
            SELECT site, page_url, final_url, redirect_hops, issues, detected_date
            FROM redirect_log
            ORDER BY detected_date DESC, redirect_hops DESC
        """)
        if redir_df.empty:
            st.success("✅ No redirect issues logged.")
        else:
            redir_df["site"] = redir_df["site"].str.replace("https://", "", regex=False).str.rstrip("/")
            redir_df["issues"] = redir_df["issues"].fillna("")
            issue_breakdown = (
                redir_df["issues"].str.split(" | ", expand=False)
                .explode()
                .dropna()
                .loc[lambda s: s != ""]
                .value_counts()
                .reset_index()
            )
            issue_breakdown.columns = ["Issue", "Count"]

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Redirect Issues", len(redir_df))
            with c2:
                st.metric("Sites Affected", redir_df["site"].nunique())
            with c3:
                st.metric("Max Redirect Hops", int(redir_df["redirect_hops"].max()) if not redir_df.empty else 0)

            st.markdown("---")
            st.subheader("Issue Breakdown")
            if not issue_breakdown.empty:
                st.dataframe(issue_breakdown, use_container_width=True, hide_index=True)
            else:
                st.info("No issue labels available yet.")

            st.subheader("Recent Redirect Records")
            st.dataframe(redir_df, use_container_width=True, hide_index=True)

elif page == "🔗 External Links Monitor":
    st.title("🔗 External Links Monitor")
    st.caption("This page shows outbound links found on your pages so you can review whether unexpected or spammy links have appeared.")

    if not table_exists(conn, "external_links_baseline"):
        st.info("No external link data yet. Run `python advanced_monitor.py` first.")
    else:
        links_df = q(conn, """
            SELECT site, link_url, first_seen
            FROM external_links_baseline
            ORDER BY first_seen DESC, site ASC
        """)
        if links_df.empty:
            st.info("No external links recorded yet.")
        else:
            links_df["site"] = links_df["site"].str.replace("https://", "", regex=False).str.rstrip("/")
            site_counts = (
                links_df.groupby("site", as_index=False)
                .size()
                .rename(columns={"size": "link_count"})
                .sort_values("link_count", ascending=False)
            )

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Tracked Link Records", len(links_df))
            with c2:
                st.metric("Sites With Links", links_df["site"].nunique())
            with c3:
                st.metric("Most Linked Site", site_counts.iloc[0]["site"] if not site_counts.empty else "—", help=site_counts.iloc[0]["link_count"] if not site_counts.empty else None)

            st.markdown("---")
            st.subheader("Links by Site")
            st.dataframe(site_counts, use_container_width=True, hide_index=True)

            st.subheader("Tracked External Links")
            st.dataframe(links_df, use_container_width=True, hide_index=True)


