import streamlit as st
import streamlit_authenticator as stauth


@st.cache_resource
def build_authenticator() -> stauth.Authenticate:
    """Build the authenticator once per server session.
    bcrypt hashing is intentionally slow, so we cache the result.
    """
    from users import build_stauth_credentials
    credentials = build_stauth_credentials()
    return stauth.Authenticate(
        credentials,
        cookie_name="ads_dashboard_auth",
        key="ads_dash_cookie_secret_2024_v1",
        cookie_expiry_days=30,
    )


def do_logout(authenticator: stauth.Authenticate) -> None:
    """Delete the auth cookie and clear session state, then rerun."""
    try:
        # stauth 0.3.x exposes cookie_handler
        authenticator.cookie_handler.delete_cookie()
    except Exception:
        pass
    for key in ("authentication_status", "name", "username", "logout"):
        st.session_state.pop(key, None)
    st.rerun()
