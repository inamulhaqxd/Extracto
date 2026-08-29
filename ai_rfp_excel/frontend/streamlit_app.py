import datetime

import extra_streamlit_components as stx
import streamlit as st
import streamlit_antd_components as sac

from ai_rfp_excel.frontend.api_client import APIClient
from ai_rfp_excel.frontend.components import (
    inject_custom_css,
    render_error_card,
)
from ai_rfp_excel.frontend.views.history import render_history
from ai_rfp_excel.frontend.views.settings import render_settings
from ai_rfp_excel.frontend.views.workspace import render_workspace

st.set_page_config(
    page_title="TenderFlow",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject Enterprise CSS Design System
inject_custom_css()

# Initialize API Client
if "api_client" not in st.session_state:
    st.session_state["api_client"] = APIClient()

client: APIClient = st.session_state["api_client"]

# Initialize Session State
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["token"] = None
    st.session_state["user_info"] = None
    st.session_state["current_run_id"] = None
    st.session_state["cookie_checked"] = False
    st.session_state["active_nav"] = "Dashboard"

if "active_nav" not in st.session_state:
    st.session_state["active_nav"] = "Dashboard"

# Cookie Manager for 30-day "Remember Me" persistence
cookie_manager = stx.CookieManager(key="rfp_auth_cookie_manager")

# Check and restore active session from cookie on initial load
if not st.session_state["authenticated"] and not st.session_state["cookie_checked"]:
    stored_token = cookie_manager.get(cookie="rfp_auth_token")
    if stored_token and isinstance(stored_token, str):
        client.set_token(stored_token)
        user = client.get_me()
        if user:
            st.session_state["authenticated"] = True
            st.session_state["token"] = stored_token
            st.session_state["user_info"] = user
            st.session_state["cookie_checked"] = True
            st.rerun()
        else:
            cookie_manager.delete(cookie="rfp_auth_token", key="del_expired_cookie")
            client.set_token(None)
            st.session_state["cookie_checked"] = True


# ==========================================
# UNAUTHENTICATED: Full-Screen Login Gate
# ==========================================
if not st.session_state["authenticated"]:
    # Lock down view: hide sidebar navigation completely
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="stSidebarNav"] { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
        .block-container { max-width: 100% !important; padding-top: 1rem !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Top-Left TenderFlow Brand Mark
    st.markdown(
        """
        <div style="padding: 12px 24px; display: flex; align-items: center; gap: 8px;">
            <span style="width: 5px; height: 18px; background-color: var(--theme-button-bg); border-radius: 1px; display: inline-block;"></span>
            <span style="font-size: 14px; font-weight: 800; letter-spacing: 0.08em; color: var(--theme-text-primary); text-transform: uppercase;">
                TENDERFLOW
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Centered Minimalist Login Container
    _, center_col, _ = st.columns([1, 1.2, 1])

    with center_col:
        st.markdown(
            """
            <div style="margin-top: 50px; margin-bottom: 28px;">
                <div style="font-size: 32px; font-weight: 400; letter-spacing: -0.03em; color: var(--theme-text-primary); margin-bottom: 6px; line-height: 1.2;">
                    Welcome back
                </div>
                <div style="font-size: 14px; color: var(--theme-text-subtle); font-weight: 400;">
                    Please enter your details to sign in.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("tenderflow_login_form", clear_on_submit=False):
            username = st.text_input("EMAIL ADDRESS", placeholder="email@example.com")
            password = st.text_input("PASSWORD", type="password", placeholder="••••••••")

            remember_me = st.checkbox("Remember me", value=True)

            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
            submit = st.form_submit_button("SIGN IN", type="primary", use_container_width=True)

            if submit:
                if not username or not password:
                    render_error_card("Validation Error", "Please enter your email address and password.")
                else:
                    success, res = client.login(username, password)
                    if success and isinstance(res, dict):
                        token = res.get("access_token")
                        user_data = res.get("user")

                        st.session_state["authenticated"] = True
                        st.session_state["token"] = token
                        st.session_state["user_info"] = user_data
                        client.set_token(token)

                        if remember_me and token:
                            expires = datetime.datetime.now() + datetime.timedelta(days=30)
                            cookie_manager.set(
                                cookie="rfp_auth_token",
                                val=token,
                                expires_at=expires,
                                key="set_auth_token_cookie",
                            )

                        st.toast("Signed in successfully.")
                        st.rerun()
                    else:
                        error_msg = str(res)
                        render_error_card(
                            "Authentication Failed",
                            error_msg,
                            "Verify your credentials or contact system administrator.",
                        )

    st.stop()


# ==========================================
# AUTHENTICATED: Sidebar Shell & Navigation
# ==========================================
if "default_model" not in st.session_state or not st.session_state["default_model"]:
    st.session_state["default_model"] = client.get_model_preference()

with st.sidebar:
    # Top Minimalist Brand Header
    st.markdown(
        """
        <div style="padding: 6px 0 18px 0; display: flex; align-items: center; gap: 8px; border-bottom: 1px solid var(--theme-border); margin-bottom: 16px;">
            <span style="width: 5px; height: 18px; background-color: var(--theme-button-bg); border-radius: 1px; display: inline-block;"></span>
            <span style="font-size: 15px; font-weight: 800; letter-spacing: 0.08em; color: var(--theme-text-primary); text-transform: uppercase;">
                TENDERFLOW
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Navigation Menu via sac.menu inside Sidebar
    nav_items = [
        sac.MenuItem("Dashboard", icon="grid"),
        sac.MenuItem("History", icon="clock-history"),
        sac.MenuItem("Settings", icon="gear"),
    ]

    # Find current index
    nav_names = ["Dashboard", "History", "Settings"]
    current_nav = st.session_state.get("active_nav", "Dashboard")
    if current_nav == "RFP Workspace":
        current_nav = "Dashboard"
    nav_index = nav_names.index(current_nav) if current_nav in nav_names else 0

    selected_nav = sac.menu(
        items=nav_items,
        index=nav_index,
        format_func=None,
        size="sm",
        key="sidebar_navigation_menu",
    )

    if selected_nav and selected_nav != st.session_state.get("active_nav"):
        st.session_state["active_nav"] = selected_nav
        st.rerun()

    # Spacer pushing Sign Out to the bottom
    st.markdown("<div style='height: 380px;'></div>", unsafe_allow_html=True)

    if st.button("Sign Out", use_container_width=True, type="secondary", key="btn_sign_out"):
        cookie_manager.delete(cookie="rfp_auth_token", key="logout_delete_cookie")
        st.session_state["authenticated"] = False
        st.session_state["token"] = None
        st.session_state["user_info"] = None
        st.session_state["active_nav"] = "Dashboard"
        client.set_token(None)
        st.rerun()


# ==========================================
# AUTHENTICATED: Main View Router
# ==========================================
active_tab = st.session_state.get("active_nav", "Dashboard")

if active_tab in ("Dashboard", "RFP Workspace"):
    render_workspace(client)
elif active_tab == "History":
    render_history(client)
elif active_tab == "Settings":
    render_settings(client)
else:
    render_workspace(client)

