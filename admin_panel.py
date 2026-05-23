import html
import json
import logging
import os
from datetime import datetime

import streamlit as st

from users import hash_password

CLIENTS_FILE = os.path.join(os.path.dirname(__file__), "clients.json")

log = logging.getLogger(__name__)


# ── Storage helpers ───────────────────────────────────────────────────────────

def load_clients() -> list[dict]:
    if not os.path.exists(CLIENTS_FILE):
        return []
    try:
        with open(CLIENTS_FILE, encoding="utf-8") as f:
            return json.load(f).get("clients", [])
    except Exception as e:
        log.warning("failed to load clients.json: %s", e)
        return []


def save_clients(clients: list[dict]) -> None:
    with open(CLIENTS_FILE, "w", encoding="utf-8") as f:
        json.dump({"clients": clients}, f, indent=2, ensure_ascii=False)


def _all_usernames() -> set:
    """All taken usernames — admin (from env) + saved clients."""
    names = set()
    admin = os.getenv("ADMIN_USERNAME", "").strip()
    if admin:
        names.add(admin)
    for c in load_clients():
        names.add(c["username"])
    return names


# ── Edit dialog ───────────────────────────────────────────────────────────────

@st.dialog("Edit Client")
def _edit_dialog(client: dict) -> None:
    st.markdown(
        f"<div style='font-size:12px;color:rgba(255,255,255,0.4);margin-bottom:18px'>"
        f"Username: <b style='color:#f0f6fc'>{html.escape(client['username'])}</b></div>",
        unsafe_allow_html=True,
    )

    new_name = st.text_input("Display Name", value=client.get("display_name", ""))
    c_g, c_m, c_s = st.columns(3)
    new_cid  = c_g.text_input("Google Ads Account ID",
                               value=client.get("client_id", ""),
                               help="10-digit ID, no dashes")
    new_meta = c_m.text_input("Meta Ad Account ID",
                               value=client.get("meta_account_id", ""),
                               help="Numeric ID only, e.g. 579554746963968")
    new_snap = c_s.text_input("Snap Ad Account ID",
                               value=client.get("snap_account_id", ""),
                               help="UUID from Snap Ads Manager")
    new_pass = st.text_input("New Password", type="password",
                              placeholder="Leave blank to keep current password")
    active   = st.toggle("Account Active", value=client.get("active", True))

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    if c1.button("Save Changes", use_container_width=True, type="primary"):
        if not new_name.strip():
            st.error("Display name cannot be empty.")
            return
        clients = load_clients()
        for i, c in enumerate(clients):
            if c["username"] == client["username"]:
                clients[i]["display_name"]   = new_name.strip()
                clients[i]["client_id"]      = new_cid.strip().replace("-", "")
                clients[i]["meta_account_id"]= new_meta.strip().replace("act_", "")
                clients[i]["snap_account_id"]= new_snap.strip()
                clients[i]["active"]         = active
                if new_pass.strip():
                    clients[i]["password_hash"] = hash_password(new_pass.strip())
                clients[i]["updated_at"] = datetime.utcnow().isoformat()
                break
        save_clients(clients)
        st.rerun()

    if c2.button("Cancel", use_container_width=True):
        st.rerun()


# ── Tab: Add Client ───────────────────────────────────────────────────────────

def _tab_add() -> None:
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    with st.form("add_client_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        display_name = c1.text_input("Client Display Name *",
                                      placeholder="e.g. Elegance Store")
        username     = c2.text_input("Username *",
                                      placeholder="e.g. elegance")
        c3, c4 = st.columns(2)
        password  = c3.text_input("Password *", type="password")
        client_id = c4.text_input("Google Ads Account ID *",
                                   placeholder="1234567890  (no dashes)")
        c5, c6 = st.columns(2)
        meta_account_id = c5.text_input(
            "Meta Ad Account ID",
            placeholder="579554746963968  (optional)",
            help="Leave blank if client has no Meta Ads account")
        snap_account_id = c6.text_input(
            "Snap Ad Account ID",
            placeholder="UUID from Snap Ads Manager  (optional)",
            help="Leave blank if client has no Snap Ads account")

        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        submitted = st.form_submit_button(
            "➕  Add Client", use_container_width=True, type="primary")

        if submitted:
            errors = []
            if not display_name.strip():
                errors.append("Display Name is required.")
            if not username.strip():
                errors.append("Username is required.")
            elif username.strip() in _all_usernames():
                errors.append(f"Username **{username.strip()}** is already taken.")
            if not password.strip():
                errors.append("Password is required.")
            if not client_id.strip():
                errors.append("Google Ads Account ID is required.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                clients = load_clients()
                clients.append({
                    "username":        username.strip(),
                    "password_hash":   hash_password(password.strip()),
                    "display_name":    display_name.strip(),
                    "client_id":       client_id.strip().replace("-", ""),
                    "meta_account_id": meta_account_id.strip().replace("act_", ""),
                    "snap_account_id": snap_account_id.strip(),
                    "active":          True,
                    "created_at":      datetime.utcnow().isoformat(),
                })
                save_clients(clients)
                st.success(
                    f"✓ Client **{display_name.strip()}** added. "
                    f"They can now log in as `{username.strip()}`.`")


# ── Tab: Client List ──────────────────────────────────────────────────────────

def _tab_list() -> None:
    clients = load_clients()

    if not clients:
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        st.info("No client accounts yet. Add one in the **Add Client** tab.")
        return

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── Column headers ────────────────────────────────────────────────────────
    hcols = st.columns([2.2, 1.4, 1.8, 1.1, 0.75, 0.85])
    for col, lbl in zip(hcols,
                        ["Display Name", "Username", "Account ID",
                         "Status", "", ""]):
        col.markdown(
            f"<div style='font-size:10px;font-weight:700;letter-spacing:1.2px;"
            f"text-transform:uppercase;color:rgba(255,255,255,0.25);"
            f"padding-bottom:8px'>{lbl}</div>",
            unsafe_allow_html=True)
    st.markdown(
        "<hr style='border:none;border-top:1px solid rgba(255,255,255,0.07);"
        "margin:0 0 4px'>",
        unsafe_allow_html=True)

    confirm_key = "_admin_confirm_delete"

    for client in clients:
        active = client.get("active", True)
        sc = "#3fb950" if active else "#6e7681"
        sl = "● Active" if active else "○ Inactive"

        row = st.columns([2.2, 1.4, 1.8, 1.1, 0.75, 0.85])

        row[0].markdown(
            f"<div style='font-size:13px;font-weight:600;color:#e6edf3;"
            f"padding-top:5px'>{html.escape(client.get('display_name', client['username']))}</div>",
            unsafe_allow_html=True)
        row[1].markdown(
            f"<div style='font-size:12px;color:rgba(255,255,255,0.4);"
            f"padding-top:6px'>{html.escape(client['username'])}</div>",
            unsafe_allow_html=True)
        row[2].markdown(
            f"<div style='font-size:11px;font-family:monospace;"
            f"color:rgba(255,255,255,0.35);padding-top:6px'>"
            f"{html.escape(client.get('client_id') or '—')}</div>",
            unsafe_allow_html=True)
        row[3].markdown(
            f"<div style='font-size:11px;font-weight:600;color:{sc};"
            f"padding-top:6px'>{sl}</div>",
            unsafe_allow_html=True)

        if row[4].button("Edit", key=f"edit_{client['username']}",
                         use_container_width=True):
            _edit_dialog(client)

        # Delete — requires inline confirmation
        confirming = st.session_state.get(confirm_key) == client["username"]

        if confirming:
            st.markdown(
                f"<div style='background:rgba(248,81,73,0.07);"
                f"border:1px solid rgba(248,81,73,0.22);border-radius:10px;"
                f"padding:10px 16px;margin:4px 0 6px;display:flex;"
                f"align-items:center;gap:12px'>"
                f"<span style='font-size:12.5px;color:rgba(255,255,255,0.6);flex:1'>"
                f"Delete <b style='color:#f0f6fc'>"
                f"{html.escape(client.get('display_name', client['username']))}</b>?"
                f" This cannot be undone.</span></div>",
                unsafe_allow_html=True)
            dc1, dc2, dc3 = st.columns([3.6, 0.8, 0.8])
            if dc2.button("Delete", key=f"yes_{client['username']}",
                          type="primary", use_container_width=True):
                save_clients(
                    [c for c in load_clients()
                     if c["username"] != client["username"]])
                st.session_state.pop(confirm_key, None)
                st.rerun()
            if dc3.button("Cancel", key=f"no_{client['username']}",
                          use_container_width=True):
                st.session_state.pop(confirm_key, None)
                st.rerun()
        else:
            if row[5].button("Delete", key=f"del_{client['username']}",
                             use_container_width=True):
                st.session_state[confirm_key] = client["username"]
                st.rerun()

        st.markdown(
            "<hr style='border:none;border-top:1px solid rgba(255,255,255,0.04);"
            "margin:4px 0'>",
            unsafe_allow_html=True)

    st.markdown(
        f"<div style='font-size:11px;color:rgba(255,255,255,0.2);margin-top:8px'>"
        f"{len(clients)} client account{'s' if len(clients)!=1 else ''}</div>",
        unsafe_allow_html=True)


# ── Main entry point ──────────────────────────────────────────────────────────

def render_admin_panel() -> None:
    st.markdown("""
    <div style='padding:8px 0 20px'>
      <div style='font-size:26px;font-weight:900;color:#f0f6fc;letter-spacing:-1px'>
        Admin Panel
      </div>
      <div style='font-size:13px;color:rgba(255,255,255,0.28);margin-top:5px'>
        Manage client accounts — changes take effect immediately
      </div>
    </div>
    """, unsafe_allow_html=True)

    tab_add, tab_list = st.tabs(["➕  Add Client", "📋  All Clients"])

    with tab_add:
        _tab_add()

    with tab_list:
        _tab_list()
