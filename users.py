import bcrypt

# role "admin"  → sees all clients, can switch between them
# role "client" → locked to their assigned client_id (10-digit Google Ads ID, no dashes)
USERS: dict[str, dict] = {
    "yousef": {
        "name": "Yousef",
        "password": "0592263833",
        "role": "admin",
        "client_id": None,
    },
    # ── Add client accounts below ──────────────────────────────────────────────
    # "clientname": {
    #     "name": "Display Name",
    #     "password": "their_password",
    #     "role": "client",
    #     "client_id": "1234567890",   # 10-digit Google Ads customer ID, no dashes
    # },
}


def get_user(username: str) -> dict:
    return USERS.get(username, {})


def build_stauth_credentials() -> dict:
    """Return bcrypt-hashed credentials dict for streamlit-authenticator.
    Called once at startup (via @st.cache_resource) because bcrypt is slow.
    """
    usernames = {}
    for uname, info in USERS.items():
        hashed = bcrypt.hashpw(info["password"].encode(), bcrypt.gensalt()).decode()
        usernames[uname] = {
            "email": f"{uname}@ads.local",
            "name": info["name"],
            "password": hashed,
            "failed_login_attempts": 0,
            "logged_in": False,
        }
    return {"usernames": usernames}
