"""
Meta Access Token lifecycle manager.

Flow:
  1. Load current token + app credentials from .env
  2. Call /debug_token to check validity and expiry
  3. If token expires in < 7 days (or is already invalid): exchange for new 60-day token
  4. Write the fresh token back to .env and update os.environ in-process

Run standalone:  python3 token_manager.py
Called from:     meta_ads_server.py on every import (once per Streamlit session)
Cron (VPS):      0 0 */7 * * cd /opt/ads-dashboard && python3 token_manager.py >> /var/log/token_refresh.log 2>&1
"""

import logging
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ENV_PATH    = Path(__file__).parent / ".env"
META_API    = "https://graph.facebook.com/v20.0"
REFRESH_THRESHOLD_DAYS = 7

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [token_manager] %(levelname)s %(message)s",
)
log = logging.getLogger("token_manager")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load():
    load_dotenv(dotenv_path=str(ENV_PATH), override=True)


def _env(key: str) -> str:
    return os.getenv(key, "")


def check_token_info(token: str, app_id: str = "", app_secret: str = "") -> dict:
    """
    Validate token by calling /me — works for user tokens AND system user tokens.
    Returns a normalised dict with 'is_valid', 'expires_at', 'type' keys.
    """
    resp = requests.get(
        f"{META_API}/me",
        params={"access_token": token, "fields": "id,name"},
        timeout=15,
    )
    data = resp.json()
    if "error" in data:
        return {"is_valid": False, "expires_at": 0, "type": "unknown"}
    # System user tokens and non-expiring tokens have no expiry — treat as permanent
    return {"is_valid": True, "expires_at": 0, "type": "system_user"}


def exchange_for_long_lived(token: str, app_id: str, app_secret: str) -> str | None:
    """Exchange any user token for a 60-day long-lived token."""
    resp = requests.get(
        f"{META_API}/oauth/access_token",
        params={
            "grant_type":       "fb_exchange_token",
            "client_id":        app_id,
            "client_secret":    app_secret,
            "fb_exchange_token": token,
        },
        timeout=15,
    )
    data = resp.json()
    if "access_token" in data:
        return data["access_token"]
    log.warning("Exchange failed: %s", data.get("error", data))
    return None


def save_token(new_token: str) -> None:
    """Overwrite META_ACCESS_TOKEN in .env and in the running process."""
    content = ENV_PATH.read_text()
    new_content = re.sub(r"META_ACCESS_TOKEN=\S*", f"META_ACCESS_TOKEN={new_token}", content)
    if "META_ACCESS_TOKEN=" not in new_content:
        new_content += f"\nMETA_ACCESS_TOKEN={new_token}\n"
    ENV_PATH.write_text(new_content)
    os.environ["META_ACCESS_TOKEN"] = new_token
    log.info("Token saved to .env and os.environ updated")


# ── Main ──────────────────────────────────────────────────────────────────────

def refresh_if_needed() -> dict:
    """
    Check the current token and refresh if it expires within REFRESH_THRESHOLD_DAYS.

    Returns a status dict:
      {
        "status":    "ok" | "refreshed" | "expired" | "no_credentials" | "error",
        "days_left": int,          # 9999 = never expires
        "message":   str,
      }
    """
    _load()
    token      = _env("META_ACCESS_TOKEN")
    app_id     = _env("META_APP_ID")
    app_secret = _env("META_APP_SECRET")

    if not token:
        return {"status": "no_credentials", "days_left": 0, "message": "META_ACCESS_TOKEN not set"}

    # ── Inspect token (works without app credentials) ─────────────────────────
    try:
        info = check_token_info(token)
    except Exception as exc:
        return {"status": "error", "days_left": 0, "message": f"Token check failed: {exc}"}

    if not info.get("is_valid"):
        log.warning("Token is invalid — attempting emergency exchange")
        new_token = exchange_for_long_lived(token, app_id, app_secret)
        if new_token:
            save_token(new_token)
            return {"status": "refreshed", "days_left": 60, "message": "Token was expired — refreshed to new 60-day token"}
        return {
            "status":    "expired",
            "days_left": 0,
            "message":   "Token expired and automatic refresh failed (app credentials may not match token issuer)",
        }

    expires_at = info.get("expires_at", 0)

    # Tokens issued as non-expiring (e.g. system-user tokens, page tokens)
    if expires_at == 0:
        return {"status": "ok", "days_left": 9999, "message": "Token does not expire"}

    days_left = max(0, int((expires_at - time.time()) / 86400))
    log.info("Token is valid — %d days remaining", days_left)

    if days_left <= REFRESH_THRESHOLD_DAYS:
        log.info("Threshold reached (%d days) — exchanging for new 60-day token", days_left)
        new_token = exchange_for_long_lived(token, app_id, app_secret)
        if new_token:
            save_token(new_token)
            return {"status": "refreshed", "days_left": 60,
                    "message": f"Token refreshed automatically ({days_left}d were remaining)"}
        log.error("Exchange failed — continuing with current token (%d days left)", days_left)
        return {"status": "error", "days_left": days_left,
                "message": f"Auto-refresh failed — token still valid for {days_left} days"}

    return {"status": "ok", "days_left": days_left,
            "message": f"Token valid for {days_left} more days"}


# ── Standalone run ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = refresh_if_needed()
    print(result)
    if result["status"] == "refreshed":
        print("✓ New token written to .env")
    elif result["status"] == "expired":
        print("✗ Token expired — paste a new token from Graph API Explorer into .env manually")
    elif result["status"] == "ok":
        print(f"✓ Token OK — {result['days_left']} days remaining")
    else:
        print(f"⚠ {result['message']}")
