#!/usr/bin/env python3
"""Exchange a Google OAuth authorization code for an access + refresh token.

Usage:
    GOOGLE_ADS_CLIENT_ID=...  GOOGLE_ADS_CLIENT_SECRET=... \\
    AUTH_CODE=4/0Aeo...  REDIRECT_URI=https://developers.google.com/oauthplayground \\
    python3 scripts/exchange_oauth_code.py

Notes:
  - The code is single-use and expires in ~10 minutes.
  - The client_id + client_secret + redirect_uri must match the ones used
    when the code was issued, otherwise Google returns invalid_grant.
"""
from __future__ import annotations

import json
import os
import sys

import requests


def main() -> int:
    client_id     = os.getenv("GOOGLE_ADS_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET", "").strip()
    code          = os.getenv("AUTH_CODE", "").strip()
    redirect_uri  = os.getenv(
        "REDIRECT_URI", "https://developers.google.com/oauthplayground"
    ).strip()

    missing = [name for name, val in [
        ("GOOGLE_ADS_CLIENT_ID", client_id),
        ("GOOGLE_ADS_CLIENT_SECRET", client_secret),
        ("AUTH_CODE", code),
    ] if not val]
    if missing:
        print(f"✗ missing env vars: {', '.join(missing)}", file=sys.stderr)
        return 2

    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code":          code,
            "client_id":     client_id,
            "client_secret": client_secret,
            "redirect_uri":  redirect_uri,
            "grant_type":    "authorization_code",
        },
        timeout=15,
    )

    print(f"HTTP {resp.status_code}")
    try:
        body = resp.json()
    except ValueError:
        print(resp.text)
        return 1

    if resp.status_code != 200:
        # Pretty-print Google's error for diagnosis
        print(json.dumps(body, indent=2))
        return 1

    refresh_token = body.get("refresh_token", "")
    if not refresh_token:
        print("⚠ Google returned no refresh_token. This usually means the "
              "user previously consented; revoke the app from "
              "https://myaccount.google.com/permissions and retry, OR add "
              "prompt=consent + access_type=offline to the authorize URL.")
        print(json.dumps(body, indent=2))
        return 1

    print()
    print("✓ Exchange successful")
    print(f"  access_token  : {body['access_token'][:20]}…  (expires in {body.get('expires_in', '?')}s)")
    print(f"  refresh_token : {refresh_token}")
    print()
    print("Add this line to your server's .env and restart the dashboard:")
    print(f"  GOOGLE_ADS_REFRESH_TOKEN={refresh_token}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
