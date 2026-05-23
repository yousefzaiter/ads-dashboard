import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime, timedelta
import logging

_CLIENTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clients.json")

_SNAP_SAR = float(os.getenv("USD_TO_SAR", "3.75"))   # Snap returns monetary values in USD; multiply to display in SAR


def _snap_to_sar(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    for col in ("Cost", "Conv. Value"):
        if col in df.columns:
            df[col] = df[col] * _SNAP_SAR
    return df


_PLATFORM_COLORS = {
    "google":  "#58a6ff",
    "meta":    "#4267B2",
    "snap":    "#FFFC00",
    "tiktok":  "#FF0050",
}

_PLATFORM_LABELS = {
    "google":  "Google Ads",
    "meta":    "Meta Ads",
    "snap":    "Snap Ads",
    "tiktok":  "TikTok Ads",
}

# Platform filter button labels (emoji dot + short name)
_PLAT_BTN_LABELS = {
    "google":  "🔵 Google",
    "meta":    "🟣 Meta",
    "snap":    "🟡 Snap",
    "tiktok":  "⚫ TikTok",
}

# ── Project detail nav ────────────────────────────────────────────────────────
_NAV_LABELS = [
    "📊 نظرة عامة",
    "📅 السجل اليومي",
    "📢 أداء الإعلانات",
    "🎨 تحليل الإعلانات",
    "🔔 تنبيهات",
]
_NAV_KEYS = {
    "📊 نظرة عامة":      "overview",
    "📅 السجل اليومي":   "daily",
    "📢 أداء الإعلانات": "ads",
    "🎨 تحليل الإعلانات": "creative",
    "🔔 تنبيهات":         "alerts",
}



# ── persistence ───────────────────────────────────────────────────────────────

def load_projects() -> list[dict]:
    try:
        with open(_CLIENTS_FILE) as f:
            data = json.load(f)
        return data.get("projects", [])
    except Exception:
        return []


def save_projects(projects: list[dict]) -> None:
    try:
        with open(_CLIENTS_FILE) as f:
            data = json.load(f)
    except Exception:
        data = {}
    data["projects"] = projects
    with open(_CLIENTS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── format helpers ────────────────────────────────────────────────────────────

def _fmt_sar(v: float) -> str:
    if v == 0:
        return "—"
    if v >= 1_000_000:
        return f"SAR {v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"SAR {v/1_000:.2f}K"
    return f"SAR {v:,.2f}"


def _fmt_num(v: float) -> str:
    if v == 0:
        return "—"
    if v >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v/1_000:.1f}K"
    return f"{v:,.0f}"


def _fmt_pct(v: float) -> str:
    if v == 0:
        return "—"
    return f"{v:.2f}%"


def _fmt_x(v: float) -> str:
    if v == 0:
        return "—"
    return f"{v:.2f}×"


def _platform_dots(platforms: dict) -> str:
    dots = []
    for key, color in _PLATFORM_COLORS.items():
        acct = (platforms or {}).get(key, {})
        ids  = list(acct.values()) if isinstance(acct, dict) else []
        active = any(str(v).strip() for v in ids)
        opacity = "1" if active else "0.18"
        dots.append(
            f"<span style='display:inline-block;width:9px;height:9px;"
            f"border-radius:50%;background:{color};opacity:{opacity};"
            f"margin-right:4px'></span>"
        )
    return "".join(dots)


def _delta_badge(curr: float, prev: float, higher_is_better: bool = True) -> str:
    """Inline ▲/▼ % badge HTML."""
    if not prev or not curr:
        return ""
    pct = (curr - prev) / abs(prev) * 100
    if abs(pct) < 0.05:
        return "<span style='font-size:11px;color:rgba(255,255,255,0.3)'>±0%</span>"
    up      = pct > 0
    is_good = up if higher_is_better else not up
    color   = "#3fb950" if is_good else "#f85149"
    arrow   = "▲" if up else "▼"
    return f"<span style='font-size:11px;font-weight:500;color:{color}'>{arrow}&thinsp;{abs(pct):.1f}%</span>"


def _roas_ind_color(roas: float, target_mer: float) -> str:
    if target_mer <= 0:
        return "rgba(255,255,255,0.2)"
    if roas >= target_mer:
        return "#3fb950"
    if roas >= target_mer * 0.8:
        return "#e3b341"
    return "#f85149"


def _roas_color(roas: float, target_mer: float) -> str:
    if target_mer <= 0:
        return "#f0f6fc"
    if roas >= target_mer:
        return "#3fb950"
    if roas >= target_mer * 0.8:
        return "#e3b341"
    return "#f85149"


# ── KPI card helper ───────────────────────────────────────────────────────────

_KS  = ("background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.06);"
        "border-radius:10px;padding:14px 16px;min-height:80px")
_LBL = "font-size:10px;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:1px"
_VAL = "font-size:20px;font-weight:800;margin-top:4px;line-height:1.2"
_SUB = "font-size:10px;color:rgba(255,255,255,0.3);margin-top:2px"


def _kpi_card(col, label: str, value: str, badge: str = "",
              color: str = "#f0f6fc", sub: str = "") -> None:
    sub_html  = f"<div style='{_SUB}'>{sub}</div>" if sub else ""
    badge_html = f"<div style='margin-top:5px'>{badge}</div>" if badge else ""
    col.markdown(
        f"<div style='{_KS}'>"
        f"<div style='{_LBL}'>{label}</div>"
        f"<div style='{_VAL};color:{color}'>{value}</div>"
        f"{badge_html}{sub_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


# ── new-project dialog ────────────────────────────────────────────────────────

@st.dialog("New Project", width="large")
def _new_project_dialog():
    st.markdown("#### Create a new project")
    name = st.text_input("Project name *", placeholder="e.g. My Brand")
    col1, col2 = st.columns(2)
    with col1:
        target_cpa = st.number_input("Target CPA (SAR)", min_value=0.0, value=0.0, step=1.0)
    with col2:
        target_mer = st.number_input("Target MER (×)", min_value=0.0, value=0.0, step=0.1)

    st.markdown("##### Platform accounts")
    g_col, m_col = st.columns(2)
    with g_col:
        google_cid = st.text_input("Google Ads Customer ID", placeholder="1234567890")
    with m_col:
        meta_aid = st.text_input("Meta Ad Account ID", placeholder="act_579554746963968")
    s_col, t_col = st.columns(2)
    with s_col:
        snap_aid = st.text_input("Snap Ad Account ID", placeholder="xxxxxxxx-xxxx-...")
    with t_col:
        tiktok_aid = st.text_input("TikTok Advertiser ID", placeholder="7xxxxxxxxxxxxxx")

    if st.button("Create project", type="primary", use_container_width=True):
        if not name.strip():
            st.error("Project name is required.")
            return
        projects = load_projects()
        new_proj = {
            "id": str(uuid.uuid4()),
            "name": name.strip(),
            "target_cpa": target_cpa,
            "target_mer": target_mer,
            "created_at": datetime.utcnow().isoformat(),
            "platforms": {
                "google":  {"customer_id": google_cid.strip()},
                "meta":    {"ad_account_id": meta_aid.strip()},
                "snap":    {"ad_account_id": snap_aid.strip()},
                "tiktok":  {"advertiser_id": tiktok_aid.strip()},
            },
        }
        projects.append(new_proj)
        save_projects(projects)
        st.success(f"Project **{new_proj['name']}** created!")
        st.rerun()


# ── edit-project dialog ───────────────────────────────────────────────────────

@st.dialog("Edit Project", width="large")
def _edit_project_dialog(proj: dict):
    projects = load_projects()
    idx = next((i for i, p in enumerate(projects) if p["id"] == proj["id"]), None)

    name = st.text_input("Project name *", value=proj.get("name", ""))
    col1, col2 = st.columns(2)
    with col1:
        target_cpa = st.number_input("Target CPA (SAR)", min_value=0.0,
                                     value=float(proj.get("target_cpa", 0)), step=1.0)
    with col2:
        target_mer = st.number_input("Target MER (×)", min_value=0.0,
                                     value=float(proj.get("target_mer", 0)), step=0.1)

    plat = proj.get("platforms", {})
    st.markdown("##### Platform accounts")
    g_col, m_col = st.columns(2)
    with g_col:
        google_cid = st.text_input("Google Ads Customer ID",
                                   value=plat.get("google", {}).get("customer_id", ""))
    with m_col:
        meta_aid = st.text_input("Meta Ad Account ID",
                                  value=plat.get("meta", {}).get("ad_account_id", ""))
    s_col, t_col = st.columns(2)
    with s_col:
        snap_aid = st.text_input("Snap Ad Account ID",
                                  value=plat.get("snap", {}).get("ad_account_id", ""))
    with t_col:
        tiktok_aid = st.text_input("TikTok Advertiser ID",
                                   value=plat.get("tiktok", {}).get("advertiser_id", ""))

    col_save, col_del = st.columns([3, 1])
    with col_save:
        if st.button("Save changes", type="primary", use_container_width=True):
            if not name.strip():
                st.error("Project name is required.")
                return
            if idx is not None:
                projects[idx].update({
                    "name": name.strip(),
                    "target_cpa": target_cpa,
                    "target_mer": target_mer,
                    "platforms": {
                        "google":  {"customer_id": google_cid.strip()},
                        "meta":    {"ad_account_id": meta_aid.strip()},
                        "snap":    {"ad_account_id": snap_aid.strip()},
                        "tiktok":  {"advertiser_id": tiktok_aid.strip()},
                    },
                })
                save_projects(projects)
            st.rerun()
    with col_del:
        if st.button("Delete", type="secondary", use_container_width=True):
            if idx is not None:
                projects.pop(idx)
                save_projects(projects)
                st.session_state.pop("selected_project_id", None)
            st.rerun()


# ── data fetchers ─────────────────────────────────────────────────────────────

def _fetch_platform_df(platform: str, proj: dict, start: str, end: str,
                       fetch_google=None) -> tuple[pd.DataFrame, str | None]:
    plat = proj.get("platforms", {}).get(platform, {})

    if platform == "google":
        cid = plat.get("customer_id", "").strip()
        if not cid or fetch_google is None:
            return pd.DataFrame(), None
        try:
            return fetch_google(cid, start, end), None
        except Exception as e:
            return pd.DataFrame(), str(e)[:80]

    if platform == "meta":
        acct = plat.get("ad_account_id", "").strip()
        if not acct:
            return pd.DataFrame(), None
        try:
            from meta_ads_server import fetch_meta_campaigns
            token = os.getenv("META_ACCESS_TOKEN", "")
            if not token:
                return pd.DataFrame(), "No META_ACCESS_TOKEN in .env"
            return fetch_meta_campaigns(token, acct, start, end), None
        except Exception as e:
            return pd.DataFrame(), str(e)[:120]

    if platform == "snap":
        acct = plat.get("ad_account_id", "").strip()
        if not acct:
            return pd.DataFrame(), None
        try:
            from snap_ads_server import fetch_snap_campaigns
            token = os.getenv("SNAP_ACCESS_TOKEN", "")
            if not token:
                return pd.DataFrame(), "No SNAP_ACCESS_TOKEN"
            return _snap_to_sar(fetch_snap_campaigns(token, acct, start, end)), None
        except Exception as e:
            return pd.DataFrame(), str(e)[:80]

    if platform == "tiktok":
        adv = plat.get("advertiser_id", "").strip()
        if not adv:
            return pd.DataFrame(), None
        token = os.getenv("TIKTOK_ACCESS_TOKEN", "")
        if not token or token == "pending":
            return pd.DataFrame(), "Credentials pending"
        try:
            from tiktok_ads_server import fetch_tiktok_campaigns
            return fetch_tiktok_campaigns(token, adv, start, end, show_paused=False), None
        except Exception as e:
            return pd.DataFrame(), str(e)[:80]

    return pd.DataFrame(), None


def _fetch_daily_df(platform: str, proj: dict, start: str, end: str,
                    fetch_google_daily=None) -> pd.DataFrame:
    """Returns daily DataFrame with Date,Impressions,Clicks,Cost,Conversions,Conv. Value."""
    plat = proj.get("platforms", {}).get(platform, {})

    if platform == "google":
        cid = plat.get("customer_id", "").strip()
        if not cid or fetch_google_daily is None:
            return pd.DataFrame()
        try:
            return fetch_google_daily(cid, start, end)
        except Exception:
            return pd.DataFrame()

    if platform == "meta":
        acct = plat.get("ad_account_id", "").strip()
        if not acct:
            return pd.DataFrame()
        try:
            from meta_ads_server import fetch_meta_daily
            token = os.getenv("META_ACCESS_TOKEN", "")
            if not token:
                return pd.DataFrame()
            return fetch_meta_daily(token, acct, start, end)
        except Exception:
            return pd.DataFrame()

    if platform == "snap":
        acct = plat.get("ad_account_id", "").strip()
        if not acct:
            return pd.DataFrame()
        try:
            from snap_ads_server import fetch_snap_daily
            token = os.getenv("SNAP_ACCESS_TOKEN", "")
            if not token:
                return pd.DataFrame()
            return _snap_to_sar(fetch_snap_daily(token, acct, start, end, show_paused=True))
        except Exception:
            return pd.DataFrame()

    return pd.DataFrame()


def _summarise(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    spend       = float(df["Cost"].sum())         if "Cost" in df.columns        else 0.0
    revenue     = float(df["Conv. Value"].sum())  if "Conv. Value" in df.columns else 0.0
    conversions = float(df["Conversions"].sum())  if "Conversions" in df.columns else 0.0
    impressions = float(df["Impressions"].sum())  if "Impressions" in df.columns else 0.0
    clicks      = float(df["Clicks"].sum())       if "Clicks" in df.columns      else 0.0
    return {
        "spend":       spend,
        "revenue":     revenue,
        "conversions": conversions,
        "impressions": impressions,
        "clicks":      clicks,
        "roas":  revenue / spend       if spend       else 0.0,
        "cpa":   spend / conversions   if conversions else 0.0,
        "ctr":   clicks / impressions * 100  if impressions else 0.0,
        "cpm":   spend  / impressions * 1000 if impressions else 0.0,
        "aov":   revenue / conversions if conversions else 0.0,
        "cvr":   conversions / clicks * 100 if clicks else 0.0,
        "mer":   revenue / spend       if spend       else 0.0,
    }


def _agg_totals(results: dict) -> dict:
    spend  = sum(r["s"].get("spend", 0)       for r in results.values())
    rev    = sum(r["s"].get("revenue", 0)     for r in results.values())
    orders = sum(r["s"].get("conversions", 0) for r in results.values())
    impr   = sum(r["s"].get("impressions", 0) for r in results.values())
    clicks = sum(r["s"].get("clicks", 0)      for r in results.values())
    return {
        "spend":  spend, "revenue": rev, "orders": orders,
        "impr":   impr,  "clicks":  clicks,
        "roas":   rev   / spend  if spend  else 0.0,
        "cpa":    spend / orders if orders else 0.0,
        "ctr":    clicks / impr  * 100  if impr   else 0.0,
        "aov":    rev   / orders if orders else 0.0,
        "cvr":    orders / clicks * 100 if clicks else 0.0,
        "mer":    rev   / spend  if spend  else 0.0,
    }


def _aggregate_daily(results: dict) -> pd.DataFrame:
    dfs = [r["daily"] for r in results.values() if not r["daily"].empty]
    if not dfs:
        return pd.DataFrame()
    combined = pd.concat(dfs, ignore_index=True)
    agg = (combined.groupby("Date")
           .agg(Spend=("Cost", "sum"), Revenue=("Conv. Value", "sum"),
                Orders=("Conversions", "sum"), Impressions=("Impressions", "sum"),
                Clicks=("Clicks", "sum"))
           .reset_index()
           .sort_values("Date"))
    agg["ROAS"] = agg.apply(lambda r: r.Revenue / r.Spend    if r.Spend   else 0.0, axis=1)
    agg["CPA"]  = agg.apply(lambda r: r.Spend   / r.Orders   if r.Orders  else 0.0, axis=1)
    agg["CTR"]  = agg.apply(lambda r: r.Clicks  / r.Impressions * 100 if r.Impressions else 0.0, axis=1)
    agg["AOV"]  = agg.apply(lambda r: r.Revenue / r.Orders   if r.Orders  else 0.0, axis=1)
    # day-over-day deltas (sort ascending, shift, then reverse for display)
    agg["ROAS_prev"] = agg["ROAS"].shift(1)
    agg["CPA_prev"]  = agg["CPA"].shift(1)
    agg = agg.sort_values("Date", ascending=False).reset_index(drop=True)
    return agg


# ── section renderers ─────────────────────────────────────────────────────────

def _section_label(text: str) -> None:
    st.markdown(
        f"<div style='font-size:11px;font-weight:600;color:rgba(255,255,255,0.3);"
        f"text-transform:uppercase;letter-spacing:1.2px;margin:22px 0 10px'>{text}</div>",
        unsafe_allow_html=True,
    )


def _render_top_cards(curr: dict, prev: dict) -> None:
    """3 wide cards: Spend, Revenue, MER."""
    c1, c2, c3 = st.columns(3, gap="small")
    mer_c = "#f0f6fc" if not curr["mer"] else "#f0f6fc"

    _kpi_card(c1, "Total Spend",
              _fmt_sar(curr["spend"]),
              _delta_badge(curr["spend"], prev.get("spend", 0), higher_is_better=False))
    _kpi_card(c2, "Total Revenue",
              _fmt_sar(curr["revenue"]),
              _delta_badge(curr["revenue"], prev.get("revenue", 0)))
    _kpi_card(c3, "MER  (Revenue / Spend)",
              _fmt_x(curr["mer"]),
              _delta_badge(curr["mer"], prev.get("mer", 0)),
              color=mer_c)


def _render_metric_grid(curr: dict, prev: dict, target_mer: float, target_cpa: float) -> None:
    """8 cards in 2 rows of 4."""
    r1 = st.columns(4, gap="small")
    r2 = st.columns(4, gap="small")

    roas_c = _roas_color(curr["roas"], target_mer)
    cpa_c  = ("#3fb950" if (target_cpa and curr["cpa"] <= target_cpa)
              else "#f85149" if target_cpa else "#f0f6fc")

    # row 1
    _kpi_card(r1[0], "ROAS",
              _fmt_x(curr["roas"]),
              _delta_badge(curr["roas"], prev.get("roas", 0)),
              color=roas_c,
              sub=f"Target {target_mer:.1f}×" if target_mer else "")
    _kpi_card(r1[1], "Total Orders",
              _fmt_num(curr["orders"]),
              _delta_badge(curr["orders"], prev.get("orders", 0)))
    _kpi_card(r1[2], "Total Revenue",
              _fmt_sar(curr["revenue"]),
              _delta_badge(curr["revenue"], prev.get("revenue", 0)))
    _kpi_card(r1[3], "Total Spend",
              _fmt_sar(curr["spend"]),
              _delta_badge(curr["spend"], prev.get("spend", 0), higher_is_better=False))

    # row 2
    _kpi_card(r2[0], "CTR",
              _fmt_pct(curr["ctr"]),
              _delta_badge(curr["ctr"], prev.get("ctr", 0)))
    _kpi_card(r2[1], "CVR  (Orders / Clicks)",
              _fmt_pct(curr["cvr"]),
              _delta_badge(curr["cvr"], prev.get("cvr", 0)))
    _kpi_card(r2[2], "AOV  (Revenue / Order)",
              _fmt_sar(curr["aov"]),
              _delta_badge(curr["aov"], prev.get("aov", 0)))
    _kpi_card(r2[3], "CPA",
              _fmt_sar(curr["cpa"]),
              _delta_badge(curr["cpa"], prev.get("cpa", 0), higher_is_better=False),
              color=cpa_c,
              sub=f"Target {_fmt_sar(target_cpa)}" if target_cpa else "")


def _render_daily_chart(daily: pd.DataFrame) -> None:
    if daily.empty:
        st.info("No daily data available for chart.")
        return

    lines = st.multiselect(
        "Show lines",
        ["Spend", "Revenue", "Orders"],
        default=["Spend", "Revenue", "Orders"],
        key="proj_chart_lines",
        label_visibility="collapsed",
    )

    fig = go.Figure()
    line_cfg = {
        "Spend":   {"col": "Spend",   "color": "#58a6ff", "yaxis": "y"},
        "Revenue": {"col": "Revenue", "color": "#3fb950", "yaxis": "y"},
        "Orders":  {"col": "Orders",  "color": "#e3b341", "yaxis": "y2"},
    }

    has_orders = "Orders" in lines
    for name in lines:
        cfg = line_cfg[name]
        fig.add_trace(go.Scatter(
            x=daily["Date"], y=daily[cfg["col"]],
            name=name, mode="lines+markers",
            line=dict(color=cfg["color"], width=2),
            marker=dict(size=4),
            yaxis=cfg["yaxis"],
        ))

    layout = dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    font=dict(color="rgba(255,255,255,0.6)", size=11)),
        xaxis=dict(showgrid=False, tickfont=dict(color="rgba(255,255,255,0.4)", size=10),
                   linecolor="rgba(255,255,255,0.08)"),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                   tickfont=dict(color="rgba(255,255,255,0.4)", size=10),
                   linecolor="rgba(255,255,255,0.08)",
                   title=dict(text="SAR", font=dict(color="rgba(255,255,255,0.3)", size=10))),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#1c2128", bordercolor="rgba(255,255,255,0.1)",
                        font=dict(color="#f0f6fc", size=12)),
    )
    if has_orders:
        layout["yaxis2"] = dict(
            overlaying="y", side="right", showgrid=False,
            tickfont=dict(color="#e3b341", size=10),
            title=dict(text="Orders", font=dict(color="#e3b341", size=10)),
        )

    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_daily_table(daily: pd.DataFrame, platform_results: dict | None = None) -> None:
    if daily.empty:
        st.info("No daily data.")
        return

    show_breakdown = st.toggle("Show Platform Breakdown", key="proj_daily_breakdown")

    # Build per-date per-platform lookup from individual daily dfs
    plat_daily_lookup: dict[str, dict] = {}
    if show_breakdown and platform_results:
        for plat, res in platform_results.items():
            pday = res.get("daily", pd.DataFrame())
            if pday.empty:
                continue
            grp = (pday.groupby("Date")
                   .agg(Cost=("Cost", "sum"), Revenue=("Conv. Value", "sum"),
                        Orders=("Conversions", "sum"), Clicks=("Clicks", "sum"),
                        Impressions=("Impressions", "sum"))
                   .reset_index())
            for _, row in grp.iterrows():
                dstr = (row["Date"].strftime("%Y-%m-%d")
                        if hasattr(row["Date"], "strftime") else str(row["Date"])[:10])
                if dstr not in plat_daily_lookup:
                    plat_daily_lookup[dstr] = {}
                sp = float(row.get("Cost", 0))
                rv = float(row.get("Revenue", 0))
                ord_ = float(row.get("Orders", 0))
                cl = float(row.get("Clicks", 0))
                im = float(row.get("Impressions", 0))
                plat_daily_lookup[dstr][plat] = {
                    "spend": sp, "revenue": rv, "orders": ord_,
                    "roas": rv / sp   if sp   else 0.0,
                    "cpa":  sp / ord_ if ord_ else 0.0,
                    "ctr":  cl / im * 100 if im else 0.0,
                    "aov":  rv / ord_ if ord_ else 0.0,
                }

    # Best / worst summary
    valid_roas = daily[daily["ROAS"] > 0]
    valid_cpa  = daily[daily["CPA"] > 0]

    if not valid_roas.empty and not valid_cpa.empty:
        best_roas_row = valid_roas.loc[valid_roas["ROAS"].idxmax()]
        worst_cpa_row = valid_cpa.loc[valid_cpa["CPA"].idxmax()]
        best_dt  = best_roas_row["Date"].strftime("%b %d")
        worst_dt = worst_cpa_row["Date"].strftime("%b %d")

        bc, wc, _ = st.columns([2, 2, 6])
        bc.markdown(
            f"<div style='background:rgba(63,185,80,0.1);border:1px solid rgba(63,185,80,0.25);"
            f"border-radius:8px;padding:10px 14px'>"
            f"<div style='font-size:10px;color:#3fb950;text-transform:uppercase;letter-spacing:1px'>Best ROAS Day</div>"
            f"<div style='font-size:15px;font-weight:700;color:#f0f6fc;margin-top:3px'>{best_dt}</div>"
            f"<div style='font-size:12px;color:rgba(255,255,255,0.5);margin-top:1px'>"
            f"ROAS {best_roas_row['ROAS']:.2f}× · {_fmt_sar(best_roas_row['Spend'])}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        wc.markdown(
            f"<div style='background:rgba(248,81,73,0.1);border:1px solid rgba(248,81,73,0.25);"
            f"border-radius:8px;padding:10px 14px'>"
            f"<div style='font-size:10px;color:#f85149;text-transform:uppercase;letter-spacing:1px'>Worst CPA Day</div>"
            f"<div style='font-size:15px;font-weight:700;color:#f0f6fc;margin-top:3px'>{worst_dt}</div>"
            f"<div style='font-size:12px;color:rgba(255,255,255,0.5);margin-top:1px'>"
            f"CPA {_fmt_sar(worst_cpa_row['CPA'])} · {_fmt_sar(worst_cpa_row['Spend'])}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    best_roas_date  = valid_roas["ROAS"].idxmax() if not valid_roas.empty else None
    worst_cpa_date  = valid_cpa["CPA"].idxmax()   if not valid_cpa.empty  else None

    def _day_delta(curr_v: float, prev_v: float, higher_is_better: bool) -> str:
        if not prev_v or not curr_v:
            return ""
        pct = (curr_v - prev_v) / abs(prev_v) * 100
        if abs(pct) < 0.05:
            return ""
        up      = pct > 0
        is_good = up if higher_is_better else not up
        color   = "#3fb950" if is_good else "#f85149"
        arrow   = "▲" if up else "▼"
        return f"<span style='color:{color};font-size:10px'>{arrow}{abs(pct):.0f}%</span>"

    def _tc(v, extra=""):
        return (f"<td style='padding:8px 12px;text-align:right;font-family:monospace;"
                f"font-size:12px;color:#f0f6fc{extra}'>{v}</td>")
    def _td(v):
        return (f"<td style='padding:8px 12px;text-align:right;font-family:monospace;"
                f"font-size:12px;color:rgba(255,255,255,0.55)'>{v}</td>")

    rows_html = ""
    for idx, row in daily.iterrows():
        is_best  = (best_roas_date is not None and idx == best_roas_date)
        is_worst = (worst_cpa_date is not None and idx == worst_cpa_date)
        if is_best:
            row_bg = "rgba(63,185,80,0.08)"
        elif is_worst:
            row_bg = "rgba(248,81,73,0.08)"
        else:
            row_bg = "rgba(255,255,255,0.02)" if idx % 2 else "transparent"

        date_str = row["Date"].strftime("%Y-%m-%d") if hasattr(row["Date"], "strftime") else str(row["Date"])[:10]
        roas_d   = _day_delta(row["ROAS"], row.get("ROAS_prev", 0), higher_is_better=True)
        cpa_d    = _day_delta(row["CPA"],  row.get("CPA_prev",  0), higher_is_better=False)

        rows_html += (
            f"<tr style='background:{row_bg}'>"
            f"<td style='padding:8px 12px;font-size:12px;color:rgba(255,255,255,0.6)'>{date_str}</td>"
            + _tc(_fmt_sar(row["Spend"]))
            + _tc(_fmt_sar(row["Revenue"]))
            + f"<td style='padding:8px 12px;text-align:right;font-family:monospace;font-size:12px'>"
              f"<span style='color:#f0f6fc'>{_fmt_x(row['ROAS'])}</span> {roas_d}</td>"
            + _tc(_fmt_num(row["Orders"]))
            + f"<td style='padding:8px 12px;text-align:right;font-family:monospace;font-size:12px'>"
              f"<span style='color:#f0f6fc'>{_fmt_sar(row['CPA'])}</span> {cpa_d}</td>"
            + _td(_fmt_pct(row["CTR"]))
            + _td(_fmt_sar(row["AOV"]))
            + "</tr>"
        )

        # per-platform sub-rows
        if show_breakdown and date_str in plat_daily_lookup:
            for plat, pd_data in plat_daily_lookup[date_str].items():
                dot_c = _PLATFORM_COLORS.get(plat, "#aaa")
                label = _PLATFORM_LABELS.get(plat, plat)
                sub_bg = "rgba(255,255,255,0.015)"
                rows_html += (
                    f"<tr style='background:{sub_bg};border-top:1px solid rgba(255,255,255,0.03)'>"
                    f"<td style='padding:5px 12px 5px 28px;font-size:11px;color:rgba(255,255,255,0.38)'>"
                    f"<span style='display:inline-block;width:7px;height:7px;border-radius:50%;"
                    f"background:{dot_c};margin-right:5px;vertical-align:middle'></span>"
                    f"{label}</td>"
                    + f"<td style='padding:5px 12px;text-align:right;font-family:monospace;"
                      f"font-size:11px;color:rgba(255,255,255,0.45)'>{_fmt_sar(pd_data['spend'])}</td>"
                    + f"<td style='padding:5px 12px;text-align:right;font-family:monospace;"
                      f"font-size:11px;color:rgba(255,255,255,0.45)'>{_fmt_sar(pd_data['revenue'])}</td>"
                    + f"<td style='padding:5px 12px;text-align:right;font-family:monospace;"
                      f"font-size:11px;color:rgba(255,255,255,0.45)'>{_fmt_x(pd_data['roas'])}</td>"
                    + f"<td style='padding:5px 12px;text-align:right;font-family:monospace;"
                      f"font-size:11px;color:rgba(255,255,255,0.45)'>{_fmt_num(pd_data['orders'])}</td>"
                    + f"<td style='padding:5px 12px;text-align:right;font-family:monospace;"
                      f"font-size:11px;color:rgba(255,255,255,0.45)'>{_fmt_sar(pd_data['cpa'])}</td>"
                    + f"<td style='padding:5px 12px;text-align:right;font-family:monospace;"
                      f"font-size:11px;color:rgba(255,255,255,0.45)'>{_fmt_pct(pd_data['ctr'])}</td>"
                    + f"<td style='padding:5px 12px;text-align:right;font-family:monospace;"
                      f"font-size:11px;color:rgba(255,255,255,0.45)'>{_fmt_sar(pd_data['aov'])}</td>"
                    + "</tr>"
                )

    tbl = (
        "<div style='background:#161b22;border:1px solid rgba(255,255,255,0.07);"
        "border-radius:12px;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,sans-serif'>"
        "<table style='width:100%;border-collapse:collapse'>"
        "<thead><tr style='color:rgba(255,255,255,0.35);text-transform:uppercase;"
        "font-size:10px;letter-spacing:0.5px;border-bottom:1px solid rgba(255,255,255,0.06)'>"
        "<th style='text-align:left;padding:8px 12px'>Date</th>"
        "<th style='text-align:right;padding:8px 12px'>Spend</th>"
        "<th style='text-align:right;padding:8px 12px'>Revenue</th>"
        "<th style='text-align:right;padding:8px 12px'>ROAS</th>"
        "<th style='text-align:right;padding:8px 12px'>Orders</th>"
        "<th style='text-align:right;padding:8px 12px'>CPA</th>"
        "<th style='text-align:right;padding:8px 12px'>CTR</th>"
        "<th style='text-align:right;padding:8px 12px'>AOV</th>"
        f"</tr></thead><tbody>{rows_html}</tbody></table></div>"
    )
    st.html(tbl)


def _render_platform_table(results: dict, curr: dict, target_mer: float) -> None:
    rows_html = ""
    for i, (plat, res) in enumerate(results.items()):
        s      = res["s"]
        err    = res["err"]
        dot_c  = _PLATFORM_COLORS[plat]
        label  = _PLATFORM_LABELS[plat]
        bg     = "rgba(255,255,255,0.02)" if i % 2 else "transparent"
        ind_c  = _roas_ind_color(s.get("roas", 0), target_mer)

        ind_dot  = (f"<span style='display:inline-block;width:9px;height:9px;border-radius:50%;"
                    f"background:{ind_c};margin-right:6px;flex-shrink:0'></span>")
        plat_dot = (f"<span style='display:inline-block;width:8px;height:8px;border-radius:50%;"
                    f"background:{dot_c};margin-right:7px;flex-shrink:0'></span>")
        name_cell = (
            f"<td style='padding:10px 14px'><div style='display:flex;align-items:center'>"
            f"{ind_dot}{plat_dot}<span style='font-weight:600;color:#f0f6fc'>{label}</span>"
            f"</div></td>"
        )

        if err and res["empty"]:
            rows_html += (
                f"<tr style='background:{bg}'>{name_cell}"
                f"<td colspan='7' style='padding:10px 14px;color:#ff6b6b;font-size:11px'>"
                f"Error: {err}</td></tr>"
            )
        else:
            sv  = s.get("spend",       0); rv  = s.get("revenue",     0)
            rv_ = s.get("roas",        0); cv  = s.get("cpa",         0)
            ov  = s.get("conversions", 0); tv  = s.get("ctr",         0)
            pv  = s.get("cpm",         0)
            rc  = _roas_color(rv_, target_mer)
            rd  = f"{rv_:.2f}&times;" if sv else "&mdash;"

            def _tc(v):
                return (f"<td style='padding:10px 14px;text-align:right;"
                        f"font-family:monospace;color:#f0f6fc'>{v}</td>")
            def _td(v):
                return (f"<td style='padding:10px 14px;text-align:right;"
                        f"font-family:monospace;color:rgba(255,255,255,0.55)'>{v}</td>")

            rows_html += (
                f"<tr style='background:{bg}'>{name_cell}"
                + _tc(_fmt_sar(sv)) + _tc(_fmt_sar(rv))
                + f"<td style='padding:10px 14px;text-align:right;font-family:monospace;"
                  f"color:{rc};font-weight:600'>{rd}</td>"
                + _tc(_fmt_sar(cv)) + _tc(_fmt_num(ov))
                + _td(_fmt_pct(tv)) + _td(_fmt_sar(pv))
                + "</tr>"
            )

    # totals row
    total_rc = _roas_color(curr["roas"], target_mer)
    total_rd = f"{curr['roas']:.2f}&times;" if curr["spend"] else "&mdash;"
    rows_html += (
        f"<tr style='background:rgba(255,255,255,0.055);border-top:1px solid rgba(255,255,255,0.1)'>"
        f"<td style='padding:11px 14px'><div style='display:flex;align-items:center'>"
        f"<span style='display:inline-block;width:9px;height:9px;border-radius:2px;"
        f"background:rgba(255,255,255,0.25);margin-right:13px'></span>"
        f"<span style='font-weight:700;color:#f0f6fc'>Total</span></div></td>"
        f"<td style='padding:11px 14px;text-align:right;font-family:monospace;font-weight:700;color:#f0f6fc'>{_fmt_sar(curr['spend'])}</td>"
        f"<td style='padding:11px 14px;text-align:right;font-family:monospace;font-weight:700;color:#f0f6fc'>{_fmt_sar(curr['revenue'])}</td>"
        f"<td style='padding:11px 14px;text-align:right;font-family:monospace;font-weight:700;color:{total_rc}'>{total_rd}</td>"
        f"<td style='padding:11px 14px;text-align:right;font-family:monospace;font-weight:700;color:#f0f6fc'>{_fmt_sar(curr['cpa'])}</td>"
        f"<td style='padding:11px 14px;text-align:right;font-family:monospace;font-weight:700;color:#f0f6fc'>{_fmt_num(curr['orders'])}</td>"
        f"<td style='padding:11px 14px;text-align:right;font-family:monospace;color:rgba(255,255,255,0.55)'>{_fmt_pct(curr['ctr'])}</td>"
        f"<td style='padding:11px 14px;text-align:right;font-family:monospace;color:rgba(255,255,255,0.55)'></td>"
        f"</tr>"
    )

    tbl = (
        "<div style='background:#161b22;border:1px solid rgba(255,255,255,0.07);"
        "border-radius:12px;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,sans-serif'>"
        "<table style='width:100%;border-collapse:collapse;font-size:13px'>"
        "<thead><tr style='color:rgba(255,255,255,0.4);text-transform:uppercase;"
        "font-size:10px;letter-spacing:0.5px;border-bottom:1px solid rgba(255,255,255,0.08)'>"
        "<th style='text-align:left;padding:8px 14px;width:170px'></th>"
        "<th style='text-align:right;padding:8px 14px'>Spend</th>"
        "<th style='text-align:right;padding:8px 14px'>Revenue</th>"
        "<th style='text-align:right;padding:8px 14px'>ROAS</th>"
        "<th style='text-align:right;padding:8px 14px'>CPA</th>"
        "<th style='text-align:right;padding:8px 14px'>Orders</th>"
        "<th style='text-align:right;padding:8px 14px'>CTR</th>"
        "<th style='text-align:right;padding:8px 14px'>CPM</th>"
        f"</tr></thead><tbody>{rows_html}</tbody></table></div>"
    )
    st.html(tbl)


# ── ads performance: helpers ──────────────────────────────────────────────────

def _ai_note(spend: float, roas: float, cpa: float, ctr: float,
             target_mer: float = 0, target_cpa: float = 0) -> str:
    if spend == 0:
        return "⏸️ متوقفة"
    if roas > 2:
        return "✅ ارفع الميزانية"
    if roas < 1:
        return "🔴 خسران — أوقف أو عدّل"
    if cpa > 150:
        return "🔴 CPA مرتفع — راجع الاستهداف"
    if ctr < 0.5:
        return "⚠️ CTR منخفض — اختبر كريتيف"
    return "🟡 راقب الأداء"


def _normalise_df(df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return a unified DataFrame with columns needed for the ads table."""
    if df.empty:
        return pd.DataFrame()
    out = df.copy()
    # Ensure ID column
    if "ID" not in out.columns:
        out["ID"] = out.get("Campaign ID", pd.Series([""] * len(out), index=out.index))
    # Name column
    out["_Name"] = out.get("Campaign", pd.Series([""] * len(out), index=out.index))
    out["_Platform"] = platform
    # ROAS: compute if missing
    if "ROAS" not in out.columns or out["ROAS"].fillna(0).sum() == 0:
        out["ROAS"] = out.apply(
            lambda r: round(r["Conv. Value"] / r["Cost"], 2) if r.get("Cost", 0) > 0 else 0.0,
            axis=1,
        )
    # CPM
    out["_CPM"] = out.apply(
        lambda r: round(r["Cost"] / r["Impressions"] * 1000, 2) if r.get("Impressions", 0) > 0 else 0.0,
        axis=1,
    )
    # Status normalise
    _status_map = {"ENABLED": "ENABLED", "ACTIVE": "ENABLED", "PAUSED": "PAUSED",
                   "REMOVED": "REMOVED"}
    out["_Status"] = out.get("Status", pd.Series(["ENABLED"] * len(out), index=out.index)).map(
        lambda s: _status_map.get(str(s).upper(), str(s))
    )
    return out


def _ads_summary_bar(df: pd.DataFrame) -> None:
    if df.empty:
        return
    spend = float(df["Cost"].sum()) if "Cost" in df.columns else 0
    rev   = float(df["Conv. Value"].sum()) if "Conv. Value" in df.columns else 0
    orders= float(df["Conversions"].sum()) if "Conversions" in df.columns else 0
    roas  = round(rev / spend, 2) if spend else 0.0

    c1, c2, c3, c4 = st.columns(4, gap="small")
    _ks = ("background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.07);"
           "border-radius:10px;padding:12px 16px;text-align:center")
    _lbl = "font-size:9.5px;color:rgba(255,255,255,0.35);text-transform:uppercase;letter-spacing:1px"
    _val = "font-size:19px;font-weight:800;color:#f0f6fc;margin-top:3px"

    for col, label, value in [
        (c1, "ROAS",    f"{roas:.2f}×"),
        (c2, "Spend",   _fmt_sar(spend)),
        (c3, "Revenue", _fmt_sar(rev)),
        (c4, "Orders",  _fmt_num(orders)),
    ]:
        col.markdown(
            f"<div style='{_ks}'><div style='{_lbl}'>{label}</div>"
            f"<div style='{_val}'>{value}</div></div>",
            unsafe_allow_html=True,
        )


def _platform_comparison_bar(df_all: pd.DataFrame, active_plats: list[str],
                             highlighted: str) -> None:
    """
    Vertical per-platform spend / ROAS / share rows — one platform per line.
    Always renders all 4 platforms; platforms with no credentials are greyed
    out with "قريباً".
    df_all      — unfiltered level-1 DataFrame (all platforms, all statuses).
    active_plats — platform keys that have credentials configured.
    highlighted  — "الكل" or a platform key that is currently selected.
    """
    _ALL   = ["google", "meta", "snap", "tiktok"]
    _DOT   = {"google": "🔵", "meta": "🟣", "snap": "🟡", "tiktok": "⚫"}
    _NAMES = {"google": "Google", "meta": "Meta", "snap": "Snap", "tiktok": "TikTok"}

    # Aggregate spend + revenue from the raw df
    grp: dict = {}
    if not df_all.empty and "_Platform" in df_all.columns:
        g = (
            df_all.groupby("_Platform")[["Cost", "Conv. Value"]]
            .sum()
            .rename(columns={"Cost": "spend", "Conv. Value": "rev"})
        )
        grp = g.to_dict("index")

    # Total spend across configured platforms only (for % calculation)
    total_spend = sum(grp.get(p, {}).get("spend", 0) for p in active_plats)

    rows_html = ""
    for plat in _ALL:
        color      = _PLATFORM_COLORS.get(plat, "#888")
        has_creds  = plat in active_plats
        data       = grp.get(plat, {"spend": 0.0, "rev": 0.0})
        spend      = float(data.get("spend", 0))
        rev        = float(data.get("rev", 0))
        roas       = rev / spend if spend > 0 else 0.0
        pct        = spend / total_spend * 100 if total_spend > 0 else 0.0
        is_sel     = highlighted in ("الكل", plat)

        # Opacity: no-creds = very faded, has-creds-not-selected = semi, selected = full
        if not has_creds:
            opacity = "0.32"
        elif not is_sel:
            opacity = "0.45"
        else:
            opacity = "1"

        # Name cell
        name_cell = (
            f"<div style='min-width:80px;font-size:12.5px;font-weight:600;"
            f"color:rgba(255,255,255,0.85)'>"
            f"{_DOT[plat]} {_NAMES[plat]}</div>"
        )

        # Spend cell
        if not has_creds:
            spend_cell = (
                "<div style='min-width:90px;font-size:11px;"
                "color:rgba(255,255,255,0.25)'>—&nbsp;&nbsp;"
                "<span style='font-size:10px;color:rgba(255,255,255,0.2)'>قريباً</span></div>"
            )
        else:
            spend_cell = (
                f"<div style='min-width:90px;font-size:13px;font-weight:700;"
                f"color:#f0f6fc'>{_fmt_sar(spend)}</div>"
            )

        # ROAS cell
        if not has_creds or roas == 0:
            roas_cell = "<div style='min-width:52px;font-size:11px;color:rgba(255,255,255,0.25)'>—</div>"
        else:
            roas_cell = (
                f"<div style='min-width:52px;font-size:12px;font-weight:600;"
                f"color:{color}'>{roas:.2f}×</div>"
            )

        # Progress bar (flex:1 so it fills remaining space)
        fill = (
            f"<div style='background:{color};width:{pct:.1f}%;height:6px;"
            f"border-radius:3px;min-width:{'3px' if pct > 0 else '0'}'></div>"
        )
        bar_cell = (
            f"<div style='flex:1;padding:0 10px'>"
            f"<div style='background:rgba(255,255,255,0.07);border-radius:3px;"
            f"height:6px;overflow:hidden'>{fill}</div>"
            f"</div>"
        )

        # Percent cell
        pct_cell = (
            f"<div style='min-width:34px;text-align:right;font-size:11px;"
            f"color:rgba(255,255,255,0.38)'>{pct:.0f}%</div>"
        )

        rows_html += (
            f"<div style='display:flex;align-items:center;padding:9px 0;"
            f"border-bottom:1px solid rgba(255,255,255,0.04);opacity:{opacity}'>"
            f"{name_cell}{spend_cell}{roas_cell}{bar_cell}{pct_cell}"
            f"</div>"
        )

    st.markdown(
        f"<div style='background:rgba(255,255,255,0.02);"
        f"border:1px solid rgba(255,255,255,0.07);border-radius:10px;"
        f"padding:2px 16px 2px'>{rows_html}</div>",
        unsafe_allow_html=True,
    )


_FILTER_BTNS = ["الكل", "شغالة", "شاملة"]
_SORT_BTNS   = ["ROAS ↓", "الإنفاق ↓"]


def _apply_filter_sort(df: pd.DataFrame, filt: str, sort_key: str) -> pd.DataFrame:
    if df.empty:
        return df
    if filt == "شغالة":
        df = df[df["_Status"] == "ENABLED"]
    # sort
    sort_col = {"ROAS ↓": "ROAS", "الإنفاق ↓": "Cost"}.get(sort_key, "Cost")
    if sort_col in df.columns:
        df = df.sort_values(sort_col, ascending=False)
    return df.reset_index(drop=True)


def _status_badge(status: str) -> str:
    if status == "ENABLED":
        return ("<span style='background:rgba(63,185,80,0.15);color:#3fb950;"
                "font-size:10px;padding:2px 7px;border-radius:10px;"
                "border:1px solid rgba(63,185,80,0.3)'>● شغال</span>")
    if status == "PAUSED":
        return ("<span style='background:rgba(227,179,65,0.15);color:#e3b341;"
                "font-size:10px;padding:2px 7px;border-radius:10px;"
                "border:1px solid rgba(227,179,65,0.3)'>⏸ موقوف</span>")
    return ("<span style='background:rgba(255,255,255,0.07);color:rgba(255,255,255,0.4);"
            "font-size:10px;padding:2px 7px;border-radius:10px'>—</span>")


def _roas_cell(roas: float, target_mer: float) -> str:
    color = _roas_color(roas, target_mer)
    return f"<span style='color:{color};font-weight:600'>{roas:.2f}×</span>" if roas else "—"


# Column weights:  name  status spend  rev  roas  orders cpa  ctr  cpm  note
_TBL_W = [4, 1, 1, 1, 1, 1, 1, 1, 1, 3]
_TBL_HDRS = ["الاسم", "الحالة", "الإنفاق", "الإيراد", "ROAS", "الطلبات", "CPA", "CTR%", "CPM", "ملاحظة"]

_ADT_CSS = """<style>
/* name-column buttons look like plain links */
div[data-testid="stColumns"] button[data-testid="baseButton-secondary"] {
    background:transparent !important;border:none !important;
    color:#58a6ff !important;font-size:12px !important;
    text-align:left !important;padding:4px 0 !important;
    box-shadow:none !important;
}
div[data-testid="stColumns"] button[data-testid="baseButton-secondary"]:hover {
    color:#79b8ff !important;background:rgba(88,166,255,0.06) !important;
}
</style>"""


def _render_ads_table(df: pd.DataFrame, target_mer: float, target_cpa: float,
                      drillable: bool, platform_col: str,
                      on_click_key_prefix: str) -> tuple | None:
    """Column-based table. Returns (platform, id, name) when a name is clicked, else None."""
    if df.empty:
        st.info("لا توجد بيانات لهذه الفترة.")
        return None

    st.markdown(_ADT_CSS, unsafe_allow_html=True)

    # Header row
    _hs = ("font-size:9.5px;color:rgba(255,255,255,0.3);text-transform:uppercase;"
           "letter-spacing:0.5px;font-weight:600;padding:2px 0 6px")
    hcols = st.columns(_TBL_W)
    for col, h in zip(hcols, _TBL_HDRS):
        col.markdown(f"<div style='{_hs}'>{h}</div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='height:1px;background:rgba(255,255,255,0.07);margin-bottom:2px'></div>",
        unsafe_allow_html=True,
    )

    click_result = None
    _tv  = "font-size:12px;color:#f0f6fc;padding:5px 0"
    _tvd = "font-size:12px;color:rgba(255,255,255,0.5);padding:5px 0"

    for idx, row in df.iterrows():
        plat   = str(row.get("_Platform", platform_col))
        eid    = str(row.get("ID", row.get("Campaign ID", "")))
        name   = str(row["_Name"])
        status = str(row.get("_Status", ""))
        spend  = float(row.get("Cost", 0))
        rev    = float(row.get("Conv. Value", 0))
        roas   = float(row.get("ROAS", 0))
        orders = float(row.get("Conversions", 0))
        cpa    = float(row.get("CPA", 0))
        ctr    = float(row.get("CTR", 0))
        cpm    = float(row.get("_CPM", 0))
        note   = _ai_note(spend, roas, cpa, ctr, target_mer, target_cpa)
        dot_c  = _PLATFORM_COLORS.get(plat, "#888")

        rcols = st.columns(_TBL_W)

        # name cell — button if drillable, plain text otherwise
        dot = (f"<span style='display:inline-block;width:7px;height:7px;border-radius:50%;"
               f"background:{dot_c};margin-right:5px;vertical-align:middle'></span>")
        if drillable and eid:
            if rcols[0].button(
                f"{name[:45]}",
                key=f"{on_click_key_prefix}_{idx}",
                use_container_width=True,
            ):
                click_result = (plat, eid, name)
        else:
            rcols[0].markdown(
                f"<div style='{_tv}'>{dot}{name[:45]}</div>",
                unsafe_allow_html=True,
            )

        rcols[1].markdown(
            f"<div style='padding:5px 0'>{_status_badge(status)}</div>",
            unsafe_allow_html=True,
        )
        rcols[2].markdown(f"<div style='{_tv}'>{_fmt_sar(spend)}</div>", unsafe_allow_html=True)
        rcols[3].markdown(f"<div style='{_tv}'>{_fmt_sar(rev)}</div>", unsafe_allow_html=True)
        rcols[4].markdown(
            f"<div style='padding:5px 0'>{_roas_cell(roas, target_mer)}</div>",
            unsafe_allow_html=True,
        )
        rcols[5].markdown(f"<div style='{_tv}'>{_fmt_num(orders)}</div>", unsafe_allow_html=True)
        rcols[6].markdown(
            f"<div style='{_tv}'>{_fmt_sar(cpa) if cpa else '—'}</div>",
            unsafe_allow_html=True,
        )
        rcols[7].markdown(f"<div style='{_tvd}'>{_fmt_pct(ctr)}</div>", unsafe_allow_html=True)
        rcols[8].markdown(
            f"<div style='{_tvd}'>{_fmt_sar(cpm) if cpm else '—'}</div>",
            unsafe_allow_html=True,
        )
        rcols[9].markdown(
            f"<div style='font-size:11.5px;padding:5px 0;color:#f0f6fc'>{note}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div style='height:1px;background:rgba(255,255,255,0.04);margin:0'></div>",
            unsafe_allow_html=True,
        )

    return click_result


# ── ads performance: data fetchers ────────────────────────────────────────────

def _fetch_ads_level1(proj: dict, start: str, end: str, fetch_google=None) -> pd.DataFrame:
    """All campaigns from all connected platforms, normalised."""
    plat_cfg = proj.get("platforms", {})
    frames   = []

    # Google
    cid = plat_cfg.get("google", {}).get("customer_id", "").strip()
    if cid and fetch_google:
        try:
            gdf = fetch_google(cid, start, end)
            if not gdf.empty:
                frames.append(_normalise_df(gdf, "google"))
        except Exception as _exc:
            logging.getLogger(__name__).debug('suppressed: %s', _exc)

    # Meta
    acct = plat_cfg.get("meta", {}).get("ad_account_id", "").strip()
    if acct:
        try:
            from meta_ads_server import fetch_meta_campaigns
            token = os.getenv("META_ACCESS_TOKEN", "")
            if token:
                mdf = fetch_meta_campaigns(token, acct, start, end)
                if not mdf.empty:
                    frames.append(_normalise_df(mdf, "meta"))
        except Exception as _exc:
            logging.getLogger(__name__).debug('suppressed: %s', _exc)

    # Snap
    sacct = plat_cfg.get("snap", {}).get("ad_account_id", "").strip()
    if sacct:
        try:
            from snap_ads_server import fetch_snap_campaigns
            stoken = os.getenv("SNAP_ACCESS_TOKEN", "")
            if stoken:
                sdf = _snap_to_sar(fetch_snap_campaigns(stoken, sacct, start, end))
                if not sdf.empty:
                    frames.append(_normalise_df(sdf, "snap"))
        except Exception as _exc:
            logging.getLogger(__name__).debug('suppressed: %s', _exc)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _fetch_ads_level2(proj: dict, platform: str, campaign_id: str,
                      start: str, end: str, fetch_google_adgroups=None) -> pd.DataFrame:
    """Ad sets / ad groups for the selected campaign."""
    plat_cfg = proj.get("platforms", {})

    if platform == "google":
        cid = plat_cfg.get("google", {}).get("customer_id", "").strip()
        if cid and fetch_google_adgroups:
            try:
                df = fetch_google_adgroups(cid, start, end, campaign_id)
                return _normalise_df(df, "google") if not df.empty else pd.DataFrame()
            except Exception:
                return pd.DataFrame()

    if platform == "meta":
        try:
            from meta_ads_server import fetch_meta_adsets
            token = os.getenv("META_ACCESS_TOKEN", "")
            if token:
                df = fetch_meta_adsets(token, campaign_id, start, end)
                return _normalise_df(df, "meta") if not df.empty else pd.DataFrame()
        except Exception as _exc:
            logging.getLogger(__name__).debug('suppressed: %s', _exc)

    if platform == "snap":
        acct = plat_cfg.get("snap", {}).get("ad_account_id", "").strip()
        try:
            from snap_ads_server import fetch_snap_adsets
            stoken = os.getenv("SNAP_ACCESS_TOKEN", "")
            if stoken:
                df = _snap_to_sar(fetch_snap_adsets(stoken, campaign_id, start, end, acct))
                return _normalise_df(df, "snap") if not df.empty else pd.DataFrame()
        except Exception as _exc:
            logging.getLogger(__name__).debug('suppressed: %s', _exc)

    return pd.DataFrame()


def _fetch_ads_level3(proj: dict, platform: str, adset_id: str,
                      start: str, end: str, fetch_google_ads=None) -> pd.DataFrame:
    """Ads within the selected ad set / ad group."""
    plat_cfg = proj.get("platforms", {})

    if platform == "google":
        cid = plat_cfg.get("google", {}).get("customer_id", "").strip()
        if cid and fetch_google_ads:
            try:
                df = fetch_google_ads(cid, start, end, adset_id)
                return _normalise_df(df, "google") if not df.empty else pd.DataFrame()
            except Exception:
                return pd.DataFrame()

    if platform == "meta":
        try:
            from meta_ads_server import fetch_meta_ads_list
            token = os.getenv("META_ACCESS_TOKEN", "")
            if token:
                df = fetch_meta_ads_list(token, adset_id, start, end)
                return _normalise_df(df, "meta") if not df.empty else pd.DataFrame()
        except Exception as _exc:
            logging.getLogger(__name__).debug('suppressed: %s', _exc)

    if platform == "snap":
        acct = plat_cfg.get("snap", {}).get("ad_account_id", "").strip()
        try:
            from snap_ads_server import fetch_snap_ads
            stoken = os.getenv("SNAP_ACCESS_TOKEN", "")
            if stoken:
                df = _snap_to_sar(fetch_snap_ads(stoken, adset_id, start, end, acct))
                return _normalise_df(df, "snap") if not df.empty else pd.DataFrame()
        except Exception as _exc:
            logging.getLogger(__name__).debug('suppressed: %s', _exc)

    return pd.DataFrame()


# ── ads performance: main renderer ────────────────────────────────────────────

def _render_ads_performance(proj: dict, start: str, end: str,
                            fetch_google=None,
                            fetch_google_adgroups=None,
                            fetch_google_ads=None) -> None:
    pid        = proj["id"]
    target_mer = float(proj.get("target_mer", 0))
    target_cpa = float(proj.get("target_cpa", 0))

    # ── Session-state keys (project-scoped) ───────────────────────────────────
    sk_level   = f"adp_level_{pid}"
    sk_platform= f"adp_plat_{pid}"
    sk_cid     = f"adp_cid_{pid}"
    sk_cname   = f"adp_cname_{pid}"
    sk_aid     = f"adp_aid_{pid}"
    sk_aname   = f"adp_aname_{pid}"
    sk_filter  = f"adp_filter_{pid}"
    sk_sort    = f"adp_sort_{pid}"
    sk_platf   = f"adp_platf_{pid}"   # platform filter (level-1 only)

    level      = st.session_state.get(sk_level, 1)
    platform   = st.session_state.get(sk_platform, "")
    camp_id    = st.session_state.get(sk_cid, "")
    camp_name  = st.session_state.get(sk_cname, "")
    adset_id   = st.session_state.get(sk_aid, "")
    adset_name = st.session_state.get(sk_aname, "")
    cur_filter = st.session_state.get(sk_filter, "الكل")
    cur_sort   = st.session_state.get(sk_sort, "ROAS ↓")
    cur_platf  = st.session_state.get(sk_platf, "الكل")  # "الكل" or platform key

    # Platforms configured for this project (used to build the filter row)
    plat_cfg = proj.get("platforms", {})
    active_plats = [
        p for p in ["google", "meta", "snap", "tiktok"]
        if any(str(v).strip() for v in plat_cfg.get(p, {}).values())
    ]

    # ── Fetch data ────────────────────────────────────────────────────────────
    if level == 1:
        df_raw = _fetch_ads_level1(proj, start, end, fetch_google)
        df_raw = _normalise_df(df_raw, platform) if not df_raw.empty and "_Name" not in df_raw.columns else df_raw
        # df_raw keeps all platforms for the comparison bar
        # df is the view actually shown in summary + table
        if cur_platf != "الكل" and not df_raw.empty and "_Platform" in df_raw.columns:
            df = df_raw[df_raw["_Platform"] == cur_platf].reset_index(drop=True)
        else:
            df = df_raw
    else:
        df_raw = pd.DataFrame()   # comparison bar only shown at level 1
        if level == 2:
            df = _fetch_ads_level2(proj, platform, camp_id, start, end, fetch_google_adgroups)
        else:
            df = _fetch_ads_level3(proj, platform, adset_id, start, end, fetch_google_ads)
        df = _normalise_df(df, platform) if not df.empty and "_Name" not in df.columns else df

    df = _apply_filter_sort(df, cur_filter, cur_sort)

    # ── 0. Platform filter row ────────────────────────────────────────────────
    # Determine which button is "active" for highlighting:
    # at level 1 → cur_platf;  at level 2/3 → the drill-down platform
    highlighted_plat = platform if level > 1 else cur_platf

    plat_btn_labels = ["الكل"] + [_PLAT_BTN_LABELS[p] for p in active_plats]
    plat_btn_keys   = ["الكل"] + active_plats          # parallel list of keys
    # columns: one per button + filler
    pcols = st.columns([1.1] * len(plat_btn_labels) + [max(0.1, 10 - 1.1 * len(plat_btn_labels))])
    for col, lbl, key in zip(pcols, plat_btn_labels, plat_btn_keys):
        is_active = (key == highlighted_plat) or (key == "الكل" and highlighted_plat == "الكل")
        if col.button(lbl, key=f"adp_pf_{key}_{pid}",
                      type="primary" if is_active else "secondary",
                      use_container_width=True):
            # Reset drill-down state and apply platform filter
            for k in [sk_level, sk_cid, sk_cname, sk_aid, sk_aname]:
                st.session_state.pop(k, None)
            st.session_state[sk_platf]  = key          # "الكل" or e.g. "google"
            st.session_state[sk_filter] = "الكل"
            if key != "الكل":
                st.session_state[sk_platform] = key
            else:
                st.session_state.pop(sk_platform, None)
            st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── 1. Summary bar ────────────────────────────────────────────────────────
    _ads_summary_bar(df)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ── 1b. Platform comparison bar (level 1 only, 2+ platforms) ─────────────
    if level == 1:
        _platform_comparison_bar(df_raw, active_plats, cur_platf)
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ── 2. Filter + sort row ──────────────────────────────────────────────────
    fc = st.columns([1, 1, 1, 0.2, 1.2, 1.2, 4])
    for i, lbl in enumerate(_FILTER_BTNS):
        btn_t = "primary" if cur_filter == lbl else "secondary"
        if fc[i].button(lbl, key=f"adp_f_{lbl}_{pid}", type=btn_t, use_container_width=True):
            st.session_state[sk_filter] = lbl
            st.rerun()
    for j, lbl in enumerate(_SORT_BTNS):
        btn_t = "primary" if cur_sort == lbl else "secondary"
        if fc[4 + j].button(lbl, key=f"adp_s_{lbl}_{pid}", type=btn_t, use_container_width=True):
            st.session_state[sk_sort] = lbl
            st.rerun()

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ── 3. Tab buttons (horizontal) ───────────────────────────────────────────
    tab_defs = [(1, "📋 الحملات"), (2, "📦 المجموعات"), (3, "📢 الإعلانات")]
    tc1, tc2, tc3, _ = st.columns([1.4, 1.5, 1.5, 5.6])
    for col, (lv, lbl) in zip([tc1, tc2, tc3], tab_defs):
        active   = level == lv
        disabled = (lv == 2 and not camp_id) or (lv == 3 and not adset_id)
        if not disabled:
            if col.button(lbl, key=f"adp_tab_{lv}_{pid}",
                          type="primary" if active else "secondary",
                          use_container_width=True):
                if lv == 1:
                    for k in [sk_level, sk_platform, sk_cid, sk_cname, sk_aid, sk_aname]:
                        st.session_state.pop(k, None)
                elif lv == 2:
                    st.session_state[sk_level] = 2
                    st.session_state.pop(sk_aid, None)
                    st.session_state.pop(sk_aname, None)
                st.session_state[sk_filter] = "الكل"
                st.rerun()
        else:
            col.markdown(
                f"<div style='font-size:13px;color:rgba(255,255,255,0.2);padding:6px 0'>{lbl}</div>",
                unsafe_allow_html=True,
            )

    # breadcrumb hint when drilled in
    if level > 1:
        parts = [f"<span style='color:rgba(255,255,255,0.35)'>الحملات</span>"]
        if level >= 2:
            parts.append(f"<span style='color:#58a6ff'>{camp_name[:35]}</span>")
        if level >= 3:
            parts.append(f"<span style='color:#58a6ff'>{adset_name[:35]}</span>")
        sep = "<span style='color:rgba(255,255,255,0.2);margin:0 5px'>›</span>"
        st.markdown(
            f"<div style='font-size:11px;color:rgba(255,255,255,0.4);margin:6px 0 2px'>"
            f"{sep.join(parts)}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── 4. Table ──────────────────────────────────────────────────────────────
    click = _render_ads_table(
        df, target_mer, target_cpa,
        drillable=level < 3,
        platform_col=platform,
        on_click_key_prefix=f"adp_row_{level}_{pid}",
    )

    if click:
        clicked_plat, clicked_id, clicked_name = click
        if level == 1:
            st.session_state[sk_level]    = 2
            st.session_state[sk_platform] = clicked_plat
            st.session_state[sk_cid]      = clicked_id
            st.session_state[sk_cname]    = clicked_name
            st.session_state.pop(sk_aid, None)
            st.session_state.pop(sk_aname, None)
        elif level == 2:
            st.session_state[sk_level]    = 3
            st.session_state[sk_platform] = clicked_plat
            st.session_state[sk_aid]      = clicked_id
            st.session_state[sk_aname]    = clicked_name
        st.session_state[sk_filter] = "الكل"
        st.rerun()


# ── project detail helpers ────────────────────────────────────────────────────

# ══════════════════════════════════════════════════════════════════════════════
# ALERTS PAGE
# ══════════════════════════════════════════════════════════════════════════════

def generate_alerts(
    df_curr: pd.DataFrame,
    df_prev: pd.DataFrame,
    target_cpa: float,
    target_mer: float,
) -> list[dict]:
    """
    Pure function — evaluates alert rules against campaign-level DataFrames.
    df_curr / df_prev must have columns: _Name, _Platform, _CPM, Cost,
    ROAS, CPA, CTR, Conversions, Impressions, Conv. Value.
    Returns a list of alert dicts.
    """
    alerts: list[dict] = []
    if df_curr.empty:
        return alerts

    # Build prev-period lookup: (platform, name) → row
    prev_idx: dict[tuple, pd.Series] = {}
    if not df_prev.empty and "_Platform" in df_prev.columns and "_Name" in df_prev.columns:
        for _, r in df_prev.iterrows():
            prev_idx[(str(r["_Platform"]), str(r["_Name"]))] = r

    for _, row in df_curr.iterrows():
        camp = str(row.get("_Name", ""))
        plat = str(row.get("_Platform", ""))
        spend  = float(row.get("Cost", 0) or 0)
        roas   = float(row.get("ROAS", 0) or 0)
        cpa    = float(row.get("CPA", 0) or 0)
        ctr    = float(row.get("CTR", 0) or 0)
        orders = float(row.get("Conversions", 0) or 0)
        impr   = float(row.get("Impressions", 0) or 0)
        cpm    = float(row.get("_CPM", 0) or 0)

        def _add(severity, metric, value, threshold, title, desc, action):
            alerts.append({
                "campaign_name": camp,
                "platform":      plat,
                "metric":        metric,
                "value":         value,
                "threshold":     threshold,
                "severity":      severity,
                "title":         title,
                "description":   desc,
                "action":        action,
                "period":        "الفترة الحالية",
            })

        # ── Critical ──────────────────────────────────────────────────────
        if spend > 0 and roas < 1:
            _add("critical", "ROAS", roas, 1.0,
                 "ROAS أقل من 1",
                 "تخسر على كل ريال تنفقه في هذه الحملة",
                 "أوقف أو عدّل فوراً")

        if target_cpa > 0 and cpa > target_cpa * 2:
            _add("critical", "CPA", cpa, target_cpa * 2,
                 "CPA ضعف الهدف",
                 f"CPA الحالي {_fmt_sar(cpa)} مقابل هدف {_fmt_sar(target_cpa)}",
                 "أوقف الحملة")

        if spend > 500 and orders == 0:
            _add("critical", "Conversions", orders, 1,
                 "إنفاق بدون طلبات",
                 f"تم إنفاق {_fmt_sar(spend)} دون أي طلب",
                 "أوقف وراجع الاستهداف")

        # ── Warning ───────────────────────────────────────────────────────
        if ctr < 0.5 and impr > 10_000:
            _add("warning", "CTR", ctr, 0.5,
                 "CTR منخفض — كريتيف محروق",
                 f"CTR {ctr:.2f}% مع {int(impr):,} ظهور",
                 "اختبر كريتيف جديد")

        prev_row = prev_idx.get((plat, camp))
        if prev_row is not None and cpm > 0:
            prev_cpm = float(prev_row.get("_CPM", 0) or 0)
            if prev_cpm > 0:
                chg = (cpm - prev_cpm) / prev_cpm
                if chg > 0.30:
                    _add("warning", "CPM", cpm, prev_cpm * 1.3,
                         "CPM ارتفع — منافسة أو audience ضيق",
                         f"CPM ارتفع {chg*100:.0f}% مقارنة بالفترة السابقة",
                         "راجع bidding أو وسّع الأوديانس")

        if target_cpa > 0 and cpa > 0 and target_cpa < cpa <= target_cpa * 1.5:
            _add("warning", "CPA", cpa, target_cpa,
                 "CPA قريب من الحد",
                 f"CPA {_fmt_sar(cpa)} — الهدف {_fmt_sar(target_cpa)}",
                 "راقب يومين")

        # ── Opportunity ───────────────────────────────────────────────────
        if target_mer > 0 and roas > target_mer * 1.5 and spend < 5_000:
            _add("opportunity", "ROAS", roas, target_mer * 1.5,
                 "أداء ممتاز — جاهز للـ scale",
                 f"ROAS {roas:.2f}× مع إنفاق منخفض {_fmt_sar(spend)}",
                 "ارفع الميزانية 20-30%")

        if ctr > 2:
            _add("opportunity", "CTR", ctr, 2.0,
                 "CTR مرتفع — وسّع الأوديانس",
                 f"CTR {ctr:.2f}% — الكريتيف يعمل بشكل ممتاز",
                 "Duplicate وزد الميزانية")

        if target_cpa > 0 and cpa > 0 and cpa < target_cpa * 0.7:
            _add("opportunity", "CPA", cpa, target_cpa * 0.7,
                 "CPA أقل من الهدف بـ 30%",
                 f"CPA {_fmt_sar(cpa)} — الهدف {_fmt_sar(target_cpa)} — هامش كافي للتوسع",
                 "ارفع الميزانية")

    return alerts


def _render_alert_card(alert: dict, color: str) -> None:
    plat     = alert["platform"]
    plat_dot = {"google": "🔵", "meta": "🟣", "snap": "🟡", "tiktok": "⚫"}.get(plat, "⚪")
    plat_lbl = _PLATFORM_LABELS.get(plat, plat.title() if plat else "—")
    plat_c   = _PLATFORM_COLORS.get(plat, "#888")
    metric   = alert["metric"]
    value    = alert["value"]
    thresh   = alert["threshold"]

    def _fmv(m, v):
        if m == "ROAS":      return f"{v:.2f}×"
        if m == "CTR":       return f"{v:.2f}%"
        if m == "Conversions": return str(int(v))
        return _fmt_sar(v)

    val_str = _fmv(metric, value)
    thr_str = _fmv(metric, thresh)

    st.markdown(
        f"<div style='border-left:4px solid {color};"
        f"background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);"
        f"border-left:4px solid {color};border-radius:0 10px 10px 0;"
        f"padding:14px 16px;margin-bottom:8px'>"
        # top row: title + action badge
        f"<div style='display:flex;justify-content:space-between;"
        f"align-items:flex-start;gap:12px'>"
        f"<div style='flex:1;min-width:0'>"
        f"<div style='font-size:13.5px;font-weight:700;color:#f0f6fc;margin-bottom:4px'>"
        f"{alert['title']}</div>"
        f"<div style='font-size:11.5px;color:rgba(255,255,255,0.5);margin-bottom:8px'>"
        f"{alert['description']}</div>"
        # badges row
        f"<div style='display:flex;gap:8px;align-items:center;flex-wrap:wrap'>"
        f"<span style='background:rgba(255,255,255,0.06);border-radius:6px;"
        f"padding:2px 9px;font-size:10.5px;color:rgba(255,255,255,0.45)'>"
        f"{alert['campaign_name'][:45]}</span>"
        f"<span style='background:{plat_c}22;border:1px solid {plat_c}55;"
        f"border-radius:6px;padding:2px 9px;font-size:10.5px;color:{plat_c}'>"
        f"{plat_dot} {plat_lbl}</span>"
        f"<span style='font-size:10.5px;color:rgba(255,255,255,0.35)'>"
        f"{metric}: <b style='color:{color}'>{val_str}</b>"
        f"<span style='color:rgba(255,255,255,0.2)'> / حد: {thr_str}</span>"
        f"</span>"
        f"</div>"
        f"</div>"
        # action badge
        f"<div style='background:{color}20;border:1px solid {color}50;"
        f"border-radius:8px;padding:7px 13px;font-size:11px;font-weight:600;"
        f"color:{color};white-space:nowrap;flex-shrink:0;align-self:center'>"
        f"↗ {alert['action']}"
        f"</div>"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_alerts_page(proj: dict, start: str, end: str,
                        fetch_google=None) -> None:
    pid        = proj["id"]
    target_cpa = float(proj.get("target_cpa", 0))
    target_mer = float(proj.get("target_mer", 0))

    # Compute previous period dates (same span, immediately before current)
    start_dt   = datetime.strptime(start, "%Y-%m-%d")
    end_dt     = datetime.strptime(end,   "%Y-%m-%d")
    days       = (end_dt - start_dt).days + 1
    prev_end   = (start_dt - timedelta(days=1)).strftime("%Y-%m-%d")
    prev_start = (start_dt - timedelta(days=days)).strftime("%Y-%m-%d")

    # ── Fetch campaign data (both periods) ────────────────────────────────────
    with st.spinner("جارٍ تحليل الحملات…"):
        df_curr = _fetch_ads_level1(proj, start,      end,      fetch_google)
        df_prev = _fetch_ads_level1(proj, prev_start, prev_end, fetch_google)

    alerts = generate_alerts(df_curr, df_prev, target_cpa, target_mer)

    # ── Summary cards ─────────────────────────────────────────────────────────
    n_crit = sum(1 for a in alerts if a["severity"] == "critical")
    n_warn = sum(1 for a in alerts if a["severity"] == "warning")
    n_opp  = sum(1 for a in alerts if a["severity"] == "opportunity")

    sc, sw, so = st.columns(3, gap="small")
    for col, label, count, color, icon in [
        (sc, "حرجة",         n_crit, "#f85149", "🔴"),
        (sw, "تحتاج مراجعة", n_warn, "#e3b341", "🟡"),
        (so, "فرص",          n_opp,  "#3fb950", "🟢"),
    ]:
        col.markdown(
            f"<div style='background:rgba(255,255,255,0.04);"
            f"border:1px solid rgba(255,255,255,0.08);"
            f"border-radius:10px;padding:16px 18px;text-align:center'>"
            f"<div style='font-size:30px;font-weight:900;color:{color}'>{count}</div>"
            f"<div style='font-size:11px;color:rgba(255,255,255,0.4);margin-top:4px'>"
            f"{icon} {label}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # ── Empty state ───────────────────────────────────────────────────────────
    if not alerts:
        st.markdown(
            "<div style='text-align:center;padding:60px 0'>"
            "<div style='font-size:44px'>✅</div>"
            "<div style='font-size:17px;color:rgba(255,255,255,0.5);margin-top:12px'>"
            "لا توجد تنبيهات حالياً</div>"
            "<div style='font-size:12px;color:rgba(255,255,255,0.25);margin-top:6px'>"
            "كل الحملات تعمل ضمن الحدود المقبولة</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    # ── Platform filter ───────────────────────────────────────────────────────
    sk_plat  = f"alt_plat_{pid}"
    cur_plat = st.session_state.get(sk_plat, "الكل")

    # Only show platforms that actually appear in the alerts
    alert_plats = list(dict.fromkeys(
        a["platform"] for a in alerts if a["platform"]
    ))
    plat_filter_keys = ["الكل"] + alert_plats

    pcols = st.columns([1.1] * len(plat_filter_keys) +
                       [max(0.1, 10 - 1.1 * len(plat_filter_keys))])
    for col, key in zip(pcols, plat_filter_keys):
        lbl = _PLAT_BTN_LABELS.get(key, key) if key != "الكل" else "الكل"
        if col.button(lbl, key=f"alt_pf_{key}_{pid}",
                      type="primary" if cur_plat == key else "secondary",
                      use_container_width=True):
            st.session_state[sk_plat] = key
            st.rerun()

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # Apply platform filter
    shown = [a for a in alerts
             if cur_plat == "الكل" or a["platform"] == cur_plat]

    # ── Alert sections (critical → warning → opportunity) ─────────────────────
    _SEV = [
        ("critical",    "🔴 حرجة — تحتاج تدخل فوري", "#f85149"),
        ("warning",     "🟡 تحتاج مراجعة",            "#e3b341"),
        ("opportunity", "🟢 فرص للتوسع",              "#3fb950"),
    ]
    for sev, sev_title, sev_color in _SEV:
        sev_alerts = [a for a in shown if a["severity"] == sev]
        if not sev_alerts:
            continue
        st.markdown(
            f"<div style='font-size:11.5px;font-weight:700;color:{sev_color};"
            f"text-transform:uppercase;letter-spacing:0.6px;margin:16px 0 8px'>"
            f"{sev_title} &nbsp;({len(sev_alerts)})</div>",
            unsafe_allow_html=True,
        )
        for alert in sev_alerts:
            _render_alert_card(alert, sev_color)


# ══════════════════════════════════════════════════════════════════════════════
# CREATIVE ANALYSIS PAGE
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_creative_analysis_data(
    proj: dict,
    start: str,
    end: str,
) -> pd.DataFrame:
    """
    Fetches ad-level data from all connected platforms.

    Session-state cached: results are stored in st.session_state keyed by
    (project_id, start, end) for 10 minutes. This makes navigation and
    filter changes effectively instant after first load.
    """
    pid       = proj.get("id", "")
    cache_key = f"_creative_cache_{pid}_{start}_{end}"
    cached    = st.session_state.get(cache_key)
    if cached:
        cached_at, df = cached
        if time.time() - cached_at < 600:   # 10 min TTL
            return df

    plat_cfg = proj.get("platforms", {})
    frames: list[pd.DataFrame] = []

    # ── Meta ──────────────────────────────────────────────────────────────────
    meta_acct = plat_cfg.get("meta", {}).get("ad_account_id", "").strip()
    if meta_acct:
        try:
            from meta_ads_server import fetch_meta_all_ads
            mtoken = os.getenv("META_ACCESS_TOKEN", "")
            if mtoken:
                mdf = fetch_meta_all_ads(mtoken, meta_acct, start, end)
                if not mdf.empty:
                    mdf = mdf.copy()
                    mdf["_Platform"] = "meta"
                    mdf["_Name"]     = mdf["Campaign"].fillna("")
                    mdf["_Status"]   = mdf["Status"].fillna("PAUSED")
                    mdf["_CPM"]      = mdf.get("CPM", 0).fillna(0)
                    frames.append(mdf)
        except Exception as _exc:
            logging.getLogger(__name__).debug('suppressed: %s', _exc)

    # ── Snap ──────────────────────────────────────────────────────────────────
    snap_acct = plat_cfg.get("snap", {}).get("ad_account_id", "").strip()
    if snap_acct:
        try:
            from snap_ads_server import fetch_snap_all_ads
            stoken = os.getenv("SNAP_ACCESS_TOKEN", "")
            if stoken:
                sdf = fetch_snap_all_ads(stoken, snap_acct, start, end)
                if not sdf.empty:
                    sdf = sdf.copy()
                    sdf["_Platform"] = "snap"
                    sdf["_Name"]     = sdf["Campaign"].fillna("")
                    sdf["_Status"]   = sdf["Status"].fillna("PAUSED")
                    # Vectorized CPM (much faster than apply on large DFs)
                    impr  = sdf["Impressions"].astype(float).fillna(0)
                    cost  = sdf["Cost"].astype(float).fillna(0)
                    cpm_v = (cost / impr * 1000).where(impr > 0, 0.0).round(2)
                    sdf["_CPM"]      = cpm_v
                    if "Frequency" not in sdf.columns:
                        sdf["Frequency"] = 0.0
                    if "Reach" not in sdf.columns:
                        sdf["Reach"] = 0
                    frames.append(sdf)
        except Exception as _exc:
            logging.getLogger(__name__).debug('suppressed: %s', _exc)

    if not frames:
        result = pd.DataFrame()
        st.session_state[cache_key] = (time.time(), result)
        return result

    combined = pd.concat(frames, ignore_index=True)

    # Ensure all required columns exist with safe defaults
    for col, default in [
        ("thumbnail_url", ""), ("Campaign Name", ""), ("Ad Set Name", ""),
        ("Ad Set ID", ""), ("Reach", 0), ("Frequency", 0.0),
        ("CPM", 0.0), ("Avg CPC", 0.0), ("_CPM", 0.0),
    ]:
        if col not in combined.columns:
            combined[col] = default

    combined["_CPM"]          = combined["_CPM"].fillna(0)
    combined["_Status"]       = combined["_Status"].fillna("PAUSED")
    combined["thumbnail_url"] = combined["thumbnail_url"].fillna("")

    st.session_state[cache_key] = (time.time(), combined)
    return combined


def _metric_chip(label: str, value: str, color: str) -> str:
    """Returns HTML for a small colored metric chip."""
    return (
        f"<div style='display:flex;flex-direction:column;align-items:center;"
        f"min-width:56px'>"
        f"<span style='font-size:10px;color:{color};font-weight:700'>{value}</span>"
        f"<span style='font-size:9px;color:rgba(255,255,255,0.38);margin-top:1px'>{label}</span>"
        f"</div>"
    )


def _render_creative_card(
    rank: int,
    row: pd.Series,
    is_selected: bool,
    key: str,
    target_mer: float,
    target_cpa: float,
) -> bool:
    """
    Renders a single ad creative card inside a st.column.
    Returns True if the card was clicked this run.
    """
    name       = str(row.get("_Name", row.get("Campaign", "")))
    platform   = str(row.get("_Platform", "meta"))
    thumb      = str(row.get("thumbnail_url", ""))
    status     = str(row.get("_Status", "ENABLED"))
    spend      = float(row.get("Cost", 0))
    roas_val   = float(row.get("ROAS", 0))
    cpa_val    = float(row.get("CPA", 0))
    ctr_val    = float(row.get("CTR", 0))

    # Colours
    dot_c   = _PLATFORM_COLORS.get(platform, "#888")
    plat_lbl = {"meta": "Meta", "snap": "Snap", "google": "Google", "tiktok": "TikTok"}.get(platform, platform.title())
    sel_border = "2px solid #58a6ff" if is_selected else "1px solid rgba(255,255,255,0.08)"
    sel_bg     = "rgba(88,166,255,0.06)" if is_selected else "rgba(255,255,255,0.02)"
    trophy     = "🏆 " if rank == 1 else ""

    # ROAS color
    if target_mer and roas_val >= target_mer:
        roas_c = "#3fb950"
    elif target_mer and roas_val >= target_mer * 0.8:
        roas_c = "#e3b341"
    else:
        roas_c = "#f85149" if roas_val < 1 else "#e3b341"

    # CPA color
    if target_cpa and cpa_val > 0:
        cpa_c = "#3fb950" if cpa_val <= target_cpa else ("#e3b341" if cpa_val <= target_cpa * 1.5 else "#f85149")
    else:
        cpa_c = "#f0f6fc"

    # CTR color
    ctr_c = "#3fb950" if ctr_val >= 2 else ("#e3b341" if ctr_val >= 0.5 else "#f85149")

    # Status badge
    if status in ("ENABLED", "ACTIVE"):
        stat_html = ("<span style='font-size:9px;background:rgba(63,185,80,0.15);"
                     "color:#3fb950;border:1px solid rgba(63,185,80,0.3);"
                     "border-radius:4px;padding:1px 6px'>شغال</span>")
    else:
        stat_html = ("<span style='font-size:9px;background:rgba(255,255,255,0.06);"
                     "color:rgba(255,255,255,0.4);border:1px solid rgba(255,255,255,0.1);"
                     "border-radius:4px;padding:1px 6px'>موقف</span>")

    # Platform badge
    plat_badge = (
        f"<span style='font-size:9px;background:rgba(255,255,255,0.06);"
        f"color:{dot_c};border:1px solid {dot_c}33;"
        f"border-radius:4px;padding:1px 6px'>{plat_lbl}</span>"
    )

    # Rank chip
    rank_html = (
        f"<div style='position:absolute;top:8px;left:8px;background:rgba(0,0,0,0.65);"
        f"color:#f0f6fc;font-size:10px;font-weight:700;border-radius:5px;"
        f"padding:2px 7px;backdrop-filter:blur(4px)'>{trophy}#{rank}</div>"
    )

    # Image / placeholder
    if thumb:
        img_html = (
            f"<img src='{thumb}' style='width:100%;height:160px;"
            f"object-fit:cover;border-radius:8px 8px 0 0;display:block' "
            f"onerror=\"this.style.display='none';this.nextSibling.style.display='flex'\">"
            f"<div style='display:none;width:100%;height:160px;border-radius:8px 8px 0 0;"
            f"background:linear-gradient(135deg,{dot_c}22,{dot_c}08);align-items:center;"
            f"justify-content:center;font-size:28px'>🖼️</div>"
        )
    else:
        img_html = (
            f"<div style='width:100%;height:160px;border-radius:8px 8px 0 0;"
            f"background:linear-gradient(135deg,{dot_c}33,{dot_c}0a);"
            f"display:flex;align-items:center;justify-content:center;"
            f"flex-direction:column;gap:6px'>"
            f"<span style='font-size:26px;opacity:0.5'>"
            f"{'🔵' if platform=='google' else '🟡' if platform=='snap' else '🎨'}</span>"
            f"<span style='font-size:10px;color:{dot_c};opacity:0.7'>{plat_lbl}</span>"
            f"</div>"
        )

    metrics_html = (
        f"<div style='display:flex;justify-content:space-around;margin-top:10px;padding:0 4px'>"
        + _metric_chip("CPA",  _fmt_sar(cpa_val) if cpa_val else "—",    cpa_c)
        + _metric_chip("CTR",  _fmt_pct(ctr_val),                         ctr_c)
        + _metric_chip("ROAS", f"{roas_val:.2f}×",                        roas_c)
        + "</div>"
    )

    card_html = (
        f"<div style='border:{sel_border};border-radius:10px;overflow:hidden;"
        f"background:{sel_bg};transition:all 0.15s;cursor:pointer;position:relative'>"
        f"<div style='position:relative'>"
        f"{img_html}"
        f"{rank_html}"
        f"<div style='position:absolute;top:8px;right:8px;display:flex;flex-direction:column;"
        f"gap:4px;align-items:flex-end'>{stat_html}<br style='line-height:2px'>{plat_badge}</div>"
        f"</div>"
        f"<div style='padding:10px 10px 4px'>"
        f"<div style='font-size:12px;font-weight:600;color:#f0f6fc;white-space:nowrap;"
        f"overflow:hidden;text-overflow:ellipsis' title='{name}'>{name[:48]}</div>"
        f"<div style='font-size:11px;color:rgba(255,255,255,0.38);margin-top:2px'>"
        f"{_fmt_sar(spend)}</div>"
        f"{metrics_html}"
        f"</div></div>"
    )

    st.markdown(card_html, unsafe_allow_html=True)
    # Clearly labeled click button — full width below card
    btn_label = "🔽 إخفاء التفاصيل" if is_selected else "🔍 عرض التفاصيل"
    clicked = st.button(
        btn_label,
        key=key,
        use_container_width=True,
        type="primary" if is_selected else "secondary",
    )
    return clicked


def _render_creative_detail(row: pd.Series, target_mer: float, target_cpa: float) -> None:
    """Full-width detail panel shown below the grid when a card is selected."""
    name        = str(row.get("_Name", row.get("Campaign", "")))
    platform    = str(row.get("_Platform", "meta"))
    thumb       = str(row.get("thumbnail_url", ""))
    ad_id       = str(row.get("ID", ""))
    camp_name   = str(row.get("Campaign Name", ""))
    adset_name  = str(row.get("Ad Set Name", ""))
    spend       = float(row.get("Cost", 0))
    rev         = float(row.get("Conv. Value", 0))
    roas_val    = float(row.get("ROAS", 0))
    orders      = float(row.get("Conversions", 0))
    cpa_val     = float(row.get("CPA", 0))
    ctr_val     = float(row.get("CTR", 0))
    cpm_val     = float(row.get("_CPM", row.get("CPM", 0)))
    cpc_val     = float(row.get("Avg CPC", 0))
    freq_val    = float(row.get("Frequency", 0))
    impressions = int(row.get("Impressions", 0))
    note        = _ai_note(spend, roas_val, cpa_val, ctr_val, target_mer, target_cpa)
    dot_c       = _PLATFORM_COLORS.get(platform, "#888")

    st.markdown(
        "<div style='height:1px;background:rgba(88,166,255,0.3);margin:16px 0 20px'></div>",
        unsafe_allow_html=True,
    )

    col_img, col_info = st.columns([1, 2], gap="large")

    with col_img:
        if thumb:
            st.markdown(
                f"<img src='{thumb}' style='width:100%;border-radius:12px;"
                f"border:1px solid rgba(255,255,255,0.1)' "
                f"onerror=\"this.style.display='none'\">",
                unsafe_allow_html=True,
            )
        else:
            plat_lbl = {"meta": "Meta", "snap": "Snap", "google": "Google"}.get(platform, platform.title())
            st.markdown(
                f"<div style='width:100%;aspect-ratio:1;border-radius:12px;"
                f"border:1px solid rgba(255,255,255,0.1);"
                f"background:linear-gradient(135deg,{dot_c}33,{dot_c}0a);"
                f"display:flex;align-items:center;justify-content:center;"
                f"flex-direction:column;gap:10px'>"
                f"<span style='font-size:42px;opacity:0.5'>🎨</span>"
                f"<span style='font-size:13px;color:{dot_c};opacity:0.7'>{plat_lbl} — لا تتوفر صورة</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    with col_info:
        st.markdown(
            f"<div style='font-size:18px;font-weight:700;color:#f0f6fc;margin-bottom:4px'>"
            f"{name}</div>",
            unsafe_allow_html=True,
        )
        if camp_name:
            st.markdown(
                f"<div style='font-size:12px;color:rgba(255,255,255,0.45);margin-bottom:2px'>"
                f"📋 {camp_name}</div>",
                unsafe_allow_html=True,
            )
        if adset_name:
            st.markdown(
                f"<div style='font-size:12px;color:rgba(255,255,255,0.45);margin-bottom:14px'>"
                f"📦 {adset_name}</div>",
                unsafe_allow_html=True,
            )

        # Metrics grid
        def _det_cell(lbl, val, col="rgba(255,255,255,0.85)"):
            return (
                f"<div style='background:rgba(255,255,255,0.04);border:1px solid "
                f"rgba(255,255,255,0.07);border-radius:8px;padding:10px 14px;text-align:center'>"
                f"<div style='font-size:9.5px;color:rgba(255,255,255,0.35);"
                f"text-transform:uppercase;letter-spacing:1px;margin-bottom:4px'>{lbl}</div>"
                f"<div style='font-size:15px;font-weight:700;color:{col}'>{val}</div>"
                f"</div>"
            )

        if target_mer and roas_val >= target_mer:
            roas_c = "#3fb950"
        elif target_mer and roas_val >= target_mer * 0.8:
            roas_c = "#e3b341"
        else:
            roas_c = "#f85149" if roas_val < 1 else "#e3b341"

        cpa_c = "#f0f6fc"
        if target_cpa and cpa_val > 0:
            cpa_c = "#3fb950" if cpa_val <= target_cpa else ("#e3b341" if cpa_val <= target_cpa * 1.5 else "#f85149")
        ctr_c = "#3fb950" if ctr_val >= 2 else ("#e3b341" if ctr_val >= 0.5 else "#f85149")

        cells = (
            _det_cell("الإنفاق",  _fmt_sar(spend))
            + _det_cell("الإيراد", _fmt_sar(rev))
            + _det_cell("ROAS",   f"{roas_val:.2f}×", roas_c)
            + _det_cell("الطلبات", _fmt_num(orders))
            + _det_cell("CPA",    _fmt_sar(cpa_val) if cpa_val else "—", cpa_c)
            + _det_cell("CTR",    _fmt_pct(ctr_val), ctr_c)
            + _det_cell("CPM",    _fmt_sar(cpm_val) if cpm_val else "—")
            + _det_cell("CPC",    _fmt_sar(cpc_val) if cpc_val else "—")
            + _det_cell("التردد", f"{freq_val:.2f}" if freq_val else "—")
            + _det_cell("الوصول", _fmt_num(impressions))
        )
        st.markdown(
            f"<div style='display:grid;grid-template-columns:repeat(5,1fr);gap:8px'>"
            f"{cells}</div>",
            unsafe_allow_html=True,
        )

        # AI note
        st.markdown(
            f"<div style='margin-top:14px;background:rgba(255,255,255,0.04);"
            f"border:1px solid rgba(255,255,255,0.07);border-radius:8px;padding:10px 14px;"
            f"font-size:13px;color:#f0f6fc'>🤖 {note}</div>",
            unsafe_allow_html=True,
        )

        # Action buttons
        b1, b2, _ = st.columns([1, 1, 3])
        if platform == "meta" and ad_id:
            meta_url = f"https://adsmanager.facebook.com/adsmanager/manage/ads?selected_ad_ids={ad_id}"
            b1.link_button("🔗 فتح في Meta", meta_url, use_container_width=True)
        if thumb:
            b2.link_button("🖼️ عرض الكريتيف", thumb, use_container_width=True)

    st.markdown(
        "<div style='height:1px;background:rgba(255,255,255,0.06);margin:20px 0 10px'></div>",
        unsafe_allow_html=True,
    )


def _render_creative_analysis(
    proj: dict,
    start: str,
    end: str,
    fetch_google=None,
    fetch_google_ads=None,
) -> None:
    pid        = proj["id"]
    target_mer = float(proj.get("target_mer", 0))
    target_cpa = float(proj.get("target_cpa", 0))

    # ── Header with refresh button ───────────────────────────────────────────
    hc1, hc2 = st.columns([8, 1])
    with hc2:
        if st.button("🔄 تحديث", key=f"ca_refresh_{pid}", use_container_width=True,
                     help="إعادة تحميل البيانات من المنصات"):
            # Clear all caches related to this project
            for k in list(st.session_state.keys()):
                if k.startswith(f"_creative_cache_{pid}_") or k.startswith(f"_agg_cache_{pid}_"):
                    del st.session_state[k]
            try:
                from meta_ads_server import fetch_meta_all_ads
                fetch_meta_all_ads.clear()
            except Exception as _exc:
                logging.getLogger(__name__).debug('suppressed: %s', _exc)
            try:
                from snap_ads_server import fetch_snap_all_ads
                fetch_snap_all_ads.clear()
            except Exception as _exc:
                logging.getLogger(__name__).debug('suppressed: %s', _exc)
            st.rerun()

    # ── Fetch data ────────────────────────────────────────────────────────────
    with st.spinner("جارٍ تحميل الإعلانات…"):
        df = _fetch_creative_analysis_data(proj, start, end)

    if df.empty:
        st.info("لا توجد بيانات إعلانية لهذه الفترة. تأكد من ربط Meta أو Snap.")
        return

    active_plats = [p for p in ("meta", "snap", "google", "tiktok")
                    if p in df["_Platform"].values]

    # ── FILTERS — native Streamlit widgets (auto-rerun, no manual st.rerun) ──
    _PLAT_LABELS_MAP = {"الكل": "🌐 الكل", **{
        p: _PLAT_BTN_LABELS[p] for p in active_plats
    }}
    platf_keys = ["الكل"] + active_plats

    fc1, fc2, fc3 = st.columns([4, 3, 2])
    with fc1:
        cur_platf = st.radio(
            "المنصة", options=platf_keys,
            format_func=lambda k: _PLAT_LABELS_MAP.get(k, k),
            horizontal=True,
            key=f"ca_platf_{pid}",
            label_visibility="collapsed",
        )
    with fc2:
        _sort_opts = {"ROAS ↓": "ROAS", "CPA ↑": "CPA", "CTR ↓": "CTR", "الإنفاق ↓": "Cost"}
        cur_sort_label = st.radio(
            "الترتيب", options=list(_sort_opts.keys()),
            horizontal=True,
            key=f"ca_sort_{pid}",
            label_visibility="collapsed",
        )
        sort_col = _sort_opts[cur_sort_label]
    with fc3:
        cur_status = st.radio(
            "الحالة", options=["شغالة", "الكل"],
            horizontal=True,
            key=f"ca_sts_{pid}",
            label_visibility="collapsed",
        )

    # ── Apply filters ─────────────────────────────────────────────────────────
    dff = df.copy()
    if cur_platf != "الكل":
        dff = dff[dff["_Platform"] == cur_platf]
    if cur_status == "شغالة":
        dff = dff[dff["_Status"].isin(["ENABLED", "ACTIVE"])]

    dff = dff.sort_values(
        sort_col, ascending=(sort_col == "CPA"), na_position="last"
    ).reset_index(drop=True)

    if dff.empty:
        st.info("لا توجد إعلانات تطابق الفلتر المحدد.")
        return

    # ── Summary bar ───────────────────────────────────────────────────────────
    total_ads = len(dff)
    best_roas = float(dff["ROAS"].max()) if "ROAS" in dff.columns else 0.0
    avg_ctr   = float(dff["CTR"].mean())  if "CTR"  in dff.columns else 0.0
    valid_cpa = dff[dff["CPA"] > 0]["CPA"] if "CPA" in dff.columns else pd.Series([], dtype=float)
    avg_cpa   = float(valid_cpa.mean()) if not valid_cpa.empty else 0.0

    _ks  = ("background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.07);"
            "border-radius:10px;padding:12px 16px;text-align:center")
    _ls  = "font-size:9.5px;color:rgba(255,255,255,0.35);text-transform:uppercase;letter-spacing:1px"
    _vs  = "font-size:20px;font-weight:700;color:#f0f6fc;margin:4px 0 2px"

    sb1, sb2, sb3, sb4 = st.columns(4, gap="small")
    sb1.markdown(
        f"<div style='{_ks}'><div style='{_ls}'>إجمالي الإعلانات</div>"
        f"<div style='{_vs}'>{total_ads}</div></div>", unsafe_allow_html=True)
    sb2.markdown(
        f"<div style='{_ks}'><div style='{_ls}'>أفضل ROAS</div>"
        f"<div style='{_vs}'>{best_roas:.2f}×</div></div>", unsafe_allow_html=True)
    sb3.markdown(
        f"<div style='{_ks}'><div style='{_ls}'>متوسط CTR</div>"
        f"<div style='{_vs}'>{_fmt_pct(avg_ctr)}</div></div>", unsafe_allow_html=True)
    sb4.markdown(
        f"<div style='{_ks}'><div style='{_ls}'>متوسط CPA</div>"
        f"<div style='{_vs}'>{_fmt_sar(avg_cpa) if avg_cpa else '—'}</div></div>",
        unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Session state for selected card (only card clicks need manual state) ──
    sk_selected = f"ca_sel_{pid}"
    sk_page     = f"ca_page_{pid}"
    selected_key = st.session_state.get(sk_selected, None)

    # Reset page if filter changed (previous page may be out of bounds)
    PAGE_SIZE   = 24
    total       = len(dff)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    cur_page    = st.session_state.get(sk_page, 0)
    if cur_page >= total_pages:
        cur_page = 0
        st.session_state[sk_page] = 0

    # Page info
    start_i = cur_page * PAGE_SIZE + 1
    end_i   = min((cur_page + 1) * PAGE_SIZE, total)
    if total > PAGE_SIZE:
        st.markdown(
            f"<div style='font-size:11px;color:rgba(255,255,255,0.35);margin-bottom:8px'>"
            f"عرض {start_i}–{end_i} من {total} إعلان</div>",
            unsafe_allow_html=True,
        )

    page_df = dff.iloc[cur_page * PAGE_SIZE: (cur_page + 1) * PAGE_SIZE]

    # ── Card grid ─────────────────────────────────────────────────────────────
    _DESELECT     = "__deselect__"
    COLS          = 4
    next_selected = selected_key   # changes only when a card is clicked

    for row_start in range(0, len(page_df), COLS):
        row_slice = page_df.iloc[row_start: row_start + COLS]
        grid_cols = st.columns(COLS, gap="small")
        for col_idx, (df_idx, row_data) in enumerate(row_slice.iterrows()):
            rank     = df_idx + 1
            uid      = f"{row_data.get('_Platform','x')}__{row_data.get('ID', str(df_idx))}"
            card_key = f"ca_card_{uid}_{pid}"
            is_sel   = (selected_key == uid)
            with grid_cols[col_idx]:
                was_clicked = _render_creative_card(
                    rank, row_data, is_sel, card_key, target_mer, target_cpa
                )
            if was_clicked:
                next_selected = _DESELECT if is_sel else uid

    # ── Pagination buttons ────────────────────────────────────────────────────
    if total_pages > 1:
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        pg1, pg2, pg3 = st.columns([1, 2, 1])
        with pg1:
            if cur_page > 0 and st.button("← السابق", key=f"ca_prev_{pid}",
                                           use_container_width=True):
                st.session_state[sk_page]     = cur_page - 1
                st.session_state[sk_selected] = None
                st.rerun()
        with pg2:
            st.markdown(
                f"<div style='text-align:center;font-size:12px;"
                f"color:rgba(255,255,255,0.4);padding-top:8px'>"
                f"صفحة {cur_page + 1} / {total_pages}</div>",
                unsafe_allow_html=True,
            )
        with pg3:
            if cur_page < total_pages - 1 and st.button("التالي →", key=f"ca_next_{pid}",
                                                          use_container_width=True):
                st.session_state[sk_page]     = cur_page + 1
                st.session_state[sk_selected] = None
                st.rerun()

    # ── Apply card-click result (only reruns for card clicks, not filters) ────
    if next_selected == _DESELECT:
        st.session_state[sk_selected] = None
        st.rerun()
    elif next_selected != selected_key:
        st.session_state[sk_selected] = next_selected
        st.rerun()

    # ── Detail panel ──────────────────────────────────────────────────────────
    selected_key = st.session_state.get(sk_selected)
    if selected_key:
        plat_part, id_part = (selected_key.split("__", 1) + [""])[:2]
        mask = (dff["_Platform"] == plat_part) & (dff["ID"].astype(str) == id_part)
        sel_rows = dff[mask]
        if not sel_rows.empty:
            _render_creative_detail(sel_rows.iloc[0], target_mer, target_cpa)


def _render_coming_soon(label: str) -> None:
    st.markdown(
        f"<div style='display:flex;flex-direction:column;align-items:center;"
        f"justify-content:center;height:320px;color:rgba(255,255,255,0.2)'>"
        f"<div style='font-size:52px;margin-bottom:18px'>🚧</div>"
        f"<div style='font-size:20px;font-weight:700;color:rgba(255,255,255,0.35)'>{label}</div>"
        f"<div style='font-size:13px;margin-top:8px'>قريباً</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _fetch_one_platform(plat: str, proj: dict,
                        start: str, end: str,
                        prev_start: str, prev_end: str,
                        fetch_google, fetch_google_daily) -> tuple[str, dict]:
    """Single-platform fetch worker — safe to run in a thread (no st.* calls)."""
    t0 = time.perf_counter()
    try:
        df, err = _fetch_platform_df(plat, proj, start, end, fetch_google)
    except Exception as exc:
        df, err = pd.DataFrame(), str(exc)[:120]
    try:
        df_prev, _ = _fetch_platform_df(plat, proj, prev_start, prev_end, fetch_google)
    except Exception:
        df_prev = pd.DataFrame()
    try:
        daily = _fetch_daily_df(plat, proj, start, end, fetch_google_daily)
    except Exception:
        daily = pd.DataFrame()

    elapsed = time.perf_counter() - t0
    print(f"[perf] {plat:8s} fetch: {elapsed:.2f}s  "
          f"(curr={len(df)} rows, prev={len(df_prev)} rows, daily={len(daily)} rows)")
    return plat, {
        "s":      _summarise(df),
        "s_prev": _summarise(df_prev),
        "daily":  daily,
        "err":    err,
        "empty":  df.empty,
    }


def _fetch_and_aggregate(proj: dict, start: str, end: str,
                         fetch_google=None, fetch_google_daily=None,
                         fetch_google_adgroups=None, fetch_google_ads=None):
    """
    Fetch current + previous period for all connected platforms IN PARALLEL.
    Returns (platform_results, curr, prev, daily_agg) or None if no data.

    Session-state cached for 5 min: navigating between tabs (overview/daily/etc.)
    won't refetch.
    """
    pid       = proj.get("id", "")
    cache_key = f"_agg_cache_{pid}_{start}_{end}"
    cached    = st.session_state.get(cache_key)
    if cached:
        cached_at, data = cached
        if time.time() - cached_at < 300:   # 5 min TTL
            return data

    plat_cfg  = proj.get("platforms", {})
    start_dt  = datetime.strptime(start, "%Y-%m-%d")
    end_dt    = datetime.strptime(end,   "%Y-%m-%d")
    days      = (end_dt - start_dt).days + 1
    prev_end  = (start_dt - timedelta(days=1)).strftime("%Y-%m-%d")
    prev_start = (start_dt - timedelta(days=days)).strftime("%Y-%m-%d")

    # Identify platforms that have at least one account ID configured
    active_plats = [
        plat for plat in ["google", "meta", "snap", "tiktok"]
        if any(str(v).strip()
               for v in (plat_cfg.get(plat, {}).values()
                         if isinstance(plat_cfg.get(plat, {}), dict) else []))
    ]
    if not active_plats:
        return None

    t_wall = time.perf_counter()

    # Fetch all platforms in parallel — each platform's 3 API calls run in its own thread
    platform_results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=len(active_plats)) as executor:
        futures = {
            executor.submit(
                _fetch_one_platform,
                plat, proj, start, end, prev_start, prev_end,
                fetch_google, fetch_google_daily,
            ): plat
            for plat in active_plats
        }
        for future in as_completed(futures):
            plat_name = futures[future]
            try:
                plat_key, result = future.result(timeout=60)
                platform_results[plat_key] = result
            except Exception as e:
                logging.getLogger(__name__).warning(
                    "platform fetch failed for %s: %s", plat_name, e)
                # Skip this platform's results — the rest still load.

    wall_elapsed = time.perf_counter() - t_wall
    print(f"[perf] total wall time ({len(active_plats)} platforms parallel): {wall_elapsed:.2f}s")

    if not platform_results:
        return None

    curr = _agg_totals(platform_results)
    prev = {k: sum(r["s_prev"].get(k, 0) for r in platform_results.values())
            for k in ("spend", "revenue", "conversions", "impressions", "clicks")}
    prev["roas"] = prev["revenue"] / prev["spend"]              if prev["spend"]         else 0.0
    prev["cpa"]  = prev["spend"]   / prev["conversions"]        if prev["conversions"]   else 0.0
    prev["ctr"]  = prev["clicks"]  / prev["impressions"] * 100  if prev["impressions"]   else 0.0
    prev["aov"]  = prev["revenue"] / prev["conversions"]        if prev["conversions"]   else 0.0
    prev["cvr"]  = prev["conversions"] / prev["clicks"] * 100   if prev["clicks"]        else 0.0
    prev["mer"]  = prev["revenue"] / prev["spend"]              if prev["spend"]         else 0.0

    result = (platform_results, curr, prev, _aggregate_daily(platform_results))
    st.session_state[cache_key] = (time.time(), result)
    return result


# ── project detail view ───────────────────────────────────────────────────────

def _render_project_detail(proj: dict, start: str, end: str,
                           fetch_google=None, fetch_google_daily=None,
                           fetch_google_adgroups=None, fetch_google_ads=None):
    # Reset nav state when switching to a different project
    if st.session_state.get("_proj_detail_id") != proj["id"]:
        st.session_state["_proj_detail_id"] = proj["id"]
        st.session_state.pop("proj_nav_radio", None)

    target_cpa = float(proj.get("target_cpa", 0))
    target_mer = float(proj.get("target_mer", 0))

    active_section = _NAV_KEYS.get(
        st.session_state.get("proj_nav_radio", "📊 نظرة عامة"), "overview"
    )

    if active_section in ("overview", "daily"):
        result = _fetch_and_aggregate(proj, start, end, fetch_google, fetch_google_daily)
        if result is None:
            st.info("No connected platforms with data for this date range.")
            return
        platform_results, curr, prev, daily_agg = result

        if active_section == "overview":
            _render_top_cards(curr, prev)
            _section_label("Performance Metrics")
            _render_metric_grid(curr, prev, target_mer, target_cpa)
            _section_label("Daily Trend")
            _render_daily_chart(daily_agg)
            _section_label("Platform Breakdown")
            _render_platform_table(platform_results, curr, target_mer)
            if target_mer > 0:
                lo = target_mer * 0.8
                st.markdown(
                    f"<div style='margin-top:8px;font-size:11px;color:rgba(255,255,255,0.3)'>"
                    f"<span style='color:#3fb950'>●</span> ROAS &ge; {target_mer:.1f}&times; &nbsp;"
                    f"<span style='color:#e3b341'>●</span> &ge; {lo:.1f}&times; &nbsp;"
                    f"<span style='color:#f85149'>●</span> &lt; {lo:.1f}&times;</div>",
                    unsafe_allow_html=True,
                )

        elif active_section == "daily":
            _section_label("السجل اليومي")
            _render_daily_table(daily_agg, platform_results=platform_results)

    elif active_section == "ads":
        _render_ads_performance(
            proj, start, end,
            fetch_google=fetch_google,
            fetch_google_adgroups=fetch_google_adgroups,
            fetch_google_ads=fetch_google_ads,
        )

    elif active_section == "creative":
        _render_creative_analysis(
            proj, start, end,
            fetch_google=fetch_google,
            fetch_google_ads=fetch_google_ads,
        )

    elif active_section == "alerts":
        _render_alerts_page(
            proj, start, end,
            fetch_google=fetch_google,
        )


# ── card grid ─────────────────────────────────────────────────────────────────

def _render_cards(projects: list[dict]):
    cols = st.columns(3, gap="medium")
    for i, proj in enumerate(projects):
        plat_cfg   = proj.get("platforms", {})
        target_cpa = proj.get("target_cpa", 0)
        target_mer = proj.get("target_mer", 0)
        dots = _platform_dots(plat_cfg)

        with cols[i % 3]:
            btn_key = f"proj_card_{proj['id']}"
            st.markdown(
                f"<div style='background:rgba(255,255,255,0.04);"
                f"border:1px solid rgba(255,255,255,0.08);border-radius:14px;"
                f"padding:18px 20px 14px;margin-bottom:4px'>"
                f"<div style='font-size:17px;font-weight:700;color:#f0f6fc;margin-bottom:10px'>"
                f"{proj['name']}</div>"
                f"<div style='margin-bottom:12px'>{dots}</div>"
                f"<div style='display:flex;gap:24px'>"
                f"<div><div style='font-size:9.5px;color:rgba(255,255,255,0.35);"
                f"text-transform:uppercase;letter-spacing:0.8px'>Target CPA</div>"
                f"<div style='font-size:14px;font-weight:600;color:#58a6ff'>"
                f"{_fmt_sar(target_cpa) if target_cpa else '—'}</div></div>"
                f"<div><div style='font-size:9.5px;color:rgba(255,255,255,0.35);"
                f"text-transform:uppercase;letter-spacing:0.8px'>Target MER</div>"
                f"<div style='font-size:14px;font-weight:600;color:#58a6ff'>"
                f"{f'{target_mer:.1f}×' if target_mer else '—'}</div></div>"
                f"</div></div>",
                unsafe_allow_html=True,
            )
            if st.button("Open →", key=btn_key, use_container_width=True):
                st.session_state["selected_project_id"] = proj["id"]
                st.session_state["selected_project_name"] = proj["name"]
                st.session_state["selected_project_platforms"] = proj.get("platforms", {})
                st.rerun()


# ── main entry point ──────────────────────────────────────────────────────────

def render_projects_page(start: str, end: str,
                         fetch_google=None, fetch_google_daily=None,
                         fetch_google_adgroups=None, fetch_google_ads=None):
    projects = load_projects()

    sel_id = st.session_state.get("selected_project_id")
    if sel_id:
        proj = next((p for p in projects if p["id"] == sel_id), None)
        if proj:
            _render_project_detail(proj, start, end,
                                   fetch_google=fetch_google,
                                   fetch_google_daily=fetch_google_daily,
                                   fetch_google_adgroups=fetch_google_adgroups,
                                   fetch_google_ads=fetch_google_ads)
            return
        st.session_state.pop("selected_project_id", None)

    hcol, bcol = st.columns([4, 1])
    with hcol:
        st.markdown(
            "<div style='padding:8px 0 4px'>"
            "<div style='font-size:26px;font-weight:900;color:#f0f6fc;letter-spacing:-1px'>Projects</div>"
            "<div style='font-size:13px;color:rgba(255,255,255,0.28);margin-top:5px'>"
            "Cross-platform overview per client</div></div>",
            unsafe_allow_html=True,
        )
    with bcol:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if st.button("＋  New project", type="primary", use_container_width=True):
            _new_project_dialog()

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    if not projects:
        st.info("No projects yet. Click **＋ New project** to create one.")
        return

    _render_cards(projects)
