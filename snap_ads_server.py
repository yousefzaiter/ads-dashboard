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
import logging

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
    override=True,
)

SNAP_API    = "https://adsapi.snapchat.com/v1"
TOKEN_URL   = "https://accounts.snapchat.com/login/oauth2/access_token"
_ENV_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
USD_TO_SAR  = float(os.getenv("USD_TO_SAR", "3.75"))

_STAT_FIELDS = ",".join([
    "impressions", "swipes", "spend",
    "video_views",
    "quartile_1", "quartile_2", "quartile_3", "view_completion",
    "conversion_purchases", "conversion_purchases_value",
])


# ── Token management ──────────────────────────────────────────────────────────

def get_snap_token() -> str:
    return os.getenv("SNAP_ACCESS_TOKEN", "")


def refresh_snap_token() -> str | None:
    """Exchange refresh_token for a new access_token and persist to .env."""
    client_id     = os.getenv("SNAP_CLIENT_ID", "")
    client_secret = os.getenv("SNAP_CLIENT_SECRET", "")
    refresh_token = os.getenv("SNAP_REFRESH_TOKEN", "")

    if not all([client_id, client_secret, refresh_token]):
        return None

    creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    try:
        resp = requests.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type":  "application/x-www-form-urlencoded",
            },
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            timeout=15,
        )
        data = resp.json()
    except Exception:
        return None

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


# ── Low-level request ─────────────────────────────────────────────────────────

def _get(path: str, token: str, params: dict | None = None) -> dict:
    """Make a GET request, auto-refreshing the token once on 401."""
    resp = requests.get(
        f"{SNAP_API}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=20,
    )
    if resp.status_code == 401:
        # Token expired — try refresh once
        new_token = refresh_snap_token()
        if new_token:
            resp = requests.get(
                f"{SNAP_API}{path}",
                headers={"Authorization": f"Bearer {new_token}"},
                params=params or {},
                timeout=20,
            )
            if resp.status_code == 401:
                raise RuntimeError("TOKEN_EXPIRED")
        else:
            raise RuntimeError("TOKEN_EXPIRED")
    if resp.status_code != 200:
        raise RuntimeError(f"Snap API {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def _show_token_error() -> None:
    st.error(
        "🔒 انتهت صلاحية التوكن لـ Snapchat.  "
        "شغّل `python3 snap_auth.py` مجدداً للحصول على توكن جديد."
    )


# ── Currency helpers ──────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def get_snap_account_currency(token: str, account_id: str) -> str:
    """Return the billing currency for a Snap ad account (e.g. 'USD', 'SAR')."""
    try:
        data = _get(f"/adaccounts/{account_id}", token)
        return data.get("adaccount", {}).get("currency", "SAR").upper()
    except Exception:
        return "SAR"


def _to_sar(amount: float, currency: str) -> float:
    if currency == "USD":
        return round(amount * USD_TO_SAR, 2)
    return amount


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ts(date_str: str, end: bool = False) -> str:
    """Convert YYYY-MM-DD to Snap API ISO-8601 timestamp.
    Snap requires exact hour boundaries — use next-day midnight for end times."""
    from datetime import date as _date, timedelta as _td
    if end:
        next_day = (_date.fromisoformat(date_str) + _td(days=1)).isoformat()
        return f"{next_day}T00:00:00.000+03:00"
    return f"{date_str}T00:00:00.000+03:00"


def _parse_stats(stats: dict, currency: str = "SAR") -> dict:
    """Extract metrics from a Snap stats dict (already the inner 'stats' object)."""
    spend_micro = float(stats.get("spend", 0) or 0)
    spend       = _to_sar(spend_micro / 1_000_000, currency)
    impressions = int(stats.get("impressions", 0) or 0)
    swipes      = int(stats.get("swipes", 0) or 0)
    video_views = int(stats.get("video_views", 0) or 0)
    conv        = int(stats.get("conversion_purchases", 0) or 0)
    conv_value  = _to_sar(float(stats.get("conversion_purchases_value", 0) or 0) / 1_000_000, currency)

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


def _parse_total_stats(timeseries_stat: dict, currency: str = "SAR") -> dict:
    """Legacy wrapper — kept for _fetch_stats compatibility."""
    return _parse_stats(timeseries_stat.get("total_stats", {}), currency)


def _empty_stats() -> dict:
    return _parse_stats({})


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


def _fetch_stats(path: str, token: str, start: str, end: str, currency: str = "SAR") -> dict:
    """Fetch TOTAL-granularity stats. Response: total_stats[0].total_stat.stats"""
    resp = _get(path, token, {
        "granularity": "TOTAL",
        "start_time":  _ts(start),
        "end_time":    _ts(end, end=True),
        "fields":      _STAT_FIELDS,
    })
    rows = resp.get("total_stats", [])
    if not rows:
        return _empty_stats()
    return _parse_stats(rows[0].get("total_stat", {}).get("stats", {}), currency)


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
    except RuntimeError as e:
        print(f"[Snap] API Error: {str(e)[:200]}")
        return []
    except Exception as e:
        print(f"[Snap] Unexpected error: {str(e)[:200]}")
        return []


# ── Campaign performance ───────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner="جارٍ تحميل حملات Snap…")
def fetch_snap_campaigns(token: str, account_id: str,
                         start: str, end: str,
                         show_paused: bool = False) -> pd.DataFrame:
    """Campaign-level performance for a Snap ad account.
    Only fetches stats for ACTIVE campaigns by default to avoid making
    hundreds of API calls for large accounts with many paused campaigns."""
    try:
        resp = _get(f"/adaccounts/{account_id}/campaigns", token)
    except RuntimeError as e:
        if "TOKEN_EXPIRED" in str(e):
            _show_token_error()
        else:
            st.error(f"Snap API error: {e}")
        return pd.DataFrame()

    currency = get_snap_account_currency(token, account_id)
    records  = []
    for c_wrap in resp.get("campaigns", []):
        c           = c_wrap.get("campaign", {})
        camp_id     = c.get("id", "")
        camp_status = c.get("status", "PAUSED")

        # Skip PAUSED campaigns unless show_paused requested — avoids
        # hundreds of wasted API calls on large accounts.
        if not show_paused and camp_status != "ACTIVE":
            continue

        try:
            s = _fetch_stats(f"/campaigns/{camp_id}/stats", token, start, end, currency)
        except Exception as ex:
            st.warning(f"Snap stats error for {c.get('name', camp_id)}: {ex}")
            s = _empty_stats()
        records.append(_to_df_row(
            c.get("name", ""), camp_id, account_id, camp_status, "SNAP", s,
        ))

    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).reset_index(drop=True)


# ── Daily data ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner="جارٍ تحميل بيانات Snap اليومية…")
def fetch_snap_daily(token: str, account_id: str,
                     start: str, end: str,
                     show_paused: bool = False) -> pd.DataFrame:
    """Daily breakdown aggregated across campaigns.
    Account-level stats only support 'spend'; we use campaign-level DAY stats.
    Pass show_paused=True to include paused/inactive campaigns in the totals."""
    try:
        resp = _get(f"/adaccounts/{account_id}/campaigns", token)
    except RuntimeError:
        return pd.DataFrame()

    currency      = get_snap_account_currency(token, account_id)
    daily: dict[str, dict] = {}
    _daily_fields = "impressions,swipes,spend,conversion_purchases,conversion_purchases_value"

    for c_wrap in resp.get("campaigns", []):
        camp_status = c_wrap.get("campaign", {}).get("status", "")
        if not show_paused and camp_status != "ACTIVE":
            continue
        c       = c_wrap.get("campaign", {})
        camp_id = c.get("id", "")
        try:
            dr = _get(f"/campaigns/{camp_id}/stats", token, {
                "granularity": "DAY",
                "start_time":  _ts(start),
                "end_time":    _ts(end, end=True),
                "fields":      _daily_fields,
            })
        except Exception:
            continue
        for row in dr.get("timeseries_stats", []):
            for pt in row.get("timeseries_stat", {}).get("timeseries", []):
                day   = pt.get("start_time", "")[:10]
                stats = pt.get("stats", {})
                spend      = _to_sar(float(stats.get("spend", 0) or 0) / 1_000_000, currency)
                conv_value = _to_sar(float(stats.get("conversion_purchases_value", 0) or 0) / 1_000_000, currency)
                if day not in daily:
                    daily[day] = {"Impressions": 0, "Clicks": 0,
                                  "Cost": 0.0, "Conversions": 0.0, "Conv. Value": 0.0}
                daily[day]["Impressions"] += int(stats.get("impressions", 0) or 0)
                daily[day]["Clicks"]      += int(stats.get("swipes", 0) or 0)
                daily[day]["Cost"]        += spend
                daily[day]["Conversions"] += float(stats.get("conversion_purchases", 0) or 0)
                daily[day]["Conv. Value"] += conv_value

    if not daily:
        return pd.DataFrame()

    records = [{"Date": day, **vals} for day, vals in sorted(daily.items())]
    for r in records:
        r["Cost"]        = round(r["Cost"], 2)
        r["Conv. Value"] = round(r["Conv. Value"], 2)
    df = pd.DataFrame(records)
    df["Date"] = pd.to_datetime(df["Date"])
    return df


# ── Ad Squad (ad sets) ────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def fetch_snap_adsets(token: str, campaign_id: str,
                      start: str, end: str,
                      account_id: str = "") -> pd.DataFrame:
    """Ad-squad-level insights for a campaign."""
    try:
        resp = _get(f"/campaigns/{campaign_id}/adsquads", token)
    except RuntimeError as e:
        if "TOKEN_EXPIRED" in str(e):
            _show_token_error()
        else:
            st.error(f"Snap API error: {e}")
        return pd.DataFrame()

    currency = get_snap_account_currency(token, account_id) if account_id else "SAR"
    records  = []
    for sq_wrap in resp.get("adsquads", []):
        sq    = sq_wrap.get("adsquad", {})
        sq_id = sq.get("id", "")
        if sq.get("status") not in ("ACTIVE", "PAUSED"):
            continue
        try:
            s = _fetch_stats(f"/adsquads/{sq_id}/stats", token, start, end, currency)
        except Exception:
            s = _empty_stats()
        records.append(_to_df_row(
            sq.get("name", ""), sq_id, campaign_id,
            sq.get("status", "PAUSED"), "SNAP_ADSET", s,
        ))

    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).reset_index(drop=True)


# ── Ads ───────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def fetch_snap_ads(token: str, adset_id: str,
                   start: str, end: str,
                   account_id: str = "") -> pd.DataFrame:
    """Ad-level insights for an ad squad."""
    try:
        resp = _get(f"/adsquads/{adset_id}/ads", token)
    except RuntimeError as e:
        if "TOKEN_EXPIRED" in str(e):
            _show_token_error()
        else:
            st.error(f"Snap API error: {e}")
        return pd.DataFrame()

    currency = get_snap_account_currency(token, account_id) if account_id else "SAR"
    records  = []
    for ad_wrap in resp.get("ads", []):
        ad    = ad_wrap.get("ad", {})
        ad_id = ad.get("id", "")
        try:
            s = _fetch_stats(f"/ads/{ad_id}/stats", token, start, end, currency)
        except Exception:
            s = _empty_stats()
        records.append(_to_df_row(
            ad.get("name", ""), ad_id, adset_id,
            ad.get("status", "PAUSED"), "SNAP_AD", s,
        ))


    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).reset_index(drop=True)


# ── All-ads (creative analysis) ───────────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def fetch_snap_all_ads(token: str, account_id: str, start: str, end: str,
                       active_only: bool = True) -> pd.DataFrame:
    """
    Ad-level data for the entire Snap account — fully parallel + filtered.

    By default (active_only=True), only drills into ACTIVE campaigns/squads
    and returns ACTIVE+PAUSED ads. This is dramatically faster than fetching
    every archived/deleted entity.

    Wave 1: all campaigns (1 call).
    Wave 2: ad-squads per ACTIVE campaign (parallel, 30 workers).
    Wave 3: ads per ACTIVE squad (parallel, 30 workers).
    Wave 4: stats per ad (parallel, 50 workers).
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # ── Wave 1: campaigns ─────────────────────────────────────────────────────
    try:
        camp_resp = _get(f"/adaccounts/{account_id}/campaigns", token)
    except RuntimeError as e:
        if "TOKEN_EXPIRED" in str(e):
            _show_token_error()
        return pd.DataFrame()

    campaigns = []
    for c_wrap in camp_resp.get("campaigns", []):
        c = c_wrap.get("campaign", {})
        cid = c.get("id", "")
        if not cid:
            continue
        cstatus = c.get("status", "PAUSED")
        # Skip non-active campaigns when active_only is True (huge speedup)
        if active_only and cstatus != "ACTIVE":
            continue
        campaigns.append((cid, c.get("name", "")))

    if not campaigns:
        return pd.DataFrame()

    currency = get_snap_account_currency(token, account_id)

    # ── Wave 2: squads (parallel) ─────────────────────────────────────────────
    def _get_squads(camp_id_name):
        camp_id, camp_name = camp_id_name
        try:
            resp = _get(f"/campaigns/{camp_id}/adsquads", token)
            return camp_id, camp_name, resp.get("adsquads", [])
        except Exception:
            return camp_id, camp_name, []

    squad_jobs = []
    with ThreadPoolExecutor(max_workers=30) as ex:
        futs = {ex.submit(_get_squads, c): c for c in campaigns}
        for fut in as_completed(futs):
            camp_id, camp_name, adsquads = fut.result()
            for sq_wrap in adsquads:
                sq        = sq_wrap.get("adsquad", {})
                sq_id     = sq.get("id", "")
                sq_status = sq.get("status", "PAUSED")
                if not sq_id:
                    continue
                if active_only and sq_status != "ACTIVE":
                    continue
                squad_jobs.append((sq_id, sq.get("name", ""), camp_id, camp_name))

    if not squad_jobs:
        return pd.DataFrame()

    # ── Wave 3: ads per squad (parallel) ──────────────────────────────────────
    def _get_ads(sq_tuple):
        sq_id, sq_name, camp_id, camp_name = sq_tuple
        try:
            resp = _get(f"/adsquads/{sq_id}/ads", token)
            return [(ad_wrap.get("ad", {}), sq_id, sq_name, camp_id, camp_name)
                    for ad_wrap in resp.get("ads", [])
                    if ad_wrap.get("ad", {}).get("id")]
        except Exception:
            return []

    ad_jobs = []
    with ThreadPoolExecutor(max_workers=30) as ex:
        futs = [ex.submit(_get_ads, sq) for sq in squad_jobs]
        for fut in as_completed(futs):
            ad_jobs.extend(fut.result())

    if not ad_jobs:
        return pd.DataFrame()

    # ── Wave 4: stats per ad (high parallelism) ───────────────────────────────
    def _get_ad_stats(ad_tuple):
        ad, sq_id, sq_name, camp_id, camp_name = ad_tuple
        ad_id     = ad.get("id", "")
        ad_name   = ad.get("name", "")
        ad_status = ad.get("status", "PAUSED")
        try:
            s = _fetch_stats(f"/ads/{ad_id}/stats", token, start, end, currency)
        except Exception:
            s = _empty_stats()
        rec = _to_df_row(ad_name, ad_id, sq_id, ad_status, "SNAP_AD", s)
        rec["Ad Set Name"]   = sq_name
        rec["Ad Set ID"]     = sq_id
        rec["Campaign Name"] = camp_name
        rec["Campaign ID"]   = camp_id
        rec["thumbnail_url"] = ""
        return rec

    rows = []
    with ThreadPoolExecutor(max_workers=50) as ex:
        futs = [ex.submit(_get_ad_stats, job) for job in ad_jobs]
        for fut in as_completed(futs):
            try:
                rows.append(fut.result())
            except Exception as _exc:
                logging.getLogger(__name__).debug('suppressed: %s', _exc)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).reset_index(drop=True)
