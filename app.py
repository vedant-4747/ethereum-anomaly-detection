"""
app.py — Streamlit dashboard for Ethereum On-chain Anomaly Detection.
"""

import datetime
import time
from dotenv import load_dotenv
load_dotenv(override=True)   # Always read .env before anything else

import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh   # Non-blocking refresh
import database

# ─── Page config (MUST be first Streamlit call) ───────────────────────
st.set_page_config(
    page_title="ETHWatch — Ethereum Anomaly Detector",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

database.init_db()

# ─── Helpers ──────────────────────────────────────────────────────────
import base64

def _img_b64(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""

hero_b64 = _img_b64("assets/hero.png")
SEVERITY_COLORS = {"HIGH": "#ff4b4b", "MEDIUM": "#ffa421", "LOW": "#21c354"}

LEVEL_COLORS = {
    "INFO":    "#4df2d8",
    "WARNING": "#ffa421",
    "ERROR":   "#ff4b4b",
    "DEBUG":   "#a095d5",
    "CRITICAL":"#ff4b4b",
}

# ─── CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');

/* Background */
html, body, [data-testid="stAppViewContainer"] {
    background: linear-gradient(160deg, #090214 0%, #18053a 45%, #1c0440 100%);
    color: #d8d0f0;
    font-family: 'Inter', sans-serif;
}
[data-testid="stDecoration"],
[data-testid="collapsedControl"],
header, footer { display: none !important; }
.block-container { padding: 1rem 3rem !important; max-width: 1400px !important; }

/* Metric cards */
[data-testid="metric-container"] {
    background: linear-gradient(135deg,rgba(30,10,60,.85),rgba(50,18,90,.7));
    border: 1px solid rgba(164,94,229,.3);
    border-radius: 14px;
    padding: 22px;
    box-shadow: 0 4px 20px rgba(0,0,0,.4);
}
[data-testid="stMetricLabel"]  { color: #a095d5 !important; font-size: 13px !important; }
[data-testid="stMetricValue"]  { color: #fff    !important; font-size: 30px !important; font-weight: 800 !important; }

/* Buttons */
.stButton > button {
    background: linear-gradient(90deg,#8A2BE2,#6a1bb3) !important;
    color: #fff !important;
    border: 1px solid rgba(180,120,255,.4) !important;
    padding: 10px 28px !important;
    border-radius: 6px !important;
    font-weight: 700 !important;
    letter-spacing: .8px !important;
    white-space: nowrap !important;
    box-shadow: 0 4px 18px rgba(138,43,226,.35) !important;
    transition: all .25s ease !important;
}
.stButton > button:hover {
    box-shadow: 0 6px 28px rgba(138,43,226,.65) !important;
    transform: translateY(-2px) !important;
}

/* ── Horizontal radio nav ── */
div[role="radiogroup"] {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: nowrap;
}
div[role="radiogroup"] label {
    display: flex;
    align-items: center;
    padding: 6px 14px;
    border-radius: 6px;
    cursor: pointer;
    color: #b8a8d8;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: .5px;
    white-space: nowrap;
    border: 1px solid transparent;
    background: transparent;
    transition: all .2s ease;
}
div[role="radiogroup"] label:hover {
    color: #fff;
    background: rgba(164,94,229,.15);
    border-color: rgba(164,94,229,.3);
}
/* active tab highlight */
div[role="radiogroup"] label[data-checked="true"] {
    color: #fff !important;
    background: rgba(138,43,226,.3) !important;
    border-color: rgba(164,94,229,.5) !important;
}
/* hide radio circles */
input[type="radio"] { display: none !important; }
[data-testid="stMarkdownContainer"] p { margin: 0; }

/* Dataframe */
[data-testid="stDataFrame"] {
    border: 1px solid rgba(164,94,229,.2);
    border-radius: 12px;
    overflow: hidden;
}

/* Alerts */
[data-testid="stAlert"] {
    background: rgba(30,10,60,.6) !important;
    border: 1px solid rgba(164,94,229,.3) !important;
    border-radius: 10px !important;
}

/* Sidebar */
[data-testid="stSidebarContent"] {
    background: linear-gradient(180deg,#12033a,#200445) !important;
    border-right: 1px solid rgba(164,94,229,.2);
}

hr { border-color: rgba(164,94,229,.15) !important; margin: 8px 0 20px !important; }

/* Animated scanning bar */
@keyframes scan {
    0%   { background-position: 0% 50%; }
    100% { background-position: 200% 50%; }
}
.scan-bar {
    height: 14px;
    width: 100%;
    background: linear-gradient(90deg,#8A2BE2,#4df2d8,#8A2BE2);
    background-size: 200% 100%;
    border-radius: 7px;
    animation: scan 2.5s linear infinite;
}

/* Live badge */
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
.live {
    display: inline-block;
    background: #21c354;
    color: #fff;
    font-size: .65rem;
    border-radius: 999px;
    padding: 2px 8px;
    margin-left: 8px;
    animation: pulse 2s infinite;
    font-weight: 700;
}

/* Last-updated pill */
.ts-pill {
    display: inline-block;
    background: rgba(138,43,226,.18);
    border: 1px solid rgba(164,94,229,.35);
    border-radius: 999px;
    padding: 2px 12px;
    font-size: .72rem;
    color: #b8a8d8;
    margin-left: 10px;
}

/* Lifetime count badge */
.lifetime-badge {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    background: linear-gradient(135deg, rgba(138,43,226,.18), rgba(77,242,216,.08));
    border: 1px solid rgba(164,94,229,.35);
    border-radius: 12px;
    padding: 10px 20px;
    margin-bottom: 18px;
}
.lifetime-badge .lb-label {
    font-size: 12px;
    color: #a095d5;
    font-weight: 600;
    letter-spacing: .5px;
    text-transform: uppercase;
}
.lifetime-badge .lb-count {
    font-size: 22px;
    font-weight: 800;
    color: #fff;
}
.lifetime-badge .lb-icon { font-size: 18px; }

/* ── Terminal log panel ── */
.log-terminal {
    background: #050c14;
    border: 1px solid rgba(77,242,216,.25);
    border-radius: 12px;
    padding: 16px 18px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 12px;
    line-height: 1.65;
    max-height: 420px;
    overflow-y: auto;
    box-shadow: 0 0 30px rgba(77,242,216,.07), inset 0 0 60px rgba(0,0,0,.4);
}
.log-terminal::-webkit-scrollbar { width: 4px; }
.log-terminal::-webkit-scrollbar-track { background: transparent; }
.log-terminal::-webkit-scrollbar-thumb { background: rgba(164,94,229,.4); border-radius: 2px; }
.log-line-INFO     { color: #4df2d8; }
.log-line-WARNING  { color: #ffa421; }
.log-line-ERROR    { color: #ff4b4b; }
.log-line-CRITICAL { color: #ff4b4b; font-weight: 700; }
.log-line-DEBUG    { color: #6a5f9e; }

/* Terminal header bar */
.term-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    padding-bottom: 10px;
    border-bottom: 1px solid rgba(77,242,216,.15);
}
.term-dot { width: 10px; height: 10px; border-radius: 50%; }
.term-dot-r { background: #ff5f56; }
.term-dot-y { background: #ffbd2e; }
.term-dot-g { background: #27c93f; }
.term-title { font-size: 11px; color: #6a9fb8; font-family: 'JetBrains Mono', monospace; margin-left: 6px; }

/* Week badge */
.week-badge {
    display: inline-block;
    background: rgba(77,242,216,.12);
    border: 1px solid rgba(77,242,216,.3);
    border-radius: 999px;
    padding: 2px 12px;
    font-size: .7rem;
    color: #4df2d8;
    font-weight: 600;
    margin-left: 10px;
    vertical-align: middle;
}
</style>
""", unsafe_allow_html=True)

# ─── Session state init ───────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "🏠 Home"

# ─── Nav definition ───────────────────────────────────────────────────
NAV_LABELS = ["🏠 Home", "🚨 Anomalies", "📊 Stats", "🖥️ Live Logs", "ℹ️ About", "⚙️ How It Works", "❓ FAQ"]

# ─── Navbar ───────────────────────────────────────────────────────────
col_brand, col_nav, col_live = st.columns([1.4, 6.5, 1.1])

with col_brand:
    st.markdown(
        '<div style="padding-top:6px;font-size:21px;font-weight:800;'
        'color:#fff;white-space:nowrap;">🔍 <span style="color:#a45ee5;">ETH</span>Watch</div>',
        unsafe_allow_html=True,
    )

with col_nav:
    selected = st.radio(
        "nav",
        options=NAV_LABELS,
        horizontal=True,
        label_visibility="collapsed",
        key="nav_radio",
        index=NAV_LABELS.index(st.session_state.get("page", "🏠 Home"))
              if st.session_state.get("page", "🏠 Home") in NAV_LABELS else 0,
    )
    st.session_state.page = selected

with col_live:
    auto_refresh = st.toggle("⚡ Live", value=True, key="auto_refresh")

st.markdown("<hr>", unsafe_allow_html=True)

# ─── Settings sidebar ─────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Settings")
    refresh_rate    = st.slider("Refresh interval (s)", 3, 60, 10)
    max_rows        = st.slider("Rows to display", 10, 200, 50)
    severity_filter = st.multiselect(
        "Filter by severity",
        options=["HIGH", "MEDIUM", "LOW"],
        default=["HIGH", "MEDIUM", "LOW"],
    )
    log_lines = st.slider("Log lines to show", 20, 100, 60)
    st.divider()
    st.markdown("**Data source:** `PostgreSQL (Supabase)`")
    st.markdown("[Etherscan](https://etherscan.io)")

# ─── Non-blocking auto-refresh ────────────────────────────────────────
current_page = st.session_state.get("page", "🏠 Home")
LIVE_PAGES   = {"🏠 Home", "🚨 Anomalies", "📊 Stats", "🖥️ Live Logs"}

if auto_refresh and current_page in LIVE_PAGES:
    st_autorefresh(interval=refresh_rate * 1000, key="live_refresh")

# ─── Cached data fetchers ──────────────────────────────────────────────
@st.cache_data(ttl=refresh_rate)
def fetch_stats():
    return database.get_stats()

@st.cache_data(ttl=refresh_rate)
def fetch_recent_anomalies(limit: int):
    return database.get_recent_anomalies(limit=limit)

@st.cache_data(ttl=refresh_rate)
def fetch_week_anomalies(days: int = 7, limit: int = 500):
    """Anomalies from the last `days` days."""
    return database.get_recent_anomalies_since(days=days, limit=limit)

@st.cache_data(ttl=60)
def fetch_lifetime_stats():
    """Lifetime total + breakdown — cached for 60s (low priority data)."""
    return database.get_total_anomaly_count()

@st.cache_data(ttl=refresh_rate)
def fetch_monitor_logs(limit: int = 80):
    return database.get_monitor_logs(limit=limit)

@st.cache_data(ttl=30)
def fetch_latest_block() -> int:
    return database.get_latest_block()

def _last_updated_pill() -> str:
    now = datetime.datetime.utcnow().strftime("%H:%M:%S UTC")
    return f'<span class="ts-pill">🕒 Updated {now}</span>'

def _monitor_staleness_banner(records: list) -> None:
    """Show a warning if the newest DB record is older than 30 minutes."""
    if not records:
        return
    try:
        newest_ts = pd.to_datetime(records[0]["timestamp"], utc=True)
        age_minutes = (pd.Timestamp.utcnow() - newest_ts).total_seconds() / 60
        if age_minutes > 30:
            st.warning(
                f"⚠️ **Monitor may be down.** The newest anomaly is "
                f"**{int(age_minutes)} minutes** old. "
                "Check the Render Background Worker logs.",
                icon="⚠️",
            )
    except Exception:
        pass


def _lifetime_badge(lifetime: dict) -> None:
    """Render compact lifetime count badge + collapsible expander."""
    total = lifetime.get("total", 0)
    by_type = lifetime.get("by_type", {})
    by_sev  = lifetime.get("by_severity", {})

    # ── Compact badge ──
    st.markdown(
        f'''<div class="lifetime-badge">
  <span class="lb-icon">📦</span>
  <div>
    <div class="lb-label">Lifetime Total</div>
    <div class="lb-count">{total:,}</div>
  </div>
  <div style="margin-left:20px;">
    <div class="lb-label">All-time HIGH</div>
    <div class="lb-count" style="color:#ff4b4b;">{by_sev.get("HIGH",0):,}</div>
  </div>
  <div style="margin-left:20px;">
    <div class="lb-label">All-time MEDIUM</div>
    <div class="lb-count" style="color:#ffa421;">{by_sev.get("MEDIUM",0):,}</div>
  </div>
</div>''',
        unsafe_allow_html=True,
    )

    # ── Collapsible detailed breakdown ──
    with st.expander("📊 View full lifetime breakdown", expanded=False):
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**By Type**")
            if by_type:
                type_df = pd.DataFrame(list(by_type.items()), columns=["Type", "Count"]).sort_values("Count", ascending=False)
                st.dataframe(type_df, use_container_width=True, hide_index=True)
            else:
                st.caption("No data yet.")
        with col_b:
            st.markdown("**By Severity**")
            if by_sev:
                sev_df = pd.DataFrame(list(by_sev.items()), columns=["Severity", "Count"]).sort_values("Count", ascending=False)
                st.dataframe(sev_df, use_container_width=True, hide_index=True)
            else:
                st.caption("No data yet.")


def _render_log_terminal(logs: list, title: str = "monitor.py — Live Output") -> None:
    """Render a terminal-style scrollable log panel."""
    if not logs:
        st.markdown(
            '<div class="log-terminal">'
            '<span style="color:#4a4060;">⏳ Waiting for monitor logs… '
            'Logs appear here once the monitor starts running.</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    lines_html = ""
    for row in logs:
        ts  = pd.to_datetime(row["ts"]).strftime("%H:%M:%S")
        lvl = row.get("level", "INFO")
        msg = row.get("message", "")
        # Escape HTML special chars
        msg = msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        color = LEVEL_COLORS.get(lvl, "#c9bdeb")
        lines_html += (
            f'<div class="log-line-{lvl}">'
            f'<span style="color:#4a4060;">{ts}</span> '
            f'<span style="color:{color};font-weight:600;">[{lvl:8s}]</span> '
            f'<span style="color:#c9e8d5;">{msg}</span>'
            f'</div>'
        )

    st.markdown(
        f'''<div>
  <div class="term-header">
    <div class="term-dot term-dot-r"></div>
    <div class="term-dot term-dot-y"></div>
    <div class="term-dot term-dot-g"></div>
    <span class="term-title">● {title}</span>
    <span class="live" style="margin-left:auto;">LIVE</span>
  </div>
  <div class="log-terminal">{lines_html}</div>
</div>''',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════
# PAGE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def page_home():
    stats   = fetch_stats()
    total   = stats.get("total_anomalies", 0)
    by_type = stats.get("anomalies_by_type", {})
    high_cnt = by_type.get("High Value Transfer", 0)
    med_cnt  = sum(v for k, v in by_type.items() if "Gas" in k or "Contract" in k)

    hero_l, hero_r = st.columns([1, 1], gap="large")

    with hero_l:
        st.markdown("""
<div style="padding-top:24px;">
  <div style="font-size:44px;font-weight:800;line-height:1.2;
              background:-webkit-linear-gradient(45deg,#4df2d8,#a45ee5);
              -webkit-background-clip:text;-webkit-text-fill-color:transparent;
              margin-bottom:16px;">
    Ethereum On-chain<br>Anomaly Detection<br>Platform
  </div>
  <div style="font-size:16px;color:#c9bdeb;line-height:1.75;margin-bottom:32px;">
    Real-time monitoring of the Ethereum mainnet for<br>
    suspicious transactions, flash loan attacks &amp; gas manipulation.
  </div>
</div>
""", unsafe_allow_html=True)
        b1, b2, _ = st.columns([1, 1, 1])
        with b1:
            if st.button("🔍 SCAN NOW", key="hero_scan", use_container_width=True):
                st.session_state.page = "🚨 Anomalies"
                st.rerun()
        with b2:
            if st.button("🖥️ LIVE LOGS", key="hero_logs", use_container_width=True):
                st.session_state.page = "🖥️ Live Logs"
                st.rerun()

    with hero_r:
        if hero_b64:
            st.markdown(
                f'<img src="data:image/png;base64,{hero_b64}" width="100%"'
                ' style="border-radius:14px;filter:drop-shadow(0 0 22px rgba(138,43,226,.4));">'
                , unsafe_allow_html=True
            )

    st.divider()

    low_l, low_r = st.columns([1, 1], gap="large")

    with low_l:
        st.markdown("""
<div style="background:rgba(22,11,46,.65);border:1px solid rgba(164,94,229,.22);
            border-radius:14px;padding:28px 30px;box-shadow:0 10px 40px rgba(0,0,0,.5);">
  <div style="text-align:center;font-size:16px;font-weight:700;color:#e0d4ff;margin-bottom:22px;">
    Live Monitor Status
  </div>
  <div style="display:flex;justify-content:space-between;font-size:12px;color:#a095b5;margin-bottom:6px;">
    <span>Idle</span><span>Scanning</span><span>Alert</span>
  </div>
  <div style="width:100%;height:14px;background:rgba(0,0,0,.4);border-radius:7px;
              border:1px solid rgba(255,255,255,.05);overflow:hidden;margin-bottom:24px;">
    <div class="scan-bar"></div>
  </div>
</div>
""", unsafe_allow_html=True)
        if st.button("🚀 VIEW ANOMALIES", key="lower_view", use_container_width=True):
            st.session_state.page = "🚨 Anomalies"
            st.rerun()
        st.caption("Connects to Ethereum Mainnet · PostgreSQL (Supabase)")

    with low_r:
        st.markdown("""
<div style="padding-top:10px;">
  <div style="font-size:22px;font-weight:700;color:#4df2d8;margin-bottom:12px;">
    What is Ethereum Anomaly Detection?
  </div>
  <div style="font-size:14px;color:#c9bdeb;line-height:1.8;margin-bottom:18px;">
    Our platform connects live to the Ethereum mainnet and scans every transaction
    in every new block — flagging suspicious activity using threshold analysis and
    pattern matching.
  </div>
  <div style="font-size:18px;font-weight:700;color:#4df2d8;margin-bottom:10px;">Why?</div>
  <div style="font-size:14px;color:#c9bdeb;line-height:1.8;">
    As of 2024, there were over 80,000 DeFi-related exploits costing billions.<br><br>
    The Ethereum ecosystem is vulnerable to flash loan attacks, gas price manipulation,
    and zero-value contract interaction anomalies.
  </div>
</div>
""", unsafe_allow_html=True)

    st.divider()
    # Quick stats strip
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🚨 Total Anomalies", total)
    c2.metric("🔴 High Severity",   high_cnt)
    c3.metric("🟡 Gas / Contract",  med_cnt)
    c4.metric("🟢 Monitor Status",  "Active")


def page_anomalies():
    # ── fetch data ──
    week_records = fetch_week_anomalies(days=7, limit=max_rows)
    lifetime     = fetch_lifetime_stats()
    lifetime_total = lifetime.get("total", 0)

    # Derive stats from lifetime
    by_type  = lifetime.get("by_type",  {})
    by_sev   = lifetime.get("by_severity", {})
    high_cnt = by_sev.get("HIGH", 0)
    med_cnt  = by_sev.get("MEDIUM", 0)

    st.markdown(
        '## 🚨 Recent Anomalous Transactions '
        '<span class="live">LIVE</span>'
        '<span class="week-badge">📅 Last 7 Days</span>'
        + _last_updated_pill(),
        unsafe_allow_html=True,
    )
    st.caption(f"Showing anomalies from the past 7 days. Auto-refresh every {refresh_rate}s.")

    # ── Lifetime badge (compact, always visible) ──
    _lifetime_badge(lifetime)

    # ── Week stats strip ──
    week_high = sum(1 for r in week_records if r.get("severity") == "HIGH")
    week_med  = sum(1 for r in week_records if r.get("severity") == "MEDIUM")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📅 This Week",      len(week_records))
    c2.metric("🔴 High (Week)",    week_high)
    c3.metric("🟡 Medium (Week)",  week_med)
    c4.metric("🟢 Monitor",        "Active")

    st.divider()
    _monitor_staleness_banner(week_records)

    if not week_records:
        st.info("⏳ No anomalies detected in the last 7 days.", icon="ℹ️")
        return

    df = pd.DataFrame(week_records)
    if severity_filter:
        df = df[df["severity"].isin(severity_filter)]
    if df.empty:
        st.warning("No anomalies match the severity filter for this week.")
        return

    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    df["etherscan"]  = "https://etherscan.io/tx/" + df["tx_hash"]
    df["tx_short"]   = df["tx_hash"].str[:12] + "…"

    st.dataframe(
        df[["timestamp","block_number","tx_short","anomaly_type","severity","value_eth","gas_price_gwei","etherscan"]],
        column_config={
            "timestamp":      "Time (UTC)",
            "block_number":   "Block",
            "tx_short":       "Tx Hash",
            "anomaly_type":   "Anomaly Type",
            "severity":       "Severity",
            "value_eth":      st.column_config.NumberColumn("Value (ETH)", format="%.4f"),
            "gas_price_gwei": st.column_config.NumberColumn("Gas (Gwei)",  format="%.2f"),
            "etherscan":      st.column_config.LinkColumn("Etherscan 🔗",  display_text="View"),
        },
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.subheader("🔬 Detailed View (latest 10 this week)")
    for _, row in df.head(10).iterrows():
        with st.expander(f"{row['tx_short']}  |  {row['anomaly_type']}  |  **{row['severity']}**"):
            c1, c2 = st.columns(2)
            c1.markdown(f"**Block:** `{row['block_number']}`")
            c1.markdown(f"**Value:** `{row['value_eth']:.4f} ETH`")
            c1.markdown(f"**Gas:** `{row['gas_price_gwei']:.2f} Gwei`")
            c2.markdown(f"**From:** `{row['from_address']}`")
            c2.markdown(f"**To:** `{row['to_address']}`")
            c2.markdown(f"**Time:** `{row['timestamp']}`")
            st.info(row["description"])
            st.markdown(f"[🔗 View on Etherscan](https://etherscan.io/tx/{row['tx_hash']})")


def page_live_logs():
    st.markdown(
        '## 🖥️ Live Monitor Logs '
        '<span class="live">LIVE</span>'
        + _last_updated_pill(),
        unsafe_allow_html=True,
    )
    st.caption(
        f"Real-time stdout from `monitor.py` — stored in Supabase `monitor_logs` table. "
        f"Showing last {log_lines} lines. Auto-refresh every {refresh_rate}s."
    )

    logs = fetch_monitor_logs(limit=log_lines)
    _render_log_terminal(logs, title="monitor.py — Live Output")

    st.divider()
    # ── Mini stats below logs ──
    if logs:
        errors   = sum(1 for l in logs if l.get("level") in ("ERROR", "CRITICAL"))
        warnings = sum(1 for l in logs if l.get("level") == "WARNING")
        infos    = sum(1 for l in logs if l.get("level") == "INFO")
        last_ts  = pd.to_datetime(logs[-1]["ts"]).strftime("%Y-%m-%d %H:%M:%S UTC") if logs else "—"

        lc1, lc2, lc3, lc4 = st.columns(4)
        lc1.metric("📋 Lines Shown",    len(logs))
        lc2.metric("ℹ️ INFO",           infos)
        lc3.metric("⚠️ Warnings",       warnings, delta=f"-{warnings}" if warnings else None,
                   delta_color="inverse" if warnings else "off")
        lc4.metric("🔴 Errors",         errors,   delta=f"-{errors}" if errors else None,
                   delta_color="inverse" if errors else "off")

        st.caption(f"Last log entry at: **{last_ts}**")
    else:
        st.info(
            "📭 No logs yet. The monitor writes logs here once it starts running on Render. "
            "Make sure `eth-anomaly-monitor` is deployed and the DB is reachable.",
            icon="ℹ️",
        )


def page_stats():
    stats   = fetch_stats()
    by_type = stats.get("anomalies_by_type", {})
    total   = stats.get("total_anomalies", 0)

    st.markdown(
        "## 📊 Anomaly Distribution " + _last_updated_pill(),
        unsafe_allow_html=True,
    )
    st.caption(f"Total anomalies detected: **{total}** · Auto-refresh every {refresh_rate}s.")

    if by_type:
        chart_df = (
            pd.DataFrame(list(by_type.items()), columns=["Type", "Count"])
            .sort_values("Count", ascending=False)
        )
        st.bar_chart(chart_df.set_index("Type"), use_container_width=True)
    else:
        st.info("No anomaly data yet. Start `monitor.py` to begin scanning.")


def page_about():
    st.markdown("## ℹ️ About ETHWatch")
    st.markdown("""
**ETHWatch** is a production-grade Ethereum blockchain monitoring platform that:

- Connects live to the Ethereum mainnet via Web3 RPC
- Downloads each new block and scans **every transaction**
- Flags **High Value Transfers**, **High Gas Price** spikes, and **Suspicious Contract Interactions**
- Persists findings in a PostgreSQL (Supabase) database
- Surfaces results through this real-time Streamlit dashboard
- Streams real-time monitor logs to the **Live Logs** tab via Supabase

Built as an open-source research tool for on-chain security researchers and DeFi protocol teams.
    """)


def page_how():
    st.markdown("## ⚙️ How It Works")
    st.markdown("""
### Pipeline

| Step | Component | Role |
|---|---|---|
| 1 | `monitor.py` | Connects to Ethereum RPC, polls for new blocks every 4 s |
| 2 | `detector.py` | Applies rule-based anomaly checks |
| 3 | `database.py` | Persists flagged transactions + live logs to PostgreSQL |
| 4 | `app.py` | Reads DB and renders this dashboard (auto-refresh) |

### Anomaly Types Detected

| Type | Trigger |
|---|---|
| High Value Transfer | ETH value > `HIGH_VALUE_THRESHOLD` in `.env` |
| High Gas Price | Gas (Gwei) > `HIGH_GAS_PRICE_THRESHOLD` in `.env` |
| Suspicious Contract Interaction | Zero-value tx with very high gas limit |

### Live Logs
The monitor writes its stdout to the `monitor_logs` Supabase table via a background thread.
The **🖥️ Live Logs** tab displays up to 100 of the most recent lines, auto-refreshing every {refresh_rate}s.
    """)


def page_faq():
    st.markdown("## ❓ Frequently Asked Questions")
    with st.expander("Why isn't the monitor finding anomalies?"):
        st.write("The public RPC (`cloudflare-eth.com`) throttles requests. Use a dedicated Alchemy or Infura URL in your `.env` file.")
    with st.expander("How do I change detection thresholds?"):
        st.write("Edit `HIGH_VALUE_THRESHOLD` and `HIGH_GAS_PRICE_THRESHOLD` in `.env` and restart `monitor.py`.")
    with st.expander("Can I deploy this publicly?"):
        st.write("Yes! Upload to GitHub, deploy `app.py` as a Web Service on Render, and run `monitor.py` as a Background Worker.")
    with st.expander("What does the scanning bar mean?"):
        st.write("It's a visual indicator that the dashboard is polling the database. The actual scanning happens in `monitor.py`.")
    with st.expander("Why do I see old data sometimes?"):
        st.write(f"The cache TTL is tied to your refresh slider ({refresh_rate}s). Data updates every {refresh_rate}s automatically.")
    with st.expander("What is the 'Last 7 Days' filter on the Anomalies page?"):
        st.write("The Anomalies table only shows transactions flagged in the past 7 days for clarity. The compact 'Lifetime Total' badge above the table shows all-time counts. Click it to expand the full breakdown.")
    with st.expander("Where are the Live Logs coming from?"):
        st.write("monitor.py sends every log line to the Supabase `monitor_logs` table via a background thread. The Live Logs tab reads from there — no direct process access needed.")
    with st.expander("How do I keep the monitor running 24/7 for free?"):
        st.write("Sign up for UptimeRobot (free) at https://uptimerobot.com and add your Render monitor URL as an HTTP monitor. It will ping every 5 minutes from external servers, keeping Render from sleeping the service.")


# ═══════════════════════════════════════════════════════════════════════
# Router
# ═══════════════════════════════════════════════════════════════════════
PAGE_MAP = {
    "🏠 Home":          page_home,
    "🚨 Anomalies":    page_anomalies,
    "📊 Stats":         page_stats,
    "🖥️ Live Logs":    page_live_logs,
    "ℹ️ About":        page_about,
    "⚙️ How It Works": page_how,
    "❓ FAQ":           page_faq,
}

render_fn = PAGE_MAP.get(current_page, page_home)
render_fn()

# Manual refresh button when Live toggle is off
if not auto_refresh and current_page in LIVE_PAGES:
    st.divider()
    if st.button("🔄 Refresh Now", key="manual_refresh"):
        fetch_stats.clear()
        fetch_recent_anomalies.clear()
        fetch_week_anomalies.clear()
        fetch_lifetime_stats.clear()
        fetch_monitor_logs.clear()
        st.rerun()
