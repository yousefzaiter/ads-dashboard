"""
Meta Ads data fetcher — Marketing API v20.
Returns structured campaign data matching the Google Ads schema used by dashboard.py.
"""
import os
import requests
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)

META_API_BASE = "https://graph.facebook.com/v20.0"

# ── Auto-refresh token on import ──────────────────────────────────────────────
_token_status: dict = {"status": "unknown", "days_left": 0, "message": ""}
try:
    from token_manager import refresh_if_needed as _refresh_token
    _token_status = _refresh_token()
except Exception as _tm_err:
    _token_status = {"status": "error", "days_left": 0, "message": str(_tm_err)}


# ── Low-level request ─────────────────────────────────────────────────────────

_EXPIRED_PHRASES = ("Session has expired", "Error validating access token",
                    "Invalid OAuth access token", "OAuthException")

_MSG_EXPIRED_AR = (
    "جاري تحديث صلاحية الوصول لميتا...  "
    "انتهت صلاحية التوكن. يرجى نسخ توكن جديد من "
    "[Graph API Explorer](https://developers.facebook.com/tools/explorer/) "
    "وتحديثه في لوحة الإعدادات."
)


def _is_token_error(text: str) -> bool:
    return any(p in text for p in _EXPIRED_PHRASES)


def _show_token_error() -> None:
    st.error(_MSG_EXPIRED_AR)


def _get(path: str, token: str, params: dict | None = None) -> dict:
    p = {"access_token": token, **(params or {})}
    resp = requests.get(f"{META_API_BASE}{path}", params=p, timeout=20)
    if resp.status_code != 200:
        msg = resp.text[:400]
        if _is_token_error(msg):
            raise RuntimeError("TOKEN_EXPIRED")
        raise RuntimeError(f"Meta API {resp.status_code}: {msg}")
    return resp.json()


# ── Token from env ────────────────────────────────────────────────────────────

def get_meta_token() -> str:
    token = os.getenv("META_ACCESS_TOKEN", "")
    if not token:
        raise ValueError("META_ACCESS_TOKEN not set in .env")
    return token


def get_token_status() -> dict:
    """Return the token status dict computed at import time."""
    return _token_status


# ── Ad accounts ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_meta_accounts(token: str) -> list[dict]:
    """Return list of {id, name} for all ad accounts the token can access."""
    data = _get("/me/adaccounts", token, {"fields": "id,name,account_status", "limit": 100})
    accounts = []
    for acct in data.get("data", []):
        if acct.get("account_status") == 1:  # 1 = ACTIVE
            accounts.append({
                "id":   acct["id"],          # e.g. "act_123456789"
                "name": acct.get("name", acct["id"]),
            })
    return accounts


# ── Campaign performance ───────────────────────────────────────────────────────

_INSIGHT_FIELDS = ",".join([
    "campaign_id", "campaign_name",
    "spend", "impressions", "clicks", "ctr", "cpc",
    "actions", "action_values",
])

_PURCHASE_TYPES = {
    "purchase",
    "offsite_conversion.fb_pixel_purchase",
    "omni_purchase",
}


def _extract_action(items: list[dict], types: set[str]) -> float:
    """Sum action values for the given action types."""
    return sum(
        float(item.get("value", 0))
        for item in (items or [])
        if item.get("action_type") in types
    )


@st.cache_data(ttl=300, show_spinner=False)
def fetch_meta_campaigns(token: str, account_id: str, start: str, end: str) -> pd.DataFrame:
    """
    Fetch campaign-level insights for an ad account.
    Returns DataFrame with same columns as Google Ads campaign data.
    """
    try:
        data = _get(
            f"/{account_id}/insights",
            token,
            {
                "fields":     _INSIGHT_FIELDS,
                "level":      "campaign",
                "time_range": f'{{"since":"{start}","until":"{end}"}}',
                "limit":      200,
            },
        )
    except RuntimeError as e:
        if "TOKEN_EXPIRED" in str(e):
            _show_token_error()
        else:
            st.error(f"Meta API error: {e}")
        return pd.DataFrame()

    records = []
    for row in data.get("data", []):
        spend       = float(row.get("spend", 0) or 0)
        impressions = int(row.get("impressions", 0) or 0)
        clicks      = int(row.get("clicks", 0) or 0)
        ctr         = float(row.get("ctr", 0) or 0)
        cpc         = float(row.get("cpc", 0) or 0)
        actions     = row.get("actions", [])
        action_vals = row.get("action_values", [])

        conversions    = _extract_action(actions, _PURCHASE_TYPES)
        conv_value     = _extract_action(action_vals, _PURCHASE_TYPES)
        roas           = round(conv_value / spend, 2) if spend > 0 else 0.0
        cpa            = round(spend / conversions, 2) if conversions > 0 else 0.0

        records.append({
            "Campaign":    row.get("campaign_name", ""),
            "Campaign ID": row.get("campaign_id", ""),
            "Status":      "ENABLED",       # insights only returns active campaigns
            "Type":        "META",
            "Impressions": impressions,
            "Clicks":      clicks,
            "Cost":        round(spend, 2),
            "CTR":         round(ctr, 4),   # Meta returns fraction (0.0234 = 2.34%)
            "Avg CPC":     round(cpc, 2),
            "Conversions": round(conversions, 1),
            "Conv. Value": round(conv_value, 2),
            "CPA":         cpa,
            "ROAS":        roas,
            "Imp. Share":  None,
        })

    df = pd.DataFrame(records)
    if not df.empty:
        # Meta CTR comes as percent already (e.g. 2.34), not fraction — normalise
        # Actually Meta v20 returns it as percentage string like "2.34"
        # The Google side uses CTR as a percentage too, so it's consistent
        df["CTR"] = df["CTR"].astype(float)
    return df


# ── Daily data ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def fetch_meta_daily(token: str, account_id: str, start: str, end: str) -> pd.DataFrame:
    """Daily breakdown for the account (all campaigns combined)."""
    try:
        data = _get(
            f"/{account_id}/insights",
            token,
            {
                "fields":     "spend,impressions,clicks,actions,action_values",
                "level":      "account",
                "time_increment": 1,
                "time_range": f'{{"since":"{start}","until":"{end}"}}',
                "limit":      90,
            },
        )
    except RuntimeError as e:
        if "TOKEN_EXPIRED" in str(e):
            _show_token_error()
        return pd.DataFrame()

    records = []
    for row in data.get("data", []):
        spend      = float(row.get("spend", 0) or 0)
        conv_value = _extract_action(row.get("action_values", []), _PURCHASE_TYPES)
        conv       = _extract_action(row.get("actions", []), _PURCHASE_TYPES)
        records.append({
            "Date":        row.get("date_start", ""),
            "Impressions": int(row.get("impressions", 0) or 0),
            "Clicks":      int(row.get("clicks", 0) or 0),
            "Cost":        round(spend, 2),
            "Conversions": round(conv, 1),
            "Conv. Value": round(conv_value, 2),
        })

    df = pd.DataFrame(records)
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"])
    return df


# ── Ad-set drill-down ─────────────────────────────────────────────────────────

def _insights_to_df(rows: list[dict], id_key: str, name_key: str, entity_type: str) -> pd.DataFrame:
    records = []
    for row in rows:
        spend       = float(row.get("spend", 0) or 0)
        impressions = int(row.get("impressions", 0) or 0)
        clicks      = int(row.get("clicks", 0) or 0)
        ctr         = float(row.get("ctr", 0) or 0)
        cpc         = float(row.get("cpc", 0) or 0)
        actions     = row.get("actions", [])
        action_vals = row.get("action_values", [])
        conversions = _extract_action(actions, _PURCHASE_TYPES)
        conv_value  = _extract_action(action_vals, _PURCHASE_TYPES)
        roas        = round(conv_value / spend, 2) if spend > 0 else 0.0
        cpa         = round(spend / conversions, 2) if conversions > 0 else 0.0
        records.append({
            "ID":          row.get(id_key, ""),
            "Campaign":    row.get(name_key, ""),
            "Campaign ID": "",
            "Status":      "ENABLED",
            "Type":        entity_type,
            "Impressions": impressions,
            "Clicks":      clicks,
            "Cost":        round(spend, 2),
            "CTR":         round(ctr, 4),
            "Avg CPC":     round(cpc, 2),
            "Conversions": round(conversions, 1),
            "Conv. Value": round(conv_value, 2),
            "CPA":         cpa,
            "ROAS":        roas,
            "Imp. Share":  None,
        })
    return pd.DataFrame(records)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_meta_adsets(token: str, campaign_id: str, start: str, end: str) -> pd.DataFrame:
    """Ad-set-level insights for a given campaign."""
    try:
        data = _get(
            f"/{campaign_id}/insights",
            token,
            {
                "fields":     "adset_id,adset_name,spend,impressions,clicks,ctr,cpc,actions,action_values",
                "level":      "adset",
                "time_range": f'{{"since":"{start}","until":"{end}"}}',
                "limit":      200,
            },
        )
    except RuntimeError as e:
        if "TOKEN_EXPIRED" in str(e):
            _show_token_error()
        else:
            st.error(f"Meta API error: {e}")
        return pd.DataFrame()
    return _insights_to_df(data.get("data", []), "adset_id", "adset_name", "META_ADSET")


_AD_DEEP_FIELDS = ",".join([
    "ad_id", "ad_name",
    "spend", "impressions", "clicks", "ctr", "cpc", "reach",
    "actions", "action_values",
    "video_thruplay_watched_actions",
    "video_p25_watched_actions",
    "video_p50_watched_actions",
    "video_p75_watched_actions",
    "outbound_clicks",
    "outbound_clicks_ctr",
])


def _sum_video(items: list[dict]) -> float:
    return sum(float(x.get("value", 0)) for x in (items or []))


@st.cache_data(ttl=300, show_spinner=False)
def fetch_meta_ads_list(token: str, adset_id: str, start: str, end: str) -> pd.DataFrame:
    """Ad-level insights with extended video and engagement metrics."""
    try:
        data = _get(
            f"/{adset_id}/insights",
            token,
            {
                "fields":     _AD_DEEP_FIELDS,
                "level":      "ad",
                "time_range": f'{{"since":"{start}","until":"{end}"}}',
                "limit":      200,
            },
        )
    except RuntimeError as e:
        if "TOKEN_EXPIRED" in str(e):
            _show_token_error()
        else:
            st.error(f"Meta API error: {e}")
        return pd.DataFrame()

    records = []
    for row in data.get("data", []):
        spend       = float(row.get("spend", 0) or 0)
        impressions = int(row.get("impressions", 0) or 0)
        clicks      = int(row.get("clicks", 0) or 0)
        ctr         = float(row.get("ctr", 0) or 0)
        cpc         = float(row.get("cpc", 0) or 0)
        reach       = int(row.get("reach", 0) or 0)
        actions     = row.get("actions", [])
        action_vals = row.get("action_values", [])

        conversions = _extract_action(actions, _PURCHASE_TYPES)
        conv_value  = _extract_action(action_vals, _PURCHASE_TYPES)
        roas        = round(conv_value / spend, 2) if spend > 0 else 0.0
        cpa         = round(spend / conversions, 2) if conversions > 0 else 0.0
        conv_rate   = round(conversions / clicks * 100, 2) if clicks > 0 else 0.0

        # Video metrics
        thruplay  = _sum_video(row.get("video_thruplay_watched_actions", []))
        p25       = _sum_video(row.get("video_p25_watched_actions", []))
        p75       = _sum_video(row.get("video_p75_watched_actions", []))
        has_video = p25 > 0 or thruplay > 0

        hook_val  = thruplay if thruplay > 0 else p25
        hook_rate = round(hook_val / impressions * 100, 1) if impressions > 0 and has_video else 0.0
        hold_rate = round(p75 / p25 * 100, 1) if p25 > 0 else 0.0

        # Engagement metrics
        frequency = round(impressions / reach, 2) if reach > 0 else 0.0
        cpm       = round(spend / impressions * 1000, 2) if impressions > 0 else 0.0
        ob_clicks = sum(float(x.get("value", 0)) for x in row.get("outbound_clicks", []))
        lp_ctr    = round(ob_clicks / impressions * 100, 2) if impressions > 0 else 0.0

        records.append({
            "ID":          row.get("ad_id", ""),
            "Campaign":    row.get("ad_name", ""),
            "Campaign ID": "",
            "Status":      "ENABLED",
            "Type":        "META_AD",
            "Impressions": impressions,
            "Clicks":      clicks,
            "Cost":        round(spend, 2),
            "CTR":         round(ctr, 4),
            "Avg CPC":     round(cpc, 2),
            "Conversions": round(conversions, 1),
            "Conv. Value": round(conv_value, 2),
            "CPA":         cpa,
            "ROAS":        roas,
            "Imp. Share":  None,
            "Reach":       reach,
            "Frequency":   frequency,
            "Hook Rate":   hook_rate,
            "Hold Rate":   hold_rate,
            "CPM":         cpm,
            "LP CTR":      lp_ctr,
            "Conv. Rate":  conv_rate,
            "Has Video":   has_video,
        })

    return pd.DataFrame(records)


# ── All ads for Creative Analysis page ───────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def fetch_meta_all_ads(token: str, account_id: str, start: str, end: str) -> pd.DataFrame:
    """
    Ad-level data for the entire Meta ad account.

    Strategy:
      1. List ALL ads from /{account_id}/ads (with effective_status + creative).
         This includes ads with NO spend in the period — so all running ads show.
      2. Fetch insights at ad-level for the date range, build {ad_id: metrics} dict.
      3. Iterate over the ads list (not insights), merge metrics from the dict.
         Ads with no insights data show with zeros.

    Filters out ARCHIVED/DELETED to keep volume manageable.
    """
    from concurrent.futures import ThreadPoolExecutor

    # ── Both calls in parallel — saves one round-trip ─────────────────────────
    def _fetch_ads_list():
        try:
            # First try with creative field expansion
            try:
                return _get(
                    f"/{account_id}/ads",
                    token,
                    {
                        "fields": ("id,name,effective_status,adset_id,adset_name,"
                                   "campaign_id,campaign_name,"
                                   "creative{thumbnail_url,image_url,object_story_spec}"),
                        "limit":  500,
                        # Only ads that are currently active or paused — not archived/deleted
                        "filtering": '[{"field":"effective_status","operator":"IN",'
                                     '"value":["ACTIVE","PAUSED","CAMPAIGN_PAUSED",'
                                     '"ADSET_PAUSED","DISAPPROVED","PENDING_REVIEW"]}]',
                    },
                )
            except RuntimeError as e:
                if "500" in str(e) or "reduce" in str(e).lower():
                    # If request too large, fetch without creative field
                    return _get(
                        f"/{account_id}/ads",
                        token,
                        {
                            "fields": ("id,name,effective_status,adset_id,adset_name,"
                                       "campaign_id,campaign_name"),
                            "limit":  500,
                            "filtering": '[{"field":"effective_status","operator":"IN",'
                                         '"value":["ACTIVE","PAUSED","CAMPAIGN_PAUSED",'
                                         '"ADSET_PAUSED","DISAPPROVED","PENDING_REVIEW"]}]',
                        },
                    )
                else:
                    raise
        except Exception:
            return {"data": []}

    def _fetch_insights():
        try:
            return _get(
                f"/{account_id}/insights",
                token,
                {
                    "fields": ("ad_id,spend,impressions,clicks,ctr,cpc,"
                               "reach,frequency,actions,action_values"),
                    "level":  "ad",
                    "time_range": f'{{"since":"{start}","until":"{end}"}}',
                    "limit":  500,
                },
            )
        except Exception:
            return {"data": []}

    with ThreadPoolExecutor(max_workers=2) as ex:
        f_ads      = ex.submit(_fetch_ads_list)
        f_insights = ex.submit(_fetch_insights)
        ads_resp   = f_ads.result()
        ins_resp   = f_insights.result()

    ad_rows = ads_resp.get("data", [])
    if not ad_rows:
        return pd.DataFrame()

    # Build insights lookup: ad_id → metrics
    ins_map: dict[str, dict] = {}
    for row in ins_resp.get("data", []):
        aid = row.get("ad_id", "")
        if aid:
            ins_map[aid] = row

    # Build records — iterate over ads list so ALL active ads appear
    records = []
    for ad in ad_rows:
        ad_id      = ad.get("id", "")
        eff_status = ad.get("effective_status", "PAUSED")
        # ACTIVE = currently delivering → ENABLED for filter
        status = "ENABLED" if eff_status == "ACTIVE" else "PAUSED"

        # Extract creative thumbnail (try multiple fields for different ad types)
        creative = ad.get("creative", {}) or {}
        url = (creative.get("thumbnail_url")
               or creative.get("image_url")
               or "")
        if not url:
            spec = creative.get("object_story_spec", {}) or {}
            url = (spec.get("link_data", {}).get("picture")
                   or spec.get("link_data", {}).get("image_url")
                   or spec.get("video_data", {}).get("image_url")
                   or "")

        # Look up insights for this ad
        ins = ins_map.get(ad_id, {})
        spend       = float(ins.get("spend", 0) or 0)
        impressions = int(ins.get("impressions", 0) or 0)
        clicks      = int(ins.get("clicks", 0) or 0)
        ctr         = float(ins.get("ctr", 0) or 0)
        cpc         = float(ins.get("cpc", 0) or 0)
        reach       = int(ins.get("reach", 0) or 0)
        frequency   = float(ins.get("frequency", 0) or 0)
        actions     = ins.get("actions", [])
        action_vals = ins.get("action_values", [])
        conversions = _extract_action(actions, _PURCHASE_TYPES)
        conv_value  = _extract_action(action_vals, _PURCHASE_TYPES)
        roas        = round(conv_value / spend, 2)         if spend > 0       else 0.0
        cpa         = round(spend / conversions, 2)        if conversions > 0 else 0.0
        cpm         = round(spend / impressions * 1000, 2) if impressions > 0 else 0.0

        records.append({
            "ID":            ad_id,
            "Campaign":      ad.get("name", ""),
            "Ad Set Name":   ad.get("adset_name", ""),
            "Ad Set ID":     ad.get("adset_id", ""),
            "Campaign Name": ad.get("campaign_name", ""),
            "Campaign ID":   ad.get("campaign_id", ""),
            "Status":        status,
            "Type":          "META_AD",
            "Impressions":   impressions,
            "Clicks":        clicks,
            "Cost":          round(spend, 2),
            "CTR":           round(ctr, 4),
            "Avg CPC":       round(cpc, 2),
            "Conversions":   round(conversions, 1),
            "Conv. Value":   round(conv_value, 2),
            "CPA":           cpa,
            "ROAS":          roas,
            "Reach":         reach,
            "Frequency":     frequency,
            "CPM":           cpm,
            "thumbnail_url": url,
        })

    return pd.DataFrame(records)
