import hashlib
import json
import os

_CLIENTS_FILE = os.path.join(os.path.dirname(__file__), "clients.json")


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# role "admin"  → sees all clients, can switch between them
# role "client" → locked to their assigned client_id (10-digit Google Ads ID, no dashes)
USERS: dict[str, dict] = {
    "yousef": {
        "password_hash": _hash("0592263833"),
        "role": "admin",
        "client_id": None,
    },
}


def _load_all_users() -> dict[str, dict]:
    """Merge hardcoded admins with active clients from clients.json."""
    merged = dict(USERS)
    try:
        if os.path.exists(_CLIENTS_FILE):
            with open(_CLIENTS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            for c in data.get("clients", []):
                if not c.get("active", True):
                    continue
                uname = c.get("username", "")
                if uname and uname not in merged:
                    merged[uname] = {
                        "password_hash": c["password_hash"],
                        "role": "client",
                        "client_id": c.get("client_id", ""),
                        "display_name": c.get("display_name", uname),
                    }
    except Exception:
        pass
    return merged


def verify_password(username: str, password: str) -> bool:
    user = _load_all_users().get(username)
    if not user:
        return False
    return user["password_hash"] == _hash(password)


def get_user(username: str) -> dict:
    return _load_all_users().get(username, {})
