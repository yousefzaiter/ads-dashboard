import hashlib


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# role "admin"  → sees all clients, can switch between them
# role "client" → locked to their assigned client_id (Google Ads customer ID, no dashes)
USERS: dict[str, dict] = {
    "yousef": {
        "password_hash": _hash("0592263833"),
        "role": "admin",
        "client_id": None,
    },
    # ── Add client accounts below ──────────────────────────────────────────────
    # "clientname": {
    #     "password_hash": _hash("their_password"),
    #     "role": "client",
    #     "client_id": "1234567890",   # 10-digit Google Ads customer ID, no dashes
    # },
}


def verify_password(username: str, password: str) -> bool:
    user = USERS.get(username)
    if not user:
        return False
    return user["password_hash"] == _hash(password)


def get_user(username: str) -> dict:
    return USERS.get(username, {})
