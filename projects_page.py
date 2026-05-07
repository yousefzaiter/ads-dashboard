import json
import os
import uuid
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

_CLIENTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clients.json")

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
            from token_manager import check_token_info
            token = os.getenv("META_ACCESS_TOKEN", "")
            if not token:
                return pd.DataFrame(), "No META_ACCESS_TOKEN in .env"
            if not check_token_info(token).get("is_valid"):
                return pd.DataFrame(), "Token expired — update META_ACCESS_TOKEN in .env"
            return fetch_meta_campaigns(token, acct, start, end), None
        except Exception as e:
            err = str(e)
            if "Session has expired" in err or "190" in err:
                return pd.DataFrame(), "Token expired — update META_ACCESS_TOKEN in .env"
            return pd.DataFrame(), err[:120]

    if platform == "snap":
        acct = plat.get("ad_account_id", "").strip()
        if not acct:
            return pd.DataFrame(), None
        try:
            from snap_ads_server import fetch_snap_campaigns
            token = os.getenv("SNAP_ACCESS_TOKEN", "")
            if not token:
                return pd.DataFrame(), "No SNAP_ACCESS_TOKEN"
            return fetch_snap_campaigns(token, acct, start, end), None
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
            return fetch_snap_daily(token, acct, start, end)
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


def _render_daily_table(daily: pd.DataFrame) -> None:
    if daily.empty:
        st.info("No daily data.")
        return

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

        def _tc(v, extra=""):
            return (f"<td style='padding:8px 12px;text-align:right;font-family:monospace;"
                    f"font-size:12px;color:#f0f6fc{extra}'>{v}</td>")
        def _td(v):
            return (f"<td style='padding:8px 12px;text-align:right;font-family:monospace;"
                    f"font-size:12px;color:rgba(255,255,255,0.55)'>{v}</td>")

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


# ── project detail view ───────────────────────────────────────────────────────

def _render_project_detail(proj: dict, start: str, end: str,
                           fetch_google=None, fetch_google_daily=None):
    # nav row
    back_col, edit_col, _ = st.columns([2, 2, 6])
    with back_col:
        if st.button("← Back", key="proj_back"):
            st.session_state.pop("selected_project_id", None)
            st.rerun()
    with edit_col:
        if st.button("✏️  Edit", key="proj_edit"):
            _edit_project_dialog(proj)

    plat_cfg   = proj.get("platforms", {})
    target_cpa = float(proj.get("target_cpa", 0))
    target_mer = float(proj.get("target_mer", 0))

    # previous period dates
    start_dt   = datetime.strptime(start, "%Y-%m-%d")
    end_dt     = datetime.strptime(end,   "%Y-%m-%d")
    days       = (end_dt - start_dt).days + 1
    prev_end   = (start_dt - timedelta(days=1)).strftime("%Y-%m-%d")
    prev_start = (start_dt - timedelta(days=days)).strftime("%Y-%m-%d")

    st.markdown(
        f"<div style='margin:8px 0 20px'>"
        f"<div style='font-size:28px;font-weight:900;color:#f0f6fc;letter-spacing:-1px'>{proj['name']}</div>"
        f"<div style='font-size:12px;color:rgba(255,255,255,0.35);margin-top:6px'>"
        f"{_platform_dots(plat_cfg)} &nbsp;Cross-platform &middot; {start} &rarr; {end}"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    # ── fetch all platform data ────────────────────────────────────────────
    platform_results: dict[str, dict] = {}

    for plat in ["google", "meta", "snap", "tiktok"]:
        acct = plat_cfg.get(plat, {})
        ids  = list(acct.values()) if isinstance(acct, dict) else []
        if not any(str(v).strip() for v in ids):
            continue
        with st.spinner(f"Loading {_PLATFORM_LABELS[plat]}…"):
            df,      err  = _fetch_platform_df(plat, proj, start,      end,        fetch_google)
            df_prev, _    = _fetch_platform_df(plat, proj, prev_start, prev_end,   fetch_google)
            daily         = _fetch_daily_df(   plat, proj, start,      end,        fetch_google_daily)
        platform_results[plat] = {
            "s":     _summarise(df),
            "s_prev":_summarise(df_prev),
            "daily": daily,
            "err":   err,
            "empty": df.empty,
        }

    if not platform_results:
        st.info("No connected platforms with data for this date range.")
        return

    curr = _agg_totals(platform_results)
    prev = {
        k: sum(r["s_prev"].get(k, 0) for r in platform_results.values())
        for k in ("spend","revenue","conversions","impressions","clicks")
    }
    # recompute derived prev metrics
    prev["roas"] = prev["revenue"] / prev["spend"]  if prev["spend"]       else 0.0
    prev["cpa"]  = prev["spend"]   / prev["conversions"] if prev["conversions"] else 0.0
    prev["ctr"]  = prev["clicks"]  / prev["impressions"] * 100 if prev["impressions"] else 0.0
    prev["aov"]  = prev["revenue"] / prev["conversions"] if prev["conversions"] else 0.0
    prev["cvr"]  = prev["conversions"] / prev["clicks"] * 100 if prev["clicks"] else 0.0
    prev["mer"]  = prev["revenue"] / prev["spend"]  if prev["spend"]       else 0.0

    daily_agg = _aggregate_daily(platform_results)

    # ── TOP: 3 summary cards ───────────────────────────────────────────────
    _render_top_cards(curr, prev)

    # ── MIDDLE: 8 metric cards ─────────────────────────────────────────────
    _section_label("Performance Metrics")
    _render_metric_grid(curr, prev, target_mer, target_cpa)

    # ── DAILY CHART ────────────────────────────────────────────────────────
    _section_label("Daily Trend")
    _render_daily_chart(daily_agg)

    # ── DAILY LOG TABLE ────────────────────────────────────────────────────
    _section_label("Daily Log")
    _render_daily_table(daily_agg)

    # ── PLATFORM BREAKDOWN ─────────────────────────────────────────────────
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
                st.rerun()


# ── main entry point ──────────────────────────────────────────────────────────

def render_projects_page(start: str, end: str,
                         fetch_google=None, fetch_google_daily=None):
    projects = load_projects()

    sel_id = st.session_state.get("selected_project_id")
    if sel_id:
        proj = next((p for p in projects if p["id"] == sel_id), None)
        if proj:
            _render_project_detail(proj, start, end,
                                   fetch_google=fetch_google,
                                   fetch_google_daily=fetch_google_daily)
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
