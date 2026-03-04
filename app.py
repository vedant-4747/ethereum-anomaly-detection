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

# ─── CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

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
</style>
""", unsafe_allow_html=True)

# ─── Session state init ───────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "🏠 Home"

# ─── Nav definition ───────────────────────────────────────────────────
NAV_LABELS = ["🏠 Home", "🚨 Anomalies", "📊 Stats", "ℹ️ About", "⚙️ How It Works", "❓ FAQ"]

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
    st.divider()
    st.markdown("**Data source:** `PostgreSQL (Supabase)`")
    st.markdown("[Etherscan](https://etherscan.io)")

# ─── Non-blocking auto-refresh ────────────────────────────────────────
# st_autorefresh fires a rerun every `refresh_rate * 1000` ms without
# blocking the UI thread. Returns the incremental refresh counter.
current_page = st.session_state.get("page", "🏠 Home")
LIVE_PAGES   = {"🏠 Home", "🚨 Anomalies", "📊 Stats"}

if auto_refresh and current_page in LIVE_PAGES:
    st_autorefresh(interval=refresh_rate * 1000, key="live_refresh")

# ─── Cached data fetchers (TTL tied to refresh interval) ──────────────
# These are defined as functions and called INSIDE each page function
# so Streamlit re-evaluates the cache on every rerun cycle.

@st.cache_data(ttl=refresh_rate)
def fetch_stats():
    return database.get_stats()

@st.cache_data(ttl=refresh_rate)
def fetch_recent_anomalies(limit: int):
    return database.get_recent_anomalies(limit=limit)

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

# ═══════════════════════════════════════════════════════════════════════
# PAGE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def page_home():
    # ── fetch data fresh on every render ──
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
            if st.button("📋 VIEW LOGS", key="hero_logs", use_container_width=True):
                st.session_state.page = "🚨 Anomalies"
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
    # ── fetch data fresh on every render ──
    stats    = fetch_stats()
    total    = stats.get("total_anomalies", 0)
    by_type  = stats.get("anomalies_by_type", {})
    high_cnt = by_type.get("High Value Transfer", 0)
    med_cnt  = sum(v for k, v in by_type.items() if "Gas" in k or "Contract" in k)

    st.markdown(
        '## 🚨 Recent Anomalous Transactions '
        '<span class="live">LIVE</span>' + _last_updated_pill(),
        unsafe_allow_html=True,
    )
    st.caption(f"Real-time feed from the Ethereum mainnet monitor. Auto-refresh every {refresh_rate}s.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🚨 Total Anomalies", total)
    c2.metric("🔴 High Severity",   high_cnt)
    c3.metric("🟡 Gas / Contract",  med_cnt)
    c4.metric("🟢 Monitor",         "Active")

    st.divider()
    records = fetch_recent_anomalies(limit=max_rows)
    _monitor_staleness_banner(records)

    if not records:
        st.info("⏳ No anomalies detected yet — waiting for the monitor to find suspicious transactions.", icon="ℹ️")
        return

    df = pd.DataFrame(records)
    if severity_filter:
        df = df[df["severity"].isin(severity_filter)]
    if df.empty:
        st.warning("No anomalies match the severity filter.")
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
    st.subheader("🔬 Detailed View (latest 10)")
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


def page_stats():
    # ── fetch data fresh on every render ──
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
| 3 | `database.py` | Persists flagged transactions to PostgreSQL |
| 4 | `app.py` | Reads DB and renders this dashboard (auto-refresh) |

### Anomaly Types Detected

| Type | Trigger |
|---|---|
| High Value Transfer | ETH value > `HIGH_VALUE_THRESHOLD` in `.env` |
| High Gas Price | Gas (Gwei) > `HIGH_GAS_PRICE_THRESHOLD` in `.env` |
| Suspicious Contract Interaction | Zero-value tx with very high gas limit |
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


# ═══════════════════════════════════════════════════════════════════════
# Router
# ═══════════════════════════════════════════════════════════════════════
PAGE_MAP = {
    "🏠 Home":          page_home,
    "🚨 Anomalies":    page_anomalies,
    "📊 Stats":         page_stats,
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
        st.rerun()
