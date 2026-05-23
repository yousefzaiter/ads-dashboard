"""
Snapchat Marketing API — OAuth 2.0 token acquisition.

Flow:
  1. Opens browser → user logs in and approves
  2. Snapchat redirects to ads-dashboard.yousefzaiter.com?code=...
  3. User pastes the code (or full redirect URL) here
  4. Script exchanges code for access_token + refresh_token
  5. Tokens saved to .env
"""

import base64
import os
import re
import secrets
import sys
import webbrowser
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import requests
from dotenv import load_dotenv

load_dotenv()

# ── Credentials (loaded from environment) ────────────────────────────────────
CLIENT_ID     = os.getenv("SNAP_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SNAP_CLIENT_SECRET", "")
REDIRECT_URI  = os.getenv("SNAP_REDIRECT_URI", "https://ads-dashboard.yousefzaiter.com")
SCOPE         = "snapchat-marketing-api"

if not CLIENT_ID or not CLIENT_SECRET:
    print("\n✗ SNAP_CLIENT_ID and SNAP_CLIENT_SECRET must be set in .env")
    print("  Get them from https://kit.snapchat.com/portal")
    sys.exit(1)

AUTH_URL  = "https://accounts.snapchat.com/login/oauth2/authorize"
TOKEN_URL = "https://accounts.snapchat.com/login/oauth2/access_token"
ENV_PATH  = Path(__file__).parent / ".env"


# ── Step 1: build authorization URL with CSRF state ──────────────────────────

OAUTH_STATE = secrets.token_urlsafe(32)

params = {
    "client_id":     CLIENT_ID,
    "redirect_uri":  REDIRECT_URI,
    "response_type": "code",
    "scope":         SCOPE,
    "state":         OAUTH_STATE,
}
auth_url = f"{AUTH_URL}?{urlencode(params)}"

print("\n" + "═" * 60)
print("  Snapchat OAuth — Token Setup")
print("═" * 60)
print("\nOpening browser for Snapchat login...")
print(f"\n  {auth_url}\n")
webbrowser.open(auth_url)

print("After approving, Snapchat will redirect you to:")
print(f"  {REDIRECT_URI}?code=<authorization_code>\n")
print("The page may not load fully — that's fine.")
print("Copy the full URL from your browser address bar and paste it below.\n")


# ── Step 2: capture authorization code ───────────────────────────────────────

raw = input("Paste the redirect URL (or just the code): ").strip()

# Accept full URL or bare code
if raw.startswith("http"):
    parsed = urlparse(raw)
    qs     = parse_qs(parsed.query)
    code   = qs.get("code", [None])[0]
    returned_state = qs.get("state", [None])[0]
    if not code:
        print("\n✗ Could not find 'code' in URL. Make sure you copied the full redirect URL.")
        sys.exit(1)
    if returned_state != OAUTH_STATE:
        print("\n✗ OAuth state mismatch — possible CSRF attempt. Aborting.")
        print(f"  expected: {OAUTH_STATE[:12]}…  got: {(returned_state or '')[:12]}…")
        sys.exit(1)
else:
    code = raw  # bare code: state cannot be validated, warn the user
    print("\n⚠️  Bare code pasted — OAuth state could not be validated.")
    print("    For full CSRF protection, paste the full redirect URL next time.")

print(f"\n  Code captured: {code[:12]}…")


# ── Step 3: exchange code for tokens ─────────────────────────────────────────

credentials = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()

print("\nExchanging code for tokens...")
resp = requests.post(
    TOKEN_URL,
    headers={
        "Authorization": f"Basic {credentials}",
        "Content-Type":  "application/x-www-form-urlencoded",
    },
    data={
        "grant_type":   "authorization_code",
        "code":         code,
        "redirect_uri": REDIRECT_URI,
    },
    timeout=15,
)

if resp.status_code != 200:
    print(f"\n✗ Token exchange failed ({resp.status_code}):")
    print(resp.text[:500])
    sys.exit(1)

data          = resp.json()
access_token  = data.get("access_token", "")
refresh_token = data.get("refresh_token", "")
expires_in    = data.get("expires_in", "unknown")

if not access_token:
    print("\n✗ No access_token in response:")
    print(data)
    sys.exit(1)

print(f"\n  ✓ access_token  : {access_token[:16]}… ({expires_in}s expiry)")
print(f"  ✓ refresh_token : {refresh_token[:16]}…")


# ── Step 4: save to .env ─────────────────────────────────────────────────────

def _set_env(content: str, key: str, value: str) -> str:
    pattern = rf"^{re.escape(key)}=.*$"
    line    = f"{key}={value}"
    if re.search(pattern, content, re.MULTILINE):
        return re.sub(pattern, line, content, flags=re.MULTILINE)
    return content.rstrip("\n") + f"\n{line}\n"

content = ENV_PATH.read_text() if ENV_PATH.exists() else ""
for key, val in [
    ("SNAP_CLIENT_ID",     CLIENT_ID),
    ("SNAP_CLIENT_SECRET", CLIENT_SECRET),
    ("SNAP_ACCESS_TOKEN",  access_token),
    ("SNAP_REFRESH_TOKEN", refresh_token),
]:
    content = _set_env(content, key, val)

ENV_PATH.write_text(content)
print(f"\n  ✓ Tokens saved to {ENV_PATH}")

print("\n" + "═" * 60)
print("  Setup complete — Snapchat tokens are ready.")
print("═" * 60 + "\n")
