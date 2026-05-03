import streamlit as st
from users import verify_password


def check_auth() -> bool:
    return st.session_state.get("authenticated", False)


def logout() -> None:
    for key in ("authenticated", "username"):
        st.session_state.pop(key, None)
    st.rerun()


def show_login_page() -> None:
    st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="stAppViewContainer"] { background: #07090f; }
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
    div[data-testid="stForm"] button[kind="primaryFormSubmit"] {
        background: linear-gradient(135deg, #1f6feb 0%, #388bfd 100%) !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        letter-spacing: 0.3px !important;
        height: 42px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.1, 1])
    with col:
        st.markdown("<div style='height:72px'></div>", unsafe_allow_html=True)

        st.markdown("""
        <div style='text-align:center;margin-bottom:28px'>
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
                    st.session_state["authenticated"] = True
                    st.session_state["username"] = username
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
