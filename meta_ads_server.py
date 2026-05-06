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


# ── Low-level request ─────────────────────────────────────────────────────────

def _get(path: str, token: str, params: dict | None = None) -> dict:
    p = {"access_token": token, **(params or {})}
    resp = requests.get(f"{META_API_BASE}{path}", params=p, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"Meta API {resp.status_code}: {resp.text[:400]}")
    return resp.json()


# ── Token from env ────────────────────────────────────────────────────────────

def get_meta_token() -> str:
    token = os.getenv("META_ACCESS_TOKEN", "")
    if not token:
        raise ValueError("META_ACCESS_TOKEN not set in .env")
    return token


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
    except RuntimeError:
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
        st.error(f"Meta API error: {e}")
        return pd.DataFrame()
    return _insights_to_df(data.get("data", []), "adset_id", "adset_name", "META_ADSET")


@st.cache_data(ttl=300, show_spinner=False)
def fetch_meta_ads_list(token: str, adset_id: str, start: str, end: str) -> pd.DataFrame:
    """Ad-level insights for a given ad set."""
    try:
        data = _get(
            f"/{adset_id}/insights",
            token,
            {
                "fields":     "ad_id,ad_name,spend,impressions,clicks,ctr,cpc,actions,action_values",
                "level":      "ad",
                "time_range": f'{{"since":"{start}","until":"{end}"}}',
                "limit":      200,
            },
        )
    except RuntimeError as e:
        st.error(f"Meta API error: {e}")
        return pd.DataFrame()
    return _insights_to_df(data.get("data", []), "ad_id", "ad_name", "META_AD")
