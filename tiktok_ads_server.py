"""
TikTok Ads data fetcher — Marketing API v1.3.
Returns structured campaign data matching the Google/Meta/Snap schema used by dashboard.py.

Spend values from TikTok API are already in account currency (no micro-currency division).
"""
import json
import os

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
    override=True,
)

TIKTOK_API  = "https://business-api.tiktok.com/open_api/v1.3"
USD_TO_SAR  = 3.75

_REPORT_METRICS = [
    "spend", "impressions", "clicks", "ctr", "cpm", "cpc",
    "conversion", "cost_per_conversion",
    "complete_payment", "complete_payment_roas",
    "video_play_actions", "video_watched_2s", "video_watched_6s",
    "video_views_p100",
]

# TikTok campaign/adgroup status → dashboard label
_STATUS_MAP = {
    "CAMPAIGN_STATUS_ENABLE":    "ENABLED",
    "CAMPAIGN_STATUS_DISABLE":   "PAUSED",
    "CAMPAIGN_STATUS_DELETE":    "REMOVED",
    "ADGROUP_STATUS_ENABLE":     "ENABLED",
    "ADGROUP_STATUS_DISABLE":    "PAUSED",
    "ADGROUP_STATUS_DELETE":     "REMOVED",
    "AD_STATUS_ENABLE":          "ENABLED",
    "AD_STATUS_DISABLE":         "PAUSED",
    "AD_STATUS_DELETE":          "REMOVED",
    "ENABLE":                    "ENABLED",
    "DISABLE":                   "PAUSED",
    "DELETE":                    "REMOVED",
}


# ── Auth helpers ───────────────────────────────────────────────────────────────

def get_tiktok_token() -> str:
    return os.getenv("TIKTOK_ACCESS_TOKEN", "")


def get_headers(access_token: str) -> dict:
    """Return standard TikTok API headers."""
    return {
        "Access-Token":  access_token,
        "Content-Type":  "application/json",
    }


# ── Low-level request ──────────────────────────────────────────────────────────

def _get(path: str, token: str, params: dict | None = None) -> dict:
    """GET request with JSON-encoded list params. Raises RuntimeError on failure."""
    # TikTok requires list/dict params encoded as JSON strings in the query string
    encoded: dict = {}
    for k, v in (params or {}).items():
        encoded[k] = json.dumps(v) if isinstance(v, (list, dict)) else v

    resp = requests.get(
        f"{TIKTOK_API}{path}",
        headers=get_headers(token),
        params=encoded,
        timeout=20,
    )
    if resp.status_code == 401:
        raise RuntimeError("TOKEN_EXPIRED")
    if resp.status_code != 200:
        raise RuntimeError(f"TikTok API HTTP {resp.status_code}: {resp.text[:300]}")

    body = resp.json()
    code = body.get("code", -1)
    if code == 40001:
        raise RuntimeError("TOKEN_EXPIRED")
    if code != 0:
        raise RuntimeError(f"TikTok API error {code}: {body.get('message', '')}")
    return body


def _show_token_error() -> None:
    st.error(
        "🔒 انتهت صلاحية التوكن لـ TikTok.  "
        "يرجى تحديث TIKTOK_ACCESS_TOKEN في ملف .env"
    )


# ── Currency helpers ───────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def get_tiktok_account_currency(token: str, advertiser_id: str) -> str:
    """Return the billing currency for a TikTok advertiser account."""
    try:
        body = _get("/advertiser/info/", token, {
            "advertiser_ids": [advertiser_id],
            "fields": ["currency"],
        })
        items = body.get("data", {}).get("list", [])
        if items:
            return str(items[0].get("currency", "SAR")).upper()
    except Exception:
        pass
    return "SAR"


def _to_sar(amount: float, currency: str) -> float:
    if currency == "USD":
        return round(amount * USD_TO_SAR, 2)
    return amount


# ── Raw API functions (as requested) ──────────────────────────────────────────

def get_campaigns(advertiser_id: str, access_token: str) -> list[dict]:
    """Fetch all campaigns for an advertiser. Returns raw list from API."""
    try:
        body = _get("/campaign/get/", access_token, {
            "advertiser_id": advertiser_id,
            "fields": [
                "campaign_id", "campaign_name", "status",
                "objective_type", "budget", "budget_mode",
            ],
            "page_size": 1000,
        })
        return body.get("data", {}).get("list", [])
    except Exception:
        return []


def get_adsets(advertiser_id: str, access_token: str,
               campaign_id: str | None = None) -> list[dict]:
    """Fetch ad groups for an advertiser, optionally filtered to one campaign."""
    params: dict = {
        "advertiser_id": advertiser_id,
        "fields": [
            "adgroup_id", "adgroup_name", "campaign_id",
            "status", "budget", "budget_mode",
        ],
        "page_size": 1000,
    }
    if campaign_id:
        params["campaign_ids"] = [campaign_id]
    try:
        body = _get("/adgroup/get/", access_token, params)
        return body.get("data", {}).get("list", [])
    except Exception:
        return []


def get_ads(advertiser_id: str, access_token: str,
            adgroup_id: str | None = None) -> list[dict]:
    """Fetch ads for an advertiser, optionally filtered to one ad group."""
    params: dict = {
        "advertiser_id": advertiser_id,
        "fields": [
            "ad_id", "ad_name", "adgroup_id", "campaign_id",
            "status", "ad_format",
        ],
        "page_size": 1000,
    }
    if adgroup_id:
        params["adgroup_ids"] = [adgroup_id]
    try:
        body = _get("/ad/get/", access_token, params)
        return body.get("data", {}).get("list", [])
    except Exception:
        return []


def get_campaign_stats(advertiser_id: str, access_token: str,
                       start_date: str, end_date: str) -> list[dict]:
    """
    Fetch campaign-level stats for a date range.
    Returns raw list: [{dimensions: {campaign_id}, metrics: {...}}, ...]

    Metrics included: spend, impressions, clicks, ctr, cpm, cpc,
    conversions, cost_per_conversion, video_play_actions,
    video_watched_2s, video_watched_6s.
    """
    try:
        body = _get("/report/integrated/get/", access_token, {
            "advertiser_id": advertiser_id,
            "report_type":   "BASIC",
            "data_level":    "AUCTION_CAMPAIGN",
            "dimensions":    ["campaign_id"],
            "metrics":       _REPORT_METRICS,
            "start_date":    start_date,
            "end_date":      end_date,
            "page_size":     1000,
        })
        return body.get("data", {}).get("list", [])
    except Exception:
        return []


# ── Internal helpers ───────────────────────────────────────────────────────────

def _safe_float(val) -> float:
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(val) -> int:
    try:
        return int(float(val or 0))
    except (TypeError, ValueError):
        return 0


def _parse_metrics(m: dict, currency: str = "SAR") -> dict:
    """Convert a TikTok metrics dict to the dashboard's internal stats schema."""
    spend       = _to_sar(_safe_float(m.get("spend")), currency)
    impressions = _safe_int(m.get("impressions"))
    clicks      = _safe_int(m.get("clicks"))
    ctr         = _safe_float(m.get("ctr"))          # already a % from API
    cpc         = _to_sar(_safe_float(m.get("cpc")), currency)
    conv        = _safe_float(m.get("conversion", 0))
    cpa         = _to_sar(_safe_float(m.get("cost_per_conversion")), currency)
    purchases   = _safe_float(m.get("complete_payment", 0))
    cp_roas     = _safe_float(m.get("complete_payment_roas", 0))
    video_plays = _safe_int(m.get("video_play_actions"))
    v2s         = _safe_int(m.get("video_watched_2s"))
    v6s         = _safe_int(m.get("video_watched_6s"))
    v100        = _safe_int(m.get("video_views_p100"))

    # Conv. Value derived from ROAS × spend (TikTok reports purchase ROAS)
    conv_value  = _to_sar(round(cp_roas * _safe_float(m.get("spend")), 2), currency) \
                  if cp_roas and m.get("spend") else 0.0
    roas        = round(cp_roas, 2) if cp_roas else 0.0
    vvr         = round(v6s / impressions * 100, 2) if impressions > 0 else 0.0

    return {
        "impressions": impressions,
        "clicks":      clicks,
        "spend":       round(spend, 2),
        "ctr":         round(ctr, 4),
        "cpc":         round(cpc, 2),
        "conversions": conv,
        "conv_value":  round(conv_value, 2),
        "cpa":         round(cpa, 2),
        "roas":        roas,
        "video_views": video_plays,
        "vvr":         vvr,
    }


def _empty_metrics() -> dict:
    return _parse_metrics({})


def _to_df_row(name: str, entity_id: str, parent_id: str,
               status: str, type_: str, m: dict) -> dict:
    return {
        "ID":          entity_id,
        "Campaign":    name,
        "Campaign ID": parent_id,
        "Status":      _STATUS_MAP.get(status, status),
        "Type":        type_,
        "Impressions": m["impressions"],
        "Clicks":      m["clicks"],
        "Cost":        m["spend"],
        "CTR":         m["ctr"],
        "Avg CPC":     m["cpc"],
        "Conversions": m["conversions"],
        "Conv. Value": m["conv_value"],
        "CPA":         m["cpa"],
        "ROAS":        m["roas"],
        "Imp. Share":  None,
        "Video Views": m["video_views"],
        "VVR":         m["vvr"],
    }


def _report_index(token: str, advertiser_id: str,
                  data_level: str, dimensions: list[str],
                  start: str, end: str,
                  filter_ids: list[str] | None = None) -> dict[str, dict]:
    """
    Fetch a report and return a dict keyed by the first dimension value.
    E.g. data_level=AUCTION_CAMPAIGN, dimensions=["campaign_id"]
    → {"camp_id_1": metrics_dict, ...}
    """
    params: dict = {
        "advertiser_id": advertiser_id,
        "report_type":   "BASIC",
        "data_level":    data_level,
        "dimensions":    dimensions,
        "metrics":       _REPORT_METRICS,
        "start_date":    start,
        "end_date":      end,
        "page_size":     1000,
    }
    if filter_ids and len(dimensions) == 1:
        # e.g. campaign_ids / adgroup_ids
        key = dimensions[0] + "s"          # campaign_id → campaign_ids
        params[key] = filter_ids

    try:
        body   = _get("/report/integrated/get/", token, params)
        rows   = body.get("data", {}).get("list", [])
    except Exception:
        return {}

    idx_key = dimensions[0]
    return {
        str(row["dimensions"].get(idx_key, "")): row.get("metrics", {})
        for row in rows
        if row.get("dimensions")
    }


# ── Advertiser info ────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_tiktok_advertiser_name(token: str, advertiser_id: str) -> str:
    """Return the advertiser display name, or the ID on failure."""
    try:
        body  = _get("/advertiser/info/", token, {
            "advertiser_ids": [advertiser_id],
            "fields": ["advertiser_name"],
        })
        items = body.get("data", {}).get("list", [])
        if items:
            return str(items[0].get("advertiser_name", advertiser_id))
    except Exception:
        pass
    return advertiser_id


# ── Campaign performance ───────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def fetch_tiktok_campaigns(token: str, advertiser_id: str,
                           start: str, end: str,
                           show_paused: bool = False) -> pd.DataFrame:
    """Campaign-level performance. Skips PAUSED by default."""
    campaigns = get_campaigns(advertiser_id, token)
    if not campaigns:
        return pd.DataFrame()

    active = [
        c for c in campaigns
        if show_paused or _STATUS_MAP.get(c.get("status", ""), "") == "ENABLED"
    ]
    if not active:
        return pd.DataFrame()

    camp_ids   = [str(c["campaign_id"]) for c in active]
    stats_idx  = _report_index(
        token, advertiser_id,
        "AUCTION_CAMPAIGN", ["campaign_id"],
        start, end, camp_ids,
    )
    currency = get_tiktok_account_currency(token, advertiser_id)

    records = []
    for c in active:
        cid    = str(c["campaign_id"])
        raw_m  = stats_idx.get(cid, {})
        m      = _parse_metrics(raw_m, currency)
        records.append(_to_df_row(
            c.get("campaign_name", cid), cid, advertiser_id,
            c.get("status", ""), "TIKTOK", m,
        ))

    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).reset_index(drop=True)


# ── Daily data ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def fetch_tiktok_daily(token: str, advertiser_id: str,
                       start: str, end: str) -> pd.DataFrame:
    """Daily breakdown of spend/clicks/conversions across all campaigns."""
    currency = get_tiktok_account_currency(token, advertiser_id)
    try:
        body = _get("/report/integrated/get/", token, {
            "advertiser_id": advertiser_id,
            "report_type":   "BASIC",
            "data_level":    "AUCTION_ADVERTISER",
            "dimensions":    ["stat_time_day"],
            "metrics":       [
                "spend", "impressions", "clicks",
                "conversion", "complete_payment_roas",
            ],
            "start_date":    start,
            "end_date":      end,
            "page_size":     1000,
        })
        rows = body.get("data", {}).get("list", [])
    except Exception:
        return pd.DataFrame()

    records = []
    for row in rows:
        day = str(row.get("dimensions", {}).get("stat_time_day", ""))[:10]
        if not day:
            continue
        m          = row.get("metrics", {})
        spend      = _to_sar(_safe_float(m.get("spend")), currency)
        conv_value = _to_sar(
            _safe_float(m.get("complete_payment_roas", 0)) * _safe_float(m.get("spend", 0)),
            currency,
        )
        records.append({
            "Date":        day,
            "Impressions": _safe_int(m.get("impressions")),
            "Clicks":      _safe_int(m.get("clicks")),
            "Cost":        round(spend, 2),
            "Conversions": _safe_float(m.get("conversion", 0)),
            "Conv. Value": round(conv_value, 2),
        })

    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(sorted(records, key=lambda r: r["Date"]))
    df["Date"] = pd.to_datetime(df["Date"])
    return df


# ── Ad groups (ad sets) ────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def fetch_tiktok_adsets(token: str, advertiser_id: str,
                        campaign_id: str,
                        start: str, end: str) -> pd.DataFrame:
    """Ad-group-level insights for a campaign."""
    adgroups = get_adsets(advertiser_id, token, campaign_id=campaign_id)
    if not adgroups:
        return pd.DataFrame()

    ag_ids    = [str(ag["adgroup_id"]) for ag in adgroups]
    stats_idx = _report_index(
        token, advertiser_id,
        "AUCTION_ADGROUP", ["adgroup_id"],
        start, end, ag_ids,
    )
    currency = get_tiktok_account_currency(token, advertiser_id)

    records = []
    for ag in adgroups:
        ag_id  = str(ag["adgroup_id"])
        raw_m  = stats_idx.get(ag_id, {})
        m      = _parse_metrics(raw_m, currency)
        records.append(_to_df_row(
            ag.get("adgroup_name", ag_id), ag_id, campaign_id,
            ag.get("status", ""), "TIKTOK_ADSET", m,
        ))

    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).reset_index(drop=True)


# ── Ads ────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def fetch_tiktok_ads(token: str, advertiser_id: str,
                     adgroup_id: str,
                     start: str, end: str) -> pd.DataFrame:
    """Ad-level insights for an ad group."""
    ads = get_ads(advertiser_id, token, adgroup_id=adgroup_id)
    if not ads:
        return pd.DataFrame()

    ad_ids    = [str(ad["ad_id"]) for ad in ads]
    stats_idx = _report_index(
        token, advertiser_id,
        "AUCTION_AD", ["ad_id"],
        start, end, ad_ids,
    )
    currency = get_tiktok_account_currency(token, advertiser_id)

    records = []
    for ad in ads:
        ad_id  = str(ad["ad_id"])
        raw_m  = stats_idx.get(ad_id, {})
        m      = _parse_metrics(raw_m, currency)
        records.append(_to_df_row(
            ad.get("ad_name", ad_id), ad_id, adgroup_id,
            ad.get("status", ""), "TIKTOK_AD", m,
        ))

    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).reset_index(drop=True)
