import os
import secrets
import time
import streamlit as st
from users import verify_password
import logging

# Session lifetime in seconds (default 12 hours)
SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS", "43200"))


@st.cache_resource
def _session_store() -> dict:
    """Shared in-memory {token: (username, expires_at)} store.
    Survives page reruns and multi-user sessions. Lost only on server restart.
    """
    return {}


def _is_valid(token: str) -> str | None:
    """Return username if the token is valid and not expired, else None.
    Expired tokens are cleaned up from the store."""
    entry = _session_store().get(token)
    if not entry:
        return None
    username, expires_at = entry
    if time.time() > expires_at:
        _session_store().pop(token, None)
        return None
    return username


def check_auth() -> bool:
    """Read the token from session_state (preferred) or URL query param and
    validate it. Once read from the URL we move it to session_state and clear
    the URL so the token doesn't leak via referrers, browser history, or logs.
    """
    token = st.session_state.get("_auth_token", "") or st.query_params.get("token", "")
    if not token:
        return False
    username = _is_valid(token)
    if username:
        st.session_state["username"] = username
        st.session_state["_auth_token"] = token
        # Strip the token from the URL immediately for every user
        if "token" in st.query_params:
            try:
                del st.query_params["token"]
            except Exception as _exc:
                logging.getLogger(__name__).debug('suppressed: %s', _exc)
        return True
    return False


def do_logout() -> None:
    """Invalidate the session token, clear the URL, and rerun."""
    token = st.session_state.get("_auth_token", "") or st.query_params.get("token", "")
    _session_store().pop(token, None)
    st.session_state.pop("username", None)
    st.session_state.pop("_auth_token", None)
    st.query_params.clear()
    st.rerun()


def show_login_page() -> None:
    """Render the styled login page. Call this then st.stop() when not authenticated."""
    st.markdown("""
    <style>
    section[data-testid="stSidebar"] { display: none !important; }
    [data-testid="stAppViewContainer"] { background: #07090f; }
    .main .block-container {
        max-width: 400px !important;
        margin: 64px auto 0 !important;
        padding: 0 1rem !important;
    }
    div[data-testid="stForm"] {
        background: #111624;
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 18px;
        padding: 32px 28px 24px;
    }
    div[data-testid="stForm"] input {
        background: #0d1117 !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        color: #f0f6fc !important;
        border-radius: 8px !important;
    }
    div[data-testid="stForm"] button {
        background: linear-gradient(135deg, #1f6feb, #388bfd) !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        color: #fff !important;
        height: 42px !important;
    }
    label { color: rgba(255,255,255,0.5) !important; font-size: 12px !important; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style='text-align:center;padding:0 0 28px'>
      <div style='font-size:30px;font-weight:900;color:#f0f6fc;letter-spacing:-1px'>
        ⚡ Ads Intelligence
      </div>
      <div style='font-size:13px;color:rgba(255,255,255,0.3);margin-top:8px'>
        Sign in to access your dashboard
      </div>
    </div>
    """, unsafe_allow_html=True)

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submitted = st.form_submit_button("Sign in", use_container_width=True)

        if submitted:
            if verify_password(username, password):
                token = secrets.token_urlsafe(32)
                _session_store()[token] = (username, time.time() + SESSION_TTL)
                st.session_state["username"] = username
                st.session_state["_auth_token"] = token
                st.rerun()
            else:
                st.error("Invalid username or password.")
