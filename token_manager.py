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
    Validate token. Tries /debug_token first (gives type + expiry), falls back to /me.

    System User tokens have type='SYSTEM_USER' and expires_at=0 — treated as permanent.
    Returns a normalised dict with 'is_valid', 'expires_at', 'days_left', 'type' keys.
    """
    # ── Try /debug_token when app credentials match the token's issuing app ─────
    if app_id and app_secret:
        try:
            r = requests.get(
                f"{META_API}/debug_token",
                params={"input_token": token, "access_token": f"{app_id}|{app_secret}"},
                timeout=15,
            )
            body = r.json()
            if "data" in body:          # app_id matches — full metadata available
                d          = body["data"]
                is_valid   = bool(d.get("is_valid", False))
                token_type = str(d.get("type", "")).upper()
                expires_at = int(d.get("expires_at", 0) or 0)
                # Only true System User tokens are treated as permanent.
                # expires_at <= 0 alone is ambiguous (could be API hiccup) — signal unknown.
                if token_type == "SYSTEM_USER":
                    days_left = 9999
                elif expires_at <= 0:
                    days_left = None
                else:
                    days_left = max(0, int((expires_at - time.time()) / 86400))
                return {
                    "is_valid":   is_valid,
                    "expires_at": expires_at,
                    "days_left":  days_left if is_valid else 0,
                    "type":       token_type.lower() or "user",
                }
            # /debug_token returned an error (app_id mismatch, etc.) — fall through
        except Exception as e:
            log.warning("debug_token call failed, falling back to /me: %s", e)

    # ── Fall back to /me — works for any token type ───────────────────────────
    resp = requests.get(
        f"{META_API}/me",
        params={"access_token": token, "fields": "id,name"},
        timeout=15,
    )
    data = resp.json()
    if "error" in data:
        return {"is_valid": False, "expires_at": 0, "days_left": 0, "type": "unknown"}
    # /me succeeded but we can't determine expiry without /debug_token + app creds.
    # Return days_left=None to signal "valid but unknown expiry" — do not auto-refresh.
    return {"is_valid": True, "expires_at": 0, "days_left": None, "type": "unknown"}


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
    """Overwrite META_ACCESS_TOKEN in .env atomically and update the process env."""
    content = ENV_PATH.read_text() if ENV_PATH.exists() else ""
    new_content = re.sub(r"META_ACCESS_TOKEN=\S*", f"META_ACCESS_TOKEN={new_token}", content)
    if "META_ACCESS_TOKEN=" not in new_content:
        new_content = new_content.rstrip("\n") + f"\nMETA_ACCESS_TOKEN={new_token}\n"
    # Atomic write: write to a temp file in the same directory, then rename.
    # Prevents a partial .env if the process is killed mid-write.
    tmp_path = ENV_PATH.with_suffix(ENV_PATH.suffix + ".tmp")
    tmp_path.write_text(new_content)
    os.replace(tmp_path, ENV_PATH)
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

    # ── Inspect token — pass app creds so /debug_token returns real expiry ───────
    try:
        info = check_token_info(token, app_id, app_secret)
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
            "message":   (
                "Token expired and automatic refresh failed.\n"
                "Generate a new System User token in Meta Business Manager:\n"
                "  Business Settings → Users → System Users → Generate New Token\n"
                "Then update META_ACCESS_TOKEN in .env"
            ),
        }

    days_left = info.get("days_left")  # None = valid but expiry unknown (no app creds)
    log.info("Token is valid — %s days remaining",
             "∞" if days_left is None or days_left >= 9999 else days_left)

    # Non-expiring (System User) or expiry unknown without app creds — skip refresh
    if days_left is None or days_left >= 9999:
        label = "System User (non-expiring)" if info.get("type") == "system_user" else "expiry unknown — add META_APP_ID/SECRET for full tracking"
        return {"status": "ok", "days_left": days_left, "message": f"Token valid — {label}"}

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
            "message": f"Token valid — {days_left} days remaining"}


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
