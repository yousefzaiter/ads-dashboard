"""
Snapchat Ads data fetcher — Marketing API v1.
Returns structured campaign data matching the Google/Meta Ads schema used by dashboard.py.

Spend values from Snap API are in micro-currency (divide by 1,000,000 to get dollars/SAR).
"""
import base64
import os
import re

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
    override=True,
)

SNAP_API  = "https://adsapi.snapchat.com/v1"
TOKEN_URL = "https://accounts.snapchat.com/login/oauth2/access_token"
_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

_STAT_FIELDS = ",".join([
    "impressions", "swipes", "spend",
    "video_views", "screen_time_millis",
    "quartile_1", "quartile_2", "quartile_3", "view_completion",
    "swipe_up_attribution_purchases", "view_attribution_purchases",
    "conversion_purchases", "conversion_purchases_value",
])


# ── Low-level request ─────────────────────────────────────────────────────────

def _get(path: str, token: str, params: dict | None = None) -> dict:
    resp = requests.get(
        f"{SNAP_API}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=20,
    )
    if resp.status_code == 401:
        raise RuntimeError("TOKEN_EXPIRED")
    if resp.status_code != 200:
        raise RuntimeError(f"Snap API {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def _show_token_error() -> None:
    st.error(
        "🔒 انتهت صلاحية التوكن لـ Snapchat.  "
        "شغّل `python3 snap_auth.py` مجدداً للحصول على توكن جديد."
    )


# ── Token management ──────────────────────────────────────────────────────────

def get_snap_token() -> str:
    return os.getenv("SNAP_ACCESS_TOKEN", "")


def refresh_snap_token() -> str | None:
    """Exchange refresh_token for a new access_token and save to .env."""
    client_id     = os.getenv("SNAP_CLIENT_ID", "")
    client_secret = os.getenv("SNAP_CLIENT_SECRET", "")
    refresh_token = os.getenv("SNAP_REFRESH_TOKEN", "")

    if not all([client_id, client_secret, refresh_token]):
        return None

    creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp  = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type":  "application/x-www-form-urlencoded",
        },
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        timeout=15,
    )
    data = resp.json()
    if "access_token" not in data:
        return None

    new_access  = data["access_token"]
    new_refresh = data.get("refresh_token", refresh_token)

    with open(_ENV_PATH) as f:
        content = f.read()
    content = re.sub(r"SNAP_ACCESS_TOKEN=\S*", f"SNAP_ACCESS_TOKEN={new_access}", content)
    content = re.sub(r"SNAP_REFRESH_TOKEN=\S*", f"SNAP_REFRESH_TOKEN={new_refresh}", content)
    with open(_ENV_PATH, "w") as f:
        f.write(content)

    os.environ["SNAP_ACCESS_TOKEN"]  = new_access
    os.environ["SNAP_REFRESH_TOKEN"] = new_refresh
    return new_access


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ts(date_str: str, end: bool = False) -> str:
    """Convert YYYY-MM-DD to Snap API ISO-8601 timestamp."""
    return f"{date_str}T{'23:59:59.999' if end else '00:00:00.000'}Z"


def _parse_total_stats(timeseries_stat: dict) -> dict:
    """Extract metrics from a TOTAL-granularity timeseries_stat object."""
    ts = timeseries_stat.get("total_stats", {})
    spend_micro = float(ts.get("spend", 0) or 0)
    spend       = spend_micro / 1_000_000
    impressions = int(ts.get("impressions", 0) or 0)
    swipes      = int(ts.get("swipes", 0) or 0)
    video_views = int(ts.get("video_views", 0) or 0)
    conv        = int(ts.get("conversion_purchases", 0) or 0)
    conv_value  = float(ts.get("conversion_purchases_value", 0) or 0) / 1_000_000

    swipe_rate = round(swipes / impressions * 100, 4) if impressions > 0 else 0.0
    cps        = round(spend / swipes, 2)         if swipes > 0      else 0.0
    roas       = round(conv_value / spend, 2)     if spend > 0       else 0.0
    cpa        = round(spend / conv, 2)           if conv > 0        else 0.0
    vvr        = round(video_views / impressions * 100, 2) if impressions > 0 else 0.0

    return {
        "impressions": impressions, "swipes": swipes,
        "spend":       round(spend, 2),
        "swipe_rate":  swipe_rate, "cps": cps,
        "conversions": float(conv), "conv_value": round(conv_value, 2),
        "roas": roas, "cpa": cpa,
        "video_views": video_views, "vvr": vvr,
    }


def _empty_stats() -> dict:
    return _parse_total_stats({})


def _to_df_row(name: str, entity_id: str, parent_id: str,
               status: str, type_: str, s: dict) -> dict:
    return {
        "ID":          entity_id,
        "Campaign":    name,
        "Campaign ID": parent_id,
        "Status":      "ENABLED" if status in ("ACTIVE",) else status,
        "Type":        type_,
        "Impressions": s["impressions"],
        "Clicks":      s["swipes"],
        "Cost":        s["spend"],
        "CTR":         s["swipe_rate"],
        "Avg CPC":     s["cps"],
        "Conversions": s["conversions"],
        "Conv. Value": s["conv_value"],
        "CPA":         s["cpa"],
        "ROAS":        s["roas"],
        "Imp. Share":  None,
        "Video Views": s["video_views"],
        "VVR":         s["vvr"],
    }


def _fetch_stats(path: str, token: str, start: str, end: str) -> dict:
    resp = _get(path, token, {
        "granularity": "TOTAL",
        "start_time":  _ts(start),
        "end_time":    _ts(end, end=True),
        "fields":      _STAT_FIELDS,
    })
    rows = resp.get("timeseries_stats", [])
    if not rows:
        return _empty_stats()
    return _parse_total_stats(rows[0].get("timeseries_stat", {}))


# ── Ad accounts ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_snap_accounts(token: str) -> list[dict]:
    """Return [{id, name}] for all active Snap ad accounts."""
    try:
        orgs_data = _get("/me/organizations", token)
        accounts  = []
        for org_wrap in orgs_data.get("organizations", []):
            org_id = org_wrap.get("organization", {}).get("id")
            if not org_id:
                continue
            accts_data = _get(f"/organizations/{org_id}/adaccounts", token)
            for a in accts_data.get("adaccounts", []):
                ad = a.get("adaccount", {})
                if ad.get("status") == "ACTIVE":
                    accounts.append({"id": ad["id"], "name": ad.get("name", ad["id"])})
        return accounts
    except RuntimeError:
        return []


# ── Campaign performance ───────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def fetch_snap_campaigns(token: str, account_id: str,
                         start: str, end: str) -> pd.DataFrame:
    """Campaign-level performance for a Snap ad account."""
    try:
        resp = _get(f"/adaccounts/{account_id}/campaigns", token)
    except RuntimeError as e:
        if "TOKEN_EXPIRED" in str(e):
            _show_token_error()
        else:
            st.error(f"Snap API error: {e}")
        return pd.DataFrame()

    records = []
    for c_wrap in resp.get("campaigns", []):
        c       = c_wrap.get("campaign", {})
        camp_id = c.get("id", "")
        try:
            s = _fetch_stats(f"/campaigns/{camp_id}/stats", token, start, end)
        except Exception:
            s = _empty_stats()
        records.append(_to_df_row(
            c.get("name", ""), camp_id, account_id,
            c.get("status", "PAUSED"), "SNAP", s,
        ))

    df = pd.DataFrame(records)
    return df[df["Cost"] > 0].reset_index(drop=True) if not df.empty else df


# ── Daily data ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def fetch_snap_daily(token: str, account_id: str,
                     start: str, end: str) -> pd.DataFrame:
    """Daily breakdown for a Snap ad account."""
    try:
        resp = _get(f"/adaccounts/{account_id}/stats", token, {
            "granularity": "DAY",
            "start_time":  _ts(start),
            "end_time":    _ts(end, end=True),
            "fields":      "impressions,swipes,spend,conversion_purchases,conversion_purchases_value",
        })
    except Exception:
        return pd.DataFrame()

    records = []
    for row in resp.get("timeseries_stats", []):
        for pt in row.get("timeseries_stat", {}).get("timeseries", []):
            day   = pt.get("start_time", "")[:10]
            stats = pt.get("stats", {})
            spend      = float(stats.get("spend", 0) or 0) / 1_000_000
            conv_value = float(stats.get("conversion_purchases_value", 0) or 0) / 1_000_000
            records.append({
                "Date":        day,
                "Impressions": int(stats.get("impressions", 0) or 0),
                "Clicks":      int(stats.get("swipes", 0) or 0),
                "Cost":        round(spend, 2),
                "Conversions": float(stats.get("conversion_purchases", 0) or 0),
                "Conv. Value": round(conv_value, 2),
            })

    df = pd.DataFrame(records)
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"])
    return df


# ── Ad Squad (ad sets) ────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def fetch_snap_adsets(token: str, campaign_id: str,
                      start: str, end: str) -> pd.DataFrame:
    """Ad-squad-level insights for a campaign."""
    try:
        resp = _get(f"/campaigns/{campaign_id}/adsquads", token)
    except RuntimeError as e:
        if "TOKEN_EXPIRED" in str(e):
            _show_token_error()
        else:
            st.error(f"Snap API error: {e}")
        return pd.DataFrame()

    records = []
    for sq_wrap in resp.get("adsquads", []):
        sq    = sq_wrap.get("adsquad", {})
        sq_id = sq.get("id", "")
        try:
            s = _fetch_stats(f"/adsquads/{sq_id}/stats", token, start, end)
        except Exception:
            s = _empty_stats()
        records.append(_to_df_row(
            sq.get("name", ""), sq_id, campaign_id,
            sq.get("status", "PAUSED"), "SNAP_ADSET", s,
        ))

    df = pd.DataFrame(records)
    return df[df["Cost"] > 0].reset_index(drop=True) if not df.empty else df


# ── Ads ───────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def fetch_snap_ads(token: str, adset_id: str,
                   start: str, end: str) -> pd.DataFrame:
    """Ad-level insights for an ad squad."""
    try:
        resp = _get(f"/adsquads/{adset_id}/ads", token)
    except RuntimeError as e:
        if "TOKEN_EXPIRED" in str(e):
            _show_token_error()
        else:
            st.error(f"Snap API error: {e}")
        return pd.DataFrame()

    records = []
    for ad_wrap in resp.get("ads", []):
        ad    = ad_wrap.get("ad", {})
        ad_id = ad.get("id", "")
        try:
            s = _fetch_stats(f"/ads/{ad_id}/stats", token, start, end)
        except Exception:
            s = _empty_stats()
        records.append(_to_df_row(
            ad.get("name", ""), ad_id, adset_id,
            ad.get("status", "PAUSED"), "SNAP_AD", s,
        ))

    df = pd.DataFrame(records)
    return df[df["Cost"] > 0].reset_index(drop=True) if not df.empty else df
