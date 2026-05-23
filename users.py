import hashlib
import json
import logging
import os

try:
    import bcrypt  # type: ignore
    _BCRYPT_AVAILABLE = True
except ImportError:  # bcrypt not installed yet (older envs)
    _BCRYPT_AVAILABLE = False

log = logging.getLogger(__name__)

_CLIENTS_FILE = os.path.join(os.path.dirname(__file__), "clients.json")


def _legacy_sha256(password: str) -> str:
    """Legacy unsalted SHA256 hash — kept only to verify pre-bcrypt records."""
    return hashlib.sha256(password.strip().encode()).hexdigest()


def hash_password(password: str) -> str:
    """Create a new password hash. Prefers bcrypt, falls back to legacy SHA256."""
    pw = password.strip().encode()
    if _BCRYPT_AVAILABLE:
        return bcrypt.hashpw(pw, bcrypt.gensalt()).decode()
    return _legacy_sha256(password)


def _looks_like_bcrypt(stored_hash: str) -> bool:
    return isinstance(stored_hash, str) and stored_hash.startswith(("$2a$", "$2b$", "$2y$"))


def _verify_hash(password: str, stored_hash: str) -> bool:
    if not stored_hash:
        return False
    if _looks_like_bcrypt(stored_hash) and _BCRYPT_AVAILABLE:
        try:
            return bcrypt.checkpw(password.strip().encode(), stored_hash.encode())
        except (ValueError, TypeError):
            return False
    # Legacy SHA256 fallback (for unmigrated records)
    return _legacy_sha256(password) == stored_hash


def _admin_users() -> dict[str, dict]:
    """Admin users are loaded from env. Set ADMIN_USERNAME + ADMIN_PASSWORD_HASH.
    ADMIN_PASSWORD_HASH accepts a bcrypt hash (preferred) or legacy SHA256 hex."""
    username = os.getenv("ADMIN_USERNAME", "").strip()
    pw_hash = os.getenv("ADMIN_PASSWORD_HASH", "").strip()
    if username and pw_hash:
        return {
            username: {
                "password_hash": pw_hash,
                "role": "admin",
                "client_id": None,
            }
        }
    return {}


def _load_all_users() -> dict[str, dict]:
    """Merge env-configured admins with active clients from clients.json."""
    merged = dict(_admin_users())
    try:
        if os.path.exists(_CLIENTS_FILE):
            with open(_CLIENTS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            clients = data.get("clients", [])
            log.info("clients.json found: %d client(s)", len(clients))
            for c in clients:
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
        else:
            log.info("clients.json not found at %s", _CLIENTS_FILE)
    except Exception as e:
        log.warning("error reading clients.json: %s", e)
    return merged


def verify_password(username: str, password: str) -> bool:
    all_users = _load_all_users()
    user = all_users.get(username)
    if not user:
        log.info("login: unknown username")
        return False
    ok = _verify_hash(password, user.get("password_hash", ""))
    log.info("login: result=%s", "ok" if ok else "fail")
    return ok


def get_user(username: str) -> dict:
    return _load_all_users().get(username, {})
