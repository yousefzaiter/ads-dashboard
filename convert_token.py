"""
Convert a Meta short-lived access token to a long-lived one (60-day).
Reads credentials from .env, prints the long-lived token.

Usage:
    python3 convert_token.py
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

app_id      = os.getenv("META_APP_ID", "")
app_secret  = os.getenv("META_APP_SECRET", "")
short_token = os.getenv("META_ACCESS_TOKEN", "")

if not all([app_id, app_secret, short_token]):
    print("ERROR: META_APP_ID, META_APP_SECRET, META_ACCESS_TOKEN must be set in .env")
    raise SystemExit(1)

resp = requests.get(
    "https://graph.facebook.com/v20.0/oauth/access_token",
    params={
        "grant_type":        "fb_exchange_token",
        "client_id":         app_id,
        "client_secret":     app_secret,
        "fb_exchange_token": short_token,
    },
    timeout=15,
)

data = resp.json()
if "access_token" not in data:
    print(f"ERROR: {data}")
    raise SystemExit(1)

token   = data["access_token"]
expires = data.get("expires_in", 0)
days    = round(expires / 86400)

print(f"\n✅ Long-lived token ({days} days):\n")
print(token)
print(f"\nAdd this to .env as META_ACCESS_TOKEN=<token above>")
