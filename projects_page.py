import json
import os
import uuid
import streamlit as st
import pandas as pd
from datetime import datetime

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


# ── helpers ───────────────────────────────────────────────────────────────────

def _platform_dots(platforms: dict) -> str:
    dots = []
    for key, color in _PLATFORM_COLORS.items():
        acct = (platforms or {}).get(key, {})
        ids = list(acct.values()) if isinstance(acct, dict) else []
        active = any(str(v).strip() for v in ids)
        opacity = "1" if active else "0.18"
        dots.append(
            f"<span style='display:inline-block;width:9px;height:9px;"
            f"border-radius:50%;background:{color};opacity:{opacity};"
            f"margin-right:4px'></span>"
        )
    return "".join(dots)


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


def _roas_indicator(roas: float, target_mer: float) -> str:
    """Returns a colored circle HTML. Green/yellow/red vs target, grey if no target."""
    if target_mer <= 0:
        color = "rgba(255,255,255,0.25)"
    elif roas >= target_mer:
        color = "#3fb950"       # green
    elif roas >= target_mer * 0.8:
        color = "#e3b341"       # yellow
    else:
        color = "#f85149"       # red
    return (f"<span style='display:inline-block;width:10px;height:10px;"
            f"border-radius:50%;background:{color};margin-right:8px;"
            f"flex-shrink:0;margin-top:2px'></span>")


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


# ── cross-platform data fetcher ───────────────────────────────────────────────

def _fetch_platform_df(platform: str, proj: dict, start: str, end: str,
                       fetch_google=None) -> tuple[pd.DataFrame, str | None]:
    """Returns (df, error_message). df is empty on error/skip; error is None on success."""
    plat = proj.get("platforms", {}).get(platform, {})

    if platform == "google":
        cid = plat.get("customer_id", "").strip()
        if not cid:
            return pd.DataFrame(), None
        if fetch_google is None:
            return pd.DataFrame(), "fetch_google not provided"
        try:
            df = fetch_google(cid, start, end)
            return df, None
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
                return pd.DataFrame(), "No META_ACCESS_TOKEN"
            df = fetch_meta_campaigns(token, acct, start, end)
            return df, None
        except Exception as e:
            return pd.DataFrame(), str(e)[:80]

    if platform == "snap":
        acct = plat.get("ad_account_id", "").strip()
        if not acct:
            return pd.DataFrame(), None
        try:
            from snap_ads_server import fetch_snap_campaigns
            token = os.getenv("SNAP_ACCESS_TOKEN", "")
            if not token:
                return pd.DataFrame(), "No SNAP_ACCESS_TOKEN"
            df = fetch_snap_campaigns(token, acct, start, end)
            return df, None
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
            df = fetch_tiktok_campaigns(token, adv, start, end, show_paused=False)
            return df, None
        except Exception as e:
            return pd.DataFrame(), str(e)[:80]

    return pd.DataFrame(), None


def _summarise(df: pd.DataFrame) -> dict:
    """Aggregate a campaigns DataFrame to a single-row summary dict."""
    if df.empty:
        return {}
    spend       = float(df["Cost"].sum())          if "Cost" in df.columns        else 0.0
    revenue     = float(df["Conv. Value"].sum())   if "Conv. Value" in df.columns else 0.0
    conversions = float(df["Conversions"].sum())   if "Conversions" in df.columns else 0.0
    impressions = float(df["Impressions"].sum())   if "Impressions" in df.columns else 0.0
    clicks      = float(df["Clicks"].sum())        if "Clicks" in df.columns      else 0.0
    roas   = revenue / spend       if spend else 0.0
    cpa    = spend / conversions   if conversions else 0.0
    ctr    = clicks / impressions * 100 if impressions else 0.0
    cpm    = spend / impressions * 1000 if impressions else 0.0
    return {
        "spend": spend, "revenue": revenue, "conversions": conversions,
        "impressions": impressions, "clicks": clicks,
        "roas": roas, "cpa": cpa, "ctr": ctr, "cpm": cpm,
    }


# ── project detail view ───────────────────────────────────────────────────────

def _render_project_detail(proj: dict, start: str, end: str, fetch_google=None):
    # back + edit row
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

    st.markdown(f"""
    <div style='margin:8px 0 20px'>
      <div style='font-size:28px;font-weight:900;color:#f0f6fc;letter-spacing:-1px'>
        {proj['name']}
      </div>
      <div style='font-size:12px;color:rgba(255,255,255,0.35);margin-top:6px;display:flex;align-items:center;gap:6px'>
        {_platform_dots(plat_cfg)}
        <span>Cross-platform · {start} → {end}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── fetch data for each connected platform ─────────────────────────────
    platform_results: dict[str, dict] = {}   # platform → {"s": summary, "err": str|None}

    for plat in ["google", "meta", "snap", "tiktok"]:
        acct = plat_cfg.get(plat, {})
        ids  = list(acct.values()) if isinstance(acct, dict) else []
        if not any(str(v).strip() for v in ids):
            continue
        label = _PLATFORM_LABELS[plat]
        with st.spinner(f"Loading {label}…"):
            df, err = _fetch_platform_df(plat, proj, start, end, fetch_google=fetch_google)
        platform_results[plat] = {"s": _summarise(df), "err": err, "empty": df.empty}

    if not platform_results:
        st.info("No connected platforms with data for this date range.")
        return

    # ── aggregate totals ───────────────────────────────────────────────────
    def _sum_field(field: str) -> float:
        return sum(r["s"].get(field, 0) for r in platform_results.values())

    total_spend   = _sum_field("spend")
    total_rev     = _sum_field("revenue")
    total_orders  = _sum_field("conversions")
    total_impr    = _sum_field("impressions")
    total_clicks  = _sum_field("clicks")
    agg_roas = total_rev  / total_spend  if total_spend  else 0.0
    agg_cpa  = total_spend / total_orders if total_orders else 0.0
    agg_ctr  = total_clicks / total_impr * 100 if total_impr else 0.0
    agg_cpm  = total_spend / total_impr * 1000 if total_impr else 0.0

    # ── KPI summary row ────────────────────────────────────────────────────
    cpa_color = ("#3fb950" if (target_cpa and agg_cpa <= target_cpa)
                 else "#f85149" if target_cpa else "#58a6ff")
    mer_color = ("#3fb950" if (target_mer and agg_roas >= target_mer)
                 else "#f85149" if target_mer else "#58a6ff")

    k1, k2, k3, k4, k5 = st.columns(5)
    _kpi_style = "background:rgba(255,255,255,0.04);border-radius:10px;padding:14px 16px"

    with k1:
        st.markdown(f"""
        <div style='{_kpi_style}'>
          <div style='font-size:10px;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:1px'>Total Spend</div>
          <div style='font-size:22px;font-weight:800;color:#f0f6fc;margin-top:4px'>{_fmt_sar(total_spend)}</div>
        </div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""
        <div style='{_kpi_style}'>
          <div style='font-size:10px;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:1px'>Revenue</div>
          <div style='font-size:22px;font-weight:800;color:#f0f6fc;margin-top:4px'>{_fmt_sar(total_rev)}</div>
        </div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""
        <div style='{_kpi_style}'>
          <div style='font-size:10px;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:1px'>Overall ROAS</div>
          <div style='font-size:22px;font-weight:800;color:{mer_color};margin-top:4px'>{agg_roas:.2f}×</div>
          {f"<div style='font-size:10px;color:rgba(255,255,255,0.3);margin-top:2px'>Target {target_mer:.1f}×</div>" if target_mer else ""}
        </div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""
        <div style='{_kpi_style}'>
          <div style='font-size:10px;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:1px'>Overall CPA</div>
          <div style='font-size:22px;font-weight:800;color:{cpa_color};margin-top:4px'>{_fmt_sar(agg_cpa)}</div>
          {f"<div style='font-size:10px;color:rgba(255,255,255,0.3);margin-top:2px'>Target {_fmt_sar(target_cpa)}</div>" if target_cpa else ""}
        </div>""", unsafe_allow_html=True)
    with k5:
        st.markdown(f"""
        <div style='{_kpi_style}'>
          <div style='font-size:10px;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:1px'>Total Orders</div>
          <div style='font-size:22px;font-weight:800;color:#f0f6fc;margin-top:4px'>{_fmt_num(total_orders)}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── platform breakdown table ───────────────────────────────────────────
    st.markdown(
        "<div style='font-size:11px;font-weight:600;color:rgba(255,255,255,0.35);"
        "text-transform:uppercase;letter-spacing:1px;margin-bottom:10px'>"
        "Platform Breakdown</div>",
        unsafe_allow_html=True
    )

    header_html = """
    <table style='width:100%;border-collapse:collapse;font-size:13px'>
      <thead>
        <tr style='color:rgba(255,255,255,0.4);text-transform:uppercase;font-size:10px;
                   letter-spacing:0.5px;border-bottom:1px solid rgba(255,255,255,0.08)'>
          <th style='text-align:left;padding:8px 14px;width:160px'></th>
          <th style='text-align:right;padding:8px 14px'>Spend</th>
          <th style='text-align:right;padding:8px 14px'>Revenue</th>
          <th style='text-align:right;padding:8px 14px'>ROAS</th>
          <th style='text-align:right;padding:8px 14px'>CPA</th>
          <th style='text-align:right;padding:8px 14px'>Orders</th>
          <th style='text-align:right;padding:8px 14px'>CTR</th>
          <th style='text-align:right;padding:8px 14px'>CPM</th>
        </tr>
      </thead>
      <tbody>
    """

    body = ""
    for i, (plat, res) in enumerate(platform_results.items()):
        s    = res["s"]
        err  = res["err"]
        color = _PLATFORM_COLORS[plat]
        label = _PLATFORM_LABELS[plat]
        bg    = "rgba(255,255,255,0.02)" if i % 2 else "transparent"

        spend_v   = s.get("spend", 0)
        rev_v     = s.get("revenue", 0)
        roas_v    = s.get("roas", 0)
        cpa_v     = s.get("cpa", 0)
        orders_v  = s.get("conversions", 0)
        ctr_v     = s.get("ctr", 0)
        cpm_v     = s.get("cpm", 0)

        indicator = _roas_indicator(roas_v, target_mer)

        if err and res["empty"]:
            # error state — show error message across columns
            body += f"""
        <tr style='background:{bg}'>
          <td style='padding:10px 14px'>
            <div style='display:flex;align-items:center'>
              {indicator}
              <span style='display:inline-block;width:8px;height:8px;border-radius:50%;
                           background:{color};margin-right:8px;flex-shrink:0'></span>
              <span style='font-weight:600;color:#f0f6fc'>{label}</span>
            </div>
          </td>
          <td colspan='7' style='padding:10px 14px;color:rgba(255,107,107,0.8);font-size:11px'>
            Error: {err}
          </td>
        </tr>"""
        else:
            roas_display = f"{roas_v:.2f}×" if spend_v else "—"
            body += f"""
        <tr style='background:{bg}'>
          <td style='padding:10px 14px'>
            <div style='display:flex;align-items:center'>
              {indicator}
              <span style='display:inline-block;width:8px;height:8px;border-radius:50%;
                           background:{color};margin-right:8px;flex-shrink:0'></span>
              <span style='font-weight:600;color:#f0f6fc'>{label}</span>
            </div>
          </td>
          <td style='padding:10px 14px;text-align:right;font-family:monospace;color:#f0f6fc'>{_fmt_sar(spend_v)}</td>
          <td style='padding:10px 14px;text-align:right;font-family:monospace;color:#f0f6fc'>{_fmt_sar(rev_v)}</td>
          <td style='padding:10px 14px;text-align:right;font-family:monospace;
                     color:{_roas_color(roas_v, target_mer)};font-weight:600'>{roas_display}</td>
          <td style='padding:10px 14px;text-align:right;font-family:monospace;color:#f0f6fc'>{_fmt_sar(cpa_v)}</td>
          <td style='padding:10px 14px;text-align:right;font-family:monospace;color:#f0f6fc'>{_fmt_num(orders_v)}</td>
          <td style='padding:10px 14px;text-align:right;font-family:monospace;color:rgba(255,255,255,0.65)'>{_fmt_pct(ctr_v)}</td>
          <td style='padding:10px 14px;text-align:right;font-family:monospace;color:rgba(255,255,255,0.65)'>{_fmt_sar(cpm_v)}</td>
        </tr>"""

    # totals row
    total_roas_display = f"{agg_roas:.2f}×" if total_spend else "—"
    body += f"""
        <tr style='background:rgba(255,255,255,0.055);border-top:1px solid rgba(255,255,255,0.1)'>
          <td style='padding:11px 14px;font-weight:700;color:#f0f6fc;letter-spacing:0.3px'>
            <div style='display:flex;align-items:center'>
              <span style='display:inline-block;width:8px;height:8px;border-radius:2px;
                           background:rgba(255,255,255,0.3);margin-right:16px;flex-shrink:0'></span>
              Total
            </div>
          </td>
          <td style='padding:11px 14px;text-align:right;font-family:monospace;font-weight:700;color:#f0f6fc'>{_fmt_sar(total_spend)}</td>
          <td style='padding:11px 14px;text-align:right;font-family:monospace;font-weight:700;color:#f0f6fc'>{_fmt_sar(total_rev)}</td>
          <td style='padding:11px 14px;text-align:right;font-family:monospace;font-weight:700;
                     color:{_roas_color(agg_roas, target_mer)}'>{total_roas_display}</td>
          <td style='padding:11px 14px;text-align:right;font-family:monospace;font-weight:700;color:#f0f6fc'>{_fmt_sar(agg_cpa)}</td>
          <td style='padding:11px 14px;text-align:right;font-family:monospace;font-weight:700;color:#f0f6fc'>{_fmt_num(total_orders)}</td>
          <td style='padding:11px 14px;text-align:right;font-family:monospace;color:rgba(255,255,255,0.65)'>{_fmt_pct(agg_ctr)}</td>
          <td style='padding:11px 14px;text-align:right;font-family:monospace;color:rgba(255,255,255,0.65)'>{_fmt_sar(agg_cpm)}</td>
        </tr>"""

    st.markdown(
        f"<div style='background:rgba(255,255,255,0.025);border:1px solid rgba(255,255,255,0.07);"
        f"border-radius:12px;overflow:hidden'>"
        f"{header_html}{body}</tbody></table></div>",
        unsafe_allow_html=True
    )

    # legend
    if target_mer > 0:
        st.markdown(f"""
        <div style='margin-top:10px;display:flex;gap:18px;font-size:11px;color:rgba(255,255,255,0.35)'>
          <span><span style='color:#3fb950'>●</span> ROAS ≥ {target_mer:.1f}× (on target)</span>
          <span><span style='color:#e3b341'>●</span> ROAS ≥ {target_mer*0.8:.1f}× (near target)</span>
          <span><span style='color:#f85149'>●</span> ROAS &lt; {target_mer*0.8:.1f}× (below target)</span>
        </div>""", unsafe_allow_html=True)


def _roas_color(roas: float, target_mer: float) -> str:
    if target_mer <= 0:
        return "#f0f6fc"
    if roas >= target_mer:
        return "#3fb950"
    if roas >= target_mer * 0.8:
        return "#e3b341"
    return "#f85149"


# ── card grid ─────────────────────────────────────────────────────────────────

def _render_cards(projects: list[dict]):
    cols = st.columns(3, gap="medium")
    for i, proj in enumerate(projects):
        plat_cfg = proj.get("platforms", {})
        target_cpa = proj.get("target_cpa", 0)
        target_mer = proj.get("target_mer", 0)
        dots = _platform_dots(plat_cfg)

        with cols[i % 3]:
            btn_key = f"proj_card_{proj['id']}"
            st.markdown(f"""
            <div style='background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);
                        border-radius:14px;padding:18px 20px 14px;margin-bottom:4px'>
              <div style='font-size:17px;font-weight:700;color:#f0f6fc;margin-bottom:10px'>
                {proj['name']}
              </div>
              <div style='margin-bottom:12px'>{dots}</div>
              <div style='display:flex;gap:24px'>
                <div>
                  <div style='font-size:9.5px;color:rgba(255,255,255,0.35);text-transform:uppercase;letter-spacing:0.8px'>Target CPA</div>
                  <div style='font-size:14px;font-weight:600;color:#58a6ff'>
                    {_fmt_sar(target_cpa) if target_cpa else "—"}
                  </div>
                </div>
                <div>
                  <div style='font-size:9.5px;color:rgba(255,255,255,0.35);text-transform:uppercase;letter-spacing:0.8px'>Target MER</div>
                  <div style='font-size:14px;font-weight:600;color:#58a6ff'>
                    {f"{target_mer:.1f}×" if target_mer else "—"}
                  </div>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Open →", key=btn_key, use_container_width=True):
                st.session_state["selected_project_id"] = proj["id"]
                st.rerun()


# ── main entry point ──────────────────────────────────────────────────────────

def render_projects_page(start: str, end: str, fetch_google=None):
    projects = load_projects()

    sel_id = st.session_state.get("selected_project_id")
    if sel_id:
        proj = next((p for p in projects if p["id"] == sel_id), None)
        if proj:
            _render_project_detail(proj, start, end, fetch_google=fetch_google)
            return
        else:
            st.session_state.pop("selected_project_id", None)

    hcol, bcol = st.columns([4, 1])
    with hcol:
        st.markdown("""
        <div style='padding:8px 0 4px'>
          <div style='font-size:26px;font-weight:900;color:#f0f6fc;letter-spacing:-1px;line-height:1'>
            Projects
          </div>
          <div style='font-size:13px;color:rgba(255,255,255,0.28);margin-top:5px'>
            Cross-platform overview per client
          </div>
        </div>
        """, unsafe_allow_html=True)
    with bcol:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if st.button("＋  New project", type="primary", use_container_width=True):
            _new_project_dialog()

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    if not projects:
        st.info("No projects yet. Click **＋ New project** to create one.")
        return

    _render_cards(projects)
