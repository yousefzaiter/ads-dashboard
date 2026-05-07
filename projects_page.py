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
        # a platform is "connected" if it has a non-empty account id
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
        return f"SAR {v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"SAR {v/1_000:.1f}K"
    return f"SAR {v:,.0f}"


def _fmt_num(v: float) -> str:
    if v == 0:
        return "—"
    if v >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v/1_000:.1f}K"
    return f"{v:,.0f}"


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
        meta_aid = st.text_input("Meta Ad Account ID", placeholder="act_123456")
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
                       fetch_google=None) -> pd.DataFrame:
    plat = proj.get("platforms", {}).get(platform, {})

    if platform == "google":
        cid = plat.get("customer_id", "").strip()
        if not cid or fetch_google is None:
            return pd.DataFrame()
        try:
            return fetch_google(cid, start, end)
        except Exception:
            return pd.DataFrame()

    if platform == "meta":
        acct = plat.get("ad_account_id", "").strip()
        if not acct:
            return pd.DataFrame()
        try:
            from meta_ads_server import fetch_meta_campaigns
            token = os.getenv("META_ACCESS_TOKEN", "")
            return fetch_meta_campaigns(token, acct, start, end)
        except Exception:
            return pd.DataFrame()

    if platform == "snap":
        acct = plat.get("ad_account_id", "").strip()
        if not acct:
            return pd.DataFrame()
        try:
            from snap_ads_server import fetch_snap_campaigns
            token = os.getenv("SNAP_ACCESS_TOKEN", "")
            return fetch_snap_campaigns(token, acct, start, end)
        except Exception:
            return pd.DataFrame()

    if platform == "tiktok":
        adv = plat.get("advertiser_id", "").strip()
        if not adv:
            return pd.DataFrame()
        try:
            from tiktok_ads_server import fetch_tiktok_campaigns
            token = os.getenv("TIKTOK_ACCESS_TOKEN", "")
            if not token or token == "pending":
                return pd.DataFrame()
            return fetch_tiktok_campaigns(token, adv, start, end, show_paused=False)
        except Exception:
            return pd.DataFrame()

    return pd.DataFrame()


def _summarise(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    spend       = df["Cost"].sum() if "Cost" in df.columns else 0
    revenue     = df["Conv. Value"].sum() if "Conv. Value" in df.columns else 0
    conversions = df["Conversions"].sum() if "Conversions" in df.columns else 0
    impressions = df["Impressions"].sum() if "Impressions" in df.columns else 0
    clicks      = df["Clicks"].sum() if "Clicks" in df.columns else 0
    roas        = revenue / spend if spend else 0
    cpa         = spend / conversions if conversions else 0
    return {
        "spend": spend, "revenue": revenue, "conversions": conversions,
        "impressions": impressions, "clicks": clicks, "roas": roas, "cpa": cpa,
    }


# ── project detail view ───────────────────────────────────────────────────────

def _render_project_detail(proj: dict, start: str, end: str, fetch_google=None):
    # back button
    if st.button("← Back to projects", key="proj_back"):
        st.session_state.pop("selected_project_id", None)
        st.rerun()

    plat_cfg = proj.get("platforms", {})

    st.markdown(f"""
    <div style='margin:8px 0 20px'>
      <div style='font-size:26px;font-weight:900;color:#f0f6fc;letter-spacing:-1px'>
        {proj['name']}
      </div>
      <div style='font-size:12px;color:rgba(255,255,255,0.35);margin-top:4px'>
        {_platform_dots(plat_cfg)} Cross-platform · {start} → {end}
      </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("✏️  Edit project", key="proj_edit"):
        _edit_project_dialog(proj)

    st.markdown("---")

    rows = []
    for plat in ["google", "meta", "snap", "tiktok"]:
        acct = plat_cfg.get(plat, {})
        ids = list(acct.values()) if isinstance(acct, dict) else []
        if not any(str(v).strip() for v in ids):
            continue
        df = _fetch_platform_df(plat, proj, start, end, fetch_google=fetch_google)
        s = _summarise(df)
        rows.append({
            "Platform":    _PLATFORM_LABELS[plat],
            "Spend":       s.get("spend", 0),
            "Revenue":     s.get("revenue", 0),
            "ROAS":        s.get("roas", 0),
            "CPA":         s.get("cpa", 0),
            "Orders":      s.get("conversions", 0),
            "Impressions": s.get("impressions", 0),
            "Clicks":      s.get("clicks", 0),
        })

    if not rows:
        st.info("No connected platforms with data for this date range.")
        return

    # totals row
    total_spend   = sum(r["Spend"] for r in rows)
    total_rev     = sum(r["Revenue"] for r in rows)
    total_orders  = sum(r["Orders"] for r in rows)
    total_impr    = sum(r["Impressions"] for r in rows)
    total_clicks  = sum(r["Clicks"] for r in rows)
    rows.append({
        "Platform":    "**Total**",
        "Spend":       total_spend,
        "Revenue":     total_rev,
        "ROAS":        total_rev / total_spend if total_spend else 0,
        "CPA":         total_spend / total_orders if total_orders else 0,
        "Orders":      total_orders,
        "Impressions": total_impr,
        "Clicks":      total_clicks,
    })

    # KPI summary cards
    target_cpa = proj.get("target_cpa", 0)
    target_mer = proj.get("target_mer", 0)
    agg_roas   = total_rev / total_spend if total_spend else 0
    agg_cpa    = total_spend / total_orders if total_orders else 0

    cpa_color  = "#3fb950" if (target_cpa and agg_cpa <= target_cpa) else "#f85149" if target_cpa else "#58a6ff"
    mer_color  = "#3fb950" if (target_mer and agg_roas >= target_mer) else "#f85149" if target_mer else "#58a6ff"

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""
        <div style='background:rgba(255,255,255,0.04);border-radius:10px;padding:14px 16px'>
          <div style='font-size:10px;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:1px'>Total Spend</div>
          <div style='font-size:22px;font-weight:800;color:#f0f6fc;margin-top:4px'>{_fmt_sar(total_spend)}</div>
        </div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""
        <div style='background:rgba(255,255,255,0.04);border-radius:10px;padding:14px 16px'>
          <div style='font-size:10px;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:1px'>Revenue</div>
          <div style='font-size:22px;font-weight:800;color:#f0f6fc;margin-top:4px'>{_fmt_sar(total_rev)}</div>
        </div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""
        <div style='background:rgba(255,255,255,0.04);border-radius:10px;padding:14px 16px'>
          <div style='font-size:10px;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:1px'>ROAS</div>
          <div style='font-size:22px;font-weight:800;color:{mer_color};margin-top:4px'>{agg_roas:.2f}×</div>
          {f"<div style='font-size:10px;color:rgba(255,255,255,0.3)'>Target {target_mer:.1f}×</div>" if target_mer else ""}
        </div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""
        <div style='background:rgba(255,255,255,0.04);border-radius:10px;padding:14px 16px'>
          <div style='font-size:10px;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:1px'>CPA</div>
          <div style='font-size:22px;font-weight:800;color:{cpa_color};margin-top:4px'>{_fmt_sar(agg_cpa)}</div>
          {f"<div style='font-size:10px;color:rgba(255,255,255,0.3)'>Target {_fmt_sar(target_cpa)}</div>" if target_cpa else ""}
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # table
    header_html = """
    <table style='width:100%;border-collapse:collapse;font-size:13px'>
      <thead>
        <tr style='color:rgba(255,255,255,0.4);text-transform:uppercase;font-size:10px;letter-spacing:0.5px'>
          <th style='text-align:left;padding:8px 12px'>Platform</th>
          <th style='text-align:right;padding:8px 12px'>Spend</th>
          <th style='text-align:right;padding:8px 12px'>Revenue</th>
          <th style='text-align:right;padding:8px 12px'>ROAS</th>
          <th style='text-align:right;padding:8px 12px'>CPA</th>
          <th style='text-align:right;padding:8px 12px'>Orders</th>
          <th style='text-align:right;padding:8px 12px'>Impressions</th>
          <th style='text-align:right;padding:8px 12px'>Clicks</th>
        </tr>
      </thead>
      <tbody>
    """
    body = ""
    for i, r in enumerate(rows):
        is_total = r["Platform"].startswith("**")
        bg = "rgba(255,255,255,0.06)" if is_total else ("rgba(255,255,255,0.02)" if i % 2 else "transparent")
        weight = "700" if is_total else "400"
        name = r["Platform"].replace("**", "")
        body += f"""
        <tr style='background:{bg}'>
          <td style='padding:9px 12px;font-weight:{weight};color:#f0f6fc'>{name}</td>
          <td style='padding:9px 12px;text-align:right;font-family:monospace'>{_fmt_sar(r["Spend"])}</td>
          <td style='padding:9px 12px;text-align:right;font-family:monospace'>{_fmt_sar(r["Revenue"])}</td>
          <td style='padding:9px 12px;text-align:right;font-family:monospace'>{r["ROAS"]:.2f}×</td>
          <td style='padding:9px 12px;text-align:right;font-family:monospace'>{_fmt_sar(r["CPA"])}</td>
          <td style='padding:9px 12px;text-align:right;font-family:monospace'>{_fmt_num(r["Orders"])}</td>
          <td style='padding:9px 12px;text-align:right;font-family:monospace'>{_fmt_num(r["Impressions"])}</td>
          <td style='padding:9px 12px;text-align:right;font-family:monospace'>{_fmt_num(r["Clicks"])}</td>
        </tr>"""

    st.markdown(
        f"<div style='background:rgba(255,255,255,0.03);border-radius:10px;overflow:hidden'>"
        f"{header_html}{body}</tbody></table></div>",
        unsafe_allow_html=True
    )


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
              <div style='font-size:16px;font-weight:700;color:#f0f6fc;margin-bottom:8px'>
                {proj['name']}
              </div>
              <div style='margin-bottom:12px'>{dots}</div>
              <div style='display:flex;gap:20px'>
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

    # check if a project is selected
    sel_id = st.session_state.get("selected_project_id")
    if sel_id:
        proj = next((p for p in projects if p["id"] == sel_id), None)
        if proj:
            _render_project_detail(proj, start, end, fetch_google=fetch_google)
            return
        else:
            st.session_state.pop("selected_project_id", None)

    # header row
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
