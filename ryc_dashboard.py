"""
RYC 2026 – Planning Committee Dashboard
REVIVE Youth Convention · Moscow · April 30 – May 3, 2026
"""
import os
from dotenv import load_dotenv

load_dotenv() 
import re
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests
from io import StringIO

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RYC 2026 Dashboard",
    page_icon="✝️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Brand CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
:root {
    --blue-dark: #0f3460;
    --blue-mid:  #1a1a2e;
    --red:       #e94560;
    --green:     #06d6a0;
    --gold:      #ffd166;
}
.stApp { background: #f0f2f6; }
.kpi-grid { display:flex; gap:14px; flex-wrap:wrap; margin-bottom:8px; }
.kpi-card {
    flex:1; min-width:130px;
    background:white; border-radius:12px;
    padding:18px 14px; text-align:center;
    box-shadow:0 2px 8px rgba(0,0,0,.08);
    border-top:4px solid var(--blue-dark);
}
.kpi-num  { font-size:2rem; font-weight:800; color:var(--blue-dark); line-height:1.1; }
.kpi-lbl  { font-size:.78rem; color:#666; margin-top:5px; }
.kpi-card.red   { border-top-color:var(--red);   }
.kpi-card.red   .kpi-num { color:var(--red); }
.kpi-card.green { border-top-color:var(--green); }
.kpi-card.green .kpi-num { color:#04a87a; }
.kpi-card.gold  { border-top-color:#e8a800; }
.kpi-card.gold  .kpi-num { color:#c78f00; }
.sec-hdr {
    background: linear-gradient(135deg,#1a1a2e,#0f3460);
    color:white; padding:12px 18px; border-radius:10px;
    margin:26px 0 12px; font-size:1rem; font-weight:700;
    display:flex; align-items:center; gap:8px;
}
.login-wrap { max-width:400px; margin:70px auto; background:white;
    border-radius:16px; padding:40px; box-shadow:0 8px 32px rgba(0,0,0,.13); }
div[data-testid="stButton"] button {
    background:linear-gradient(135deg,#0f3460,#1a1a2e);
    color:white; border:none; border-radius:8px;
    padding:8px 22px; font-weight:600; transition:.2s;
}
div[data-testid="stButton"] button:hover { opacity:.85; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SHEET_ID       = os.getenv("SHEET_ID", "")
REG_FEE        = 8_000.0

BRAND = ["#0f3460","#e94560","#06d6a0","#ffd166","#533483",
         "#118ab2","#ef476f","#2ec4b6","#ff9f1c","#1a1a2e"]

for k, v in [("authenticated", False), ("df", None)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Layout helper (no duplicate-key risk) ────────────────────────────────────
# CHART_BASE must NOT contain 'height' – callers pass it explicitly.
_CHART_BASE = dict(
    margin=dict(t=44, b=10, l=10, r=10),
    plot_bgcolor="white",
    paper_bgcolor="white",
    font=dict(family="sans-serif", size=12),
)

def L(height=330, **kwargs):
    """Return a complete update_layout dict with guaranteed single height."""
    return {**_CHART_BASE, "height": height, **kwargs}


# ══════════════════════════════════════════════════════════════════════════════
# DATA LAYER
# ══════════════════════════════════════════════════════════════════════════════

def fetch_csv(sheet_id):
    hdrs = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    }
    urls = [
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=0",
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv",
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv",
    ]
    last_err = "Unknown"
    for url in urls:
        try:
            r = requests.get(url, headers=hdrs, timeout=25, allow_redirects=True)
            if r.status_code == 200 and len(r.text) > 100:
                return r.text
            last_err = f"HTTP {r.status_code}"
        except Exception as e:
            last_err = str(e)
    raise ConnectionError(
        f"Could not reach Google Sheet (tried {len(urls)} URLs). "
        f"Last error: {last_err}. "
        "Ensure sharing is set to 'Anyone with the link – Viewer'."
    )


def _num(val):
    if pd.isna(val):
        return 0.0
    s = (str(val)
         .replace("pyб", "").replace("руб", "")
         .replace("\u202f", "").replace("\xa0", "")
         .replace(",", "").replace(" ", "").strip())
    m = re.findall(r"[\d.]+", s)
    return float(m[0]) if m else 0.0


def parse_contrib(choice_val, freewill_val):
    """
    Returns extra donation (above the base ₽8 000 reg fee).
      'No please - 0.00'          → 0
      'Yes - 500.00'              → 500
      'Yes - 1 000.00'            → 1000   (space-thousand-sep handled by _num)
      'Yes, other amount - 0.00'  → freewill_val column
    """
    if pd.isna(choice_val):
        return 0.0
    s = str(choice_val).strip()
    lo = s.lower()
    if lo.startswith("no"):
        return 0.0
    if "other amount" in lo:
        return _num(freewill_val)
    parts = s.rsplit("-", 1)
    if len(parts) == 2:
        return _num(parts[1])
    return 0.0


COL_HINTS = {
    "FirstName":        ["first name", "first"],
    "LastName":         ["last name", "last"],
    "Gender":           ["gender"],
    "Phone":            ["phone"],
    "Email":            ["email"],
    "City":             ["which city are you from", "city"],
    "RCCGMember":       ["rccg russia member", "rccg member"],
    "ChurchName":       ["church name"],
    "NeedsAccom":       ["accommodation"],
    "Expectations":     ["expectation", "testimon"],
    "ContribChoice":    ["contribute financially"],
    "FreewillDonation": ["freewill donation"],
    "Total":            ["total"],
}


def detect_col(name_lower):
    for canon, hints in COL_HINTS.items():
        for h in hints:
            if h in name_lower:
                return canon
    return None


@st.cache_data(ttl=300, show_spinner=False)
def load_data(sheet_id):
    csv = fetch_csv(sheet_id)
    raw = pd.read_csv(StringIO(csv))

    rename = {}
    for c in raw.columns:
        canon = detect_col(c.strip().lower())
        if canon and canon not in rename.values():
            rename[c] = canon
    df = raw.rename(columns=rename)

    # Freewill numeric
    df["FreewillAmt"] = (
        df["FreewillDonation"].apply(_num)
        if "FreewillDonation" in df.columns
        else 0.0
    )

    # Extra donation
    if "ContribChoice" in df.columns:
        df["ExtraDonation"] = df.apply(
            lambda r: parse_contrib(r["ContribChoice"], r.get("FreewillAmt", 0)),
            axis=1,
        )
        df["WillContribute"] = (
            df["ContribChoice"].str.strip().str.lower().str.startswith("yes")
        )

        def contrib_label(v):
            if pd.isna(v):
                return "No contribution"
            s = str(v).strip()
            if s.lower().startswith("no"):
                return "No contribution"
            if "other amount" in s.lower():
                return "Yes – Custom amount"
            parts = s.rsplit("-", 1)
            if len(parts) == 2:
                amt = _num(parts[1])
                if amt:
                    return f"Yes – ₽{amt:,.0f}"
            return "Yes"

        df["ContribLabel"] = df["ContribChoice"].apply(contrib_label)
    else:
        df["ExtraDonation"] = 0.0
        df["WillContribute"] = False
        df["ContribLabel"] = "No contribution"

    df["PersonTotal"] = REG_FEE + df["ExtraDonation"]

    # RCCG flag
    if "RCCGMember" in df.columns:
        df["RCCGFlag"] = (
            df["RCCGMember"].astype(str).str.strip().str.lower() == "yes"
        )
    else:
        df["RCCGFlag"] = False

    # Church display name
    def church_display(row):
        name = str(row.get("ChurchName", "")).strip()
        has_name = name and name.lower() not in ("nan", "")
        if row.get("RCCGFlag", False):
            return name if has_name else "RCCG (Parish unspecified)"
        return name if has_name else "Non-RCCG (unlisted)"

    df["ChurchDisplay"] = df.apply(church_display, axis=1)
    df["MemberType"] = df["RCCGFlag"].map(
        {True: "RCCG Parish Member", False: "Non-RCCG Attendee"}
    )

    # Accommodation
    df["AccomFlag"] = (
        df["NeedsAccom"].astype(str).str.strip().str.lower() == "yes"
        if "NeedsAccom" in df.columns
        else False
    )

    # Full name
    fn = df.get("FirstName", pd.Series([""] * len(df))).fillna("")
    ln = df.get("LastName",  pd.Series([""] * len(df))).fillna("")
    df["FullName"] = (fn + " " + ln).str.strip()

    if "Gender" in df.columns:
        df["Gender"] = df["Gender"].astype(str).str.strip().str.title()

    return df


# ══════════════════════════════════════════════════════════════════════════════
# UI HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def sec(icon, title):
    st.markdown(
        f"<div class='sec-hdr'>{icon} {title}</div>",
        unsafe_allow_html=True,
    )


def kpi_row(items):
    cards = ""
    for label, value, colour in items:
        cards += (
            f"<div class='kpi-card {colour}'>"
            f"<div class='kpi-num'>{value}</div>"
            f"<div class='kpi-lbl'>{label}</div>"
            f"</div>"
        )
    st.markdown(f"<div class='kpi-grid'>{cards}</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════════════════════

def show_login():
    st.markdown("""
    <div class='login-wrap'>
        <div style='text-align:center'>
            <div style='font-size:2.8rem'>✝️</div>
            <h2 style='color:#0f3460;margin:6px 0 2px'>RYC 2026</h2>
            <p style='color:#888;font-size:.88rem'>
                Revive Youth Convention<br>Moscow · Apr 30 – May 3, 2026
            </p>
            <hr style='margin:18px 0'>
            <p style='color:#555;font-weight:600;margin-bottom:4px'>
                Planning Committee · Admin Login
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        pwd = st.text_input("Password", type="password",
                            placeholder="Enter admin password")
        if st.button("🔐  Sign In", use_container_width=True):
            if pwd == ADMIN_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password. Please try again.")


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

def show_dashboard(df):

    st.markdown("""
    <div style='background:linear-gradient(135deg,#1a1a2e 0%,#0f3460 60%,#533483 100%);
                color:white;padding:22px 28px;border-radius:14px;margin-bottom:18px'>
        <h1 style='margin:0;font-size:1.7rem;letter-spacing:.4px'>
            ✝️ REVIVE Youth Convention 2026
        </h1>
        <p style='margin:4px 0 0;opacity:.75;font-size:.9rem'>
            RCCG Russia · Moscow · April 30 – May 3, 2026
            &nbsp;|&nbsp; Planning Committee Dashboard
        </p>
    </div>
    """, unsafe_allow_html=True)

    cr, _, cl = st.columns([2, 6, 1])
    with cr:
        if st.button("🔄  Refresh Data"):
            load_data.clear()
            st.session_state.df = None
            st.rerun()
    with cl:
        if st.button("🚪 Logout"):
            st.session_state.authenticated = False
            st.session_state.df = None
            st.rerun()

    # ── Scalars ───────────────────────────────────────────────────────────────
    total       = len(df)
    females     = int((df["Gender"] == "Female").sum()) if "Gender" in df.columns else 0
    males       = int((df["Gender"] == "Male").sum())   if "Gender" in df.columns else 0
    rccg_n      = int(df["RCCGFlag"].sum())
    non_rccg_n  = total - rccg_n
    accom_n     = int(df["AccomFlag"].sum())
    contrib_n   = int(df["WillContribute"].sum())
    total_rev   = df["PersonTotal"].sum()
    total_extra = df["ExtraDonation"].sum()
    avg_extra   = df[df["ExtraDonation"] > 0]["ExtraDonation"].mean() if contrib_n else 0

    kpi_row([
        ("Total Registrations",   total,               ""),
        ("👩 Female",            females,              "red"),
        ("👨 Male",              males,                ""),
        ("RCCG Parish Members",  rccg_n,               ""),
        ("Non-RCCG Attendees",   non_rccg_n,           "gold"),
    ])
    kpi_row([
        ("Need Accommodation",   accom_n,              "red"),
        ("Financial Contributors", contrib_n,          "green"),
        ("Total Revenue (₽)",   f"₽{total_rev:,.0f}",  ""),
        ("Extra Donations (₽)", f"₽{total_extra:,.0f}", "green"),
        ("Avg Extra / Donor",   f"₽{avg_extra:,.0f}",  "gold"),
    ])
    st.markdown("<br>", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # 1. DEMOGRAPHICS
    # ══════════════════════════════════════════════════════════════════════════
    sec("👥", "Demographics")
    c1, c2, c3 = st.columns(3)

    with c1:
        if "Gender" in df.columns:
            g = df["Gender"].value_counts().reset_index()
            g.columns = ["Gender", "Count"]
            fig = px.pie(g, names="Gender", values="Count", hole=.46,
                         color_discrete_sequence=BRAND, title="Gender Distribution")
            fig.update_traces(textinfo="percent+label", pull=[.03] * len(g))
            fig.update_layout(**L())
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        mem = pd.DataFrame({
            "Type":  ["RCCG Parish Member", "Non-RCCG Attendee"],
            "Count": [rccg_n, non_rccg_n],
        })
        fig = px.pie(mem, names="Type", values="Count", hole=.46,
                     color_discrete_sequence=["#0f3460", "#e94560"],
                     title="RCCG Membership Status")
        fig.update_traces(textinfo="percent+label", pull=[.03, .03])
        fig.update_layout(**L())
        st.plotly_chart(fig, use_container_width=True)

    with c3:
        accom_d = pd.DataFrame({
            "Status": ["Needs Accommodation", "Self-arranged"],
            "Count":  [accom_n, total - accom_n],
        })
        fig = px.bar(accom_d, x="Status", y="Count", text="Count",
                     color="Status",
                     color_discrete_sequence=["#0f3460", "#e94560"],
                     title="Accommodation Needs")
        fig.update_traces(textposition="outside")
        fig.update_layout(**L(showlegend=False, xaxis_title="", yaxis_title="Registrants"))
        st.plotly_chart(fig, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════
    # 2. GEOGRAPHY
    # ══════════════════════════════════════════════════════════════════════════
    sec("🌍", "Geographic Distribution")
    c1, c2 = st.columns(2)

    with c1:
        if "City" in df.columns:
            city_c = df["City"].value_counts().reset_index()
            city_c.columns = ["City", "Count"]
            fig = px.bar(city_c, x="City", y="Count", text="Count",
                         color="Count", color_continuous_scale="Blues",
                         title="Registrants by City of Residence")
            fig.update_traces(textposition="outside")
            fig.update_layout(**L(coloraxis_showscale=False, xaxis_title="", yaxis_title="Count"))
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        if "City" in df.columns and "Gender" in df.columns:
            gc = df.groupby(["City", "Gender"]).size().reset_index(name="Count")
            fig = px.bar(gc, x="City", y="Count", color="Gender",
                         barmode="stack", text="Count",
                         color_discrete_sequence=["#e94560", "#0f3460", "#06d6a0"],
                         title="Gender Split by City")
            fig.update_layout(**L(xaxis_title="", yaxis_title="Count"))
            st.plotly_chart(fig, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════
    # 3. CHURCH & PARISH
    # ══════════════════════════════════════════════════════════════════════════
    sec("⛪", "Church & Parish Breakdown")

    rccg_df     = df[df["RCCGFlag"] == True]
    non_rccg_df = df[df["RCCGFlag"] == False]

    c1, c2 = st.columns(2)
    with c1:
        if not rccg_df.empty:
            rc = rccg_df["ChurchDisplay"].value_counts().reset_index()
            rc.columns = ["Church", "Count"]
            h = max(300, 40 * len(rc) + 70)
            fig = px.bar(rc, x="Count", y="Church", orientation="h", text="Count",
                         color="Count", color_continuous_scale="Blues",
                         title=f"RCCG Parishes ({rccg_n} members)")
            fig.update_traces(textposition="outside")
            fig.update_layout(**L(h, coloraxis_showscale=False,
                                  yaxis=dict(autorange="reversed"),
                                  xaxis_title="", yaxis_title=""))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No RCCG parish members registered yet.")

    with c2:
        if not non_rccg_df.empty:
            nc = non_rccg_df["ChurchDisplay"].value_counts().reset_index()
            nc.columns = ["Church", "Count"]
            h = max(300, 40 * len(nc) + 70)
            fig = px.bar(nc, x="Count", y="Church", orientation="h", text="Count",
                         color="Count", color_continuous_scale="Reds",
                         title=f"Non-RCCG Churches ({non_rccg_n} attendees)")
            fig.update_traces(textposition="outside")
            fig.update_layout(**L(h, coloraxis_showscale=False,
                                  yaxis=dict(autorange="reversed"),
                                  xaxis_title="", yaxis_title=""))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No non-RCCG attendees yet.")

    # All combined
    all_church = df["ChurchDisplay"].value_counts().reset_index()
    all_church.columns = ["Church", "Count"]
    h_all = max(300, 42 * len(all_church) + 70)
    c1, c2 = st.columns([3, 2])
    with c1:
        fig = px.bar(all_church, x="Count", y="Church", orientation="h",
                     text="Count", color="Church",
                     color_discrete_sequence=BRAND,
                     title="All Churches – Combined Count")
        fig.update_traces(textposition="outside")
        fig.update_layout(**L(h_all, showlegend=False,
                              yaxis=dict(autorange="reversed"),
                              xaxis_title="", yaxis_title=""))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = px.pie(all_church, names="Church", values="Count", hole=.4,
                     color_discrete_sequence=BRAND, title="Church Share (%)")
        fig.update_traces(textinfo="percent+label")
        fig.update_layout(**L(h_all))
        st.plotly_chart(fig, use_container_width=True)

    # Gender × Church
    if "Gender" in df.columns:
        sec("🔀", "Gender × Church Cross-Analysis")
        gc2 = df.groupby(["ChurchDisplay", "Gender"]).size().reset_index(name="Count")
        fig = px.bar(gc2, x="ChurchDisplay", y="Count", color="Gender",
                     barmode="group", text="Count",
                     color_discrete_sequence=["#e94560", "#0f3460", "#06d6a0"],
                     title="Gender Breakdown per Church / Parish")
        fig.update_traces(textposition="outside")
        fig.update_layout(**L(380, xaxis_title="", yaxis_title="Count",
                              xaxis_tickangle=-25))
        st.plotly_chart(fig, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════
    # 4. FINANCIAL OVERVIEW
    # ══════════════════════════════════════════════════════════════════════════
    sec("💰", "Financial Overview")
    c1, c2, c3 = st.columns(3)

    with c1:
        cl = df["ContribLabel"].value_counts().reset_index()
        cl.columns = ["Choice", "Count"]
        fig = px.pie(cl, names="Choice", values="Count", hole=.45,
                     color_discrete_sequence=BRAND,
                     title="Contribution Choice Distribution")
        fig.update_traces(textinfo="percent+label")
        fig.update_layout(**L())
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        fig = go.Figure()
        fig.add_bar(name="Reg Fees (₽8k × registrants)",
                    x=["Total Revenue"],
                    y=[REG_FEE * total],
                    marker_color="#0f3460",
                    text=[f"₽{REG_FEE * total:,.0f}"],
                    textposition="inside")
        fig.add_bar(name="Extra Donations",
                    x=["Total Revenue"],
                    y=[total_extra],
                    marker_color="#06d6a0",
                    text=[f"₽{total_extra:,.0f}"],
                    textposition="inside")
        fig.update_layout(**L(barmode="stack",
                              title="Revenue Breakdown (₽)",
                              yaxis_title="Roubles (₽)", xaxis_title=""))
        st.plotly_chart(fig, use_container_width=True)

    with c3:
        tiers = (df[df["ExtraDonation"] > 0]["ExtraDonation"]
                 .value_counts().sort_index().reset_index())
        tiers.columns = ["Amount", "Count"]
        tiers["Label"] = tiers["Amount"].apply(lambda x: f"₽{x:,.0f}")
        fig = px.bar(tiers, x="Label", y="Count", text="Count",
                     color="Count", color_continuous_scale="Greens",
                     title="Extra Donation Tier Distribution")
        fig.update_traces(textposition="outside")
        fig.update_layout(**L(coloraxis_showscale=False,
                              xaxis_title="Tier", yaxis_title="# People"))
        st.plotly_chart(fig, use_container_width=True)

    # Revenue by church
    c1, c2 = st.columns(2)
    with c1:
        ch_rev = df.groupby("ChurchDisplay")["PersonTotal"].sum().reset_index()
        ch_rev.columns = ["Church", "Revenue"]
        ch_rev = ch_rev.sort_values("Revenue", ascending=False)
        h = max(300, 40 * len(ch_rev) + 70)
        fig = px.bar(ch_rev, x="Revenue", y="Church", orientation="h",
                     text="Revenue", color="Revenue",
                     color_continuous_scale="Blues",
                     title="Total Revenue by Church (₽)")
        fig.update_traces(texttemplate="₽%{text:,.0f}", textposition="outside")
        fig.update_layout(**L(h, coloraxis_showscale=False,
                              yaxis=dict(autorange="reversed"),
                              xaxis_title="", yaxis_title=""))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        ch_extra = (df[df["ExtraDonation"] > 0]
                    .groupby("ChurchDisplay")["ExtraDonation"].sum()
                    .reset_index())
        ch_extra.columns = ["Church", "Extra"]
        if not ch_extra.empty:
            h = max(300, 40 * len(ch_extra) + 70)
            fig = px.pie(ch_extra, names="Church", values="Extra", hole=.4,
                         color_discrete_sequence=BRAND,
                         title="Extra Donations Share by Church (₽)")
            fig.update_traces(textinfo="percent+label")
            fig.update_layout(**L(h))
            st.plotly_chart(fig, use_container_width=True)

    # Top individual donors
    if contrib_n > 0:
        sec("🏆", "Individual Financial Contributions")
        top = (df[df["ExtraDonation"] > 0]
               [["FullName", "ChurchDisplay", "ExtraDonation", "PersonTotal"]]
               .sort_values("ExtraDonation", ascending=False))
        fig = px.bar(top, x="FullName", y="ExtraDonation",
                     color="ChurchDisplay",
                     color_discrete_sequence=BRAND,
                     text="ExtraDonation",
                     title="Extra Donation per Person (above ₽8,000 reg fee)")
        fig.update_traces(texttemplate="₽%{text:,.0f}", textposition="outside")
        fig.update_layout(**L(360, xaxis_title="", yaxis_title="Extra (₽)",
                              xaxis_tickangle=-25))
        st.plotly_chart(fig, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════
    # 5. ACCOMMODATION
    # ══════════════════════════════════════════════════════════════════════════
    sec("🏠", "Accommodation Analysis")
    c1, c2 = st.columns(2)

    with c1:
        if "City" in df.columns:
            ac = df.groupby(["City", "AccomFlag"]).size().reset_index(name="Count")
            ac["Accommodation"] = ac["AccomFlag"].map(
                {True: "Needs Accommodation", False: "Self-arranged"})
            fig = px.bar(ac, x="City", y="Count", color="Accommodation",
                         barmode="stack", text="Count",
                         color_discrete_sequence=["#0f3460", "#e94560"],
                         title="Accommodation Needs by City")
            fig.update_layout(**L(xaxis_title="", yaxis_title="Count"))
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        ac2 = df.groupby(["ChurchDisplay", "AccomFlag"]).size().reset_index(name="Count")
        ac2["Accommodation"] = ac2["AccomFlag"].map(
            {True: "Needs Accommodation", False: "Self-arranged"})
        h = max(300, 40 * df["ChurchDisplay"].nunique() + 70)
        fig = px.bar(ac2, x="Count", y="ChurchDisplay", orientation="h",
                     color="Accommodation", barmode="stack", text="Count",
                     color_discrete_sequence=["#0f3460", "#e94560"],
                     title="Accommodation Needs by Church")
        fig.update_layout(**L(h, yaxis=dict(autorange="reversed"),
                              xaxis_title="Count", yaxis_title=""))
        st.plotly_chart(fig, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════
    # 6. FULL TABLE
    # ══════════════════════════════════════════════════════════════════════════
    sec("📋", "Full Registration Table")

    col_map = {
        "FullName":      "Name",
        "Gender":        "Gender",
        "City":          "City",
        "RCCGMember":    "RCCG Member?",
        "ChurchDisplay": "Church / Parish",
        "NeedsAccom":    "Accommodation?",
        "ContribLabel":  "Contribution Choice",
        "ExtraDonation": "Extra Donation (₽)",
        "PersonTotal":   "Total (₽)",
    }
    disp = df[[c for c in col_map if c in df.columns]].rename(columns=col_map).copy()
    for col in ["Extra Donation (₽)", "Total (₽)"]:
        if col in disp.columns:
            disp[col] = disp[col].apply(lambda x: f"₽{x:,.0f}")

    st.dataframe(disp, use_container_width=True, height=440)

    with st.expander("📊 Summary Statistics"):
        s1, s2, s3 = st.columns(3)
        s1.metric("Total Registrations", total)
        s1.metric("Female", females)
        s1.metric("Male", males)
        s2.metric("RCCG Members", rccg_n)
        s2.metric("Non-RCCG", non_rccg_n)
        s2.metric("Need Accommodation", accom_n)
        s3.metric("Total Revenue", f"₽{total_rev:,.0f}")
        s3.metric("Reg Fees", f"₽{REG_FEE * total:,.0f}")
        s3.metric("Extra Donations", f"₽{total_extra:,.0f}")

    st.markdown("""
    <div style='text-align:center;color:#bbb;font-size:.76rem;margin-top:28px'>
        RYC 2026 Planning Dashboard · Auto-refresh every 5 min ·
        Click 🔄 for instant update · RCCG Russia
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    if not st.session_state.authenticated:
        show_login()
        return

    if st.session_state.df is None:
        with st.spinner("⏳ Loading registration data…"):
            try:
                st.session_state.df = load_data(SHEET_ID)
            except Exception as e:
                st.error(f"❌ Could not load Google Sheet:\n\n{e}")
                st.warning(
                    "**Checklist:**\n"
                    "1. Open the sheet → **Share** → change to "
                    "**'Anyone with the link – Viewer'**\n"
                    "2. Make sure it is NOT restricted to your organisation\n"
                    "3. Test this URL in an incognito window:\n\n"
                    f"   https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
                )
                if st.button("🚪 Logout"):
                    st.session_state.authenticated = False
                    st.rerun()
                return

    show_dashboard(st.session_state.df)


if __name__ == "__main__":
    main()