import datetime

import extra_streamlit_components as stx
import streamlit as st
import streamlit_antd_components as sac

from ai_rfp_excel.frontend.api_client import APIClient
from ai_rfp_excel.frontend.components import (
    inject_custom_css,
    render_error_card,
    render_header,
    render_health_indicator,
)

st.set_page_config(
    page_title="AI RFP Excel Automation System",
    page_icon="assets/logo.png" if False else None,
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
        </style>
        """,
        unsafe_allow_html=True,
    )

    _, center_col, _ = st.columns([1, 2.2, 1])

    with center_col:
        st.markdown(
            """
            <div style="text-align: center; margin-top: 30px; margin-bottom: 24px;">
                <div style="font-size: 26px; font-weight: 800; color: #0f172a; letter-spacing: -0.02em;">
                    AI RFP Automation System
                </div>
                <div style="font-size: 14px; color: #64748b; margin-top: 6px;">
                    Enterprise PDF-to-Excel Compliance & Specification Matching
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_form, col_info = st.columns([1.1, 1])

        with col_form:
            with st.container(border=True):
                st.markdown(
                    '<div style="font-size: 16px; font-weight: 700; color: #0f172a; margin-bottom: 12px;">Sign In</div>',
                    unsafe_allow_html=True,
                )

                with st.form("login_form", clear_on_submit=False):
                    username = st.text_input("Username or Email", placeholder="admin")
                    password = st.text_input("Password", type="password", placeholder="••••••••")
                    remember_me = st.checkbox("Remember me for 30 days", value=True)
                    submit = st.form_submit_button("Sign In", type="primary", use_container_width=True)

                    if submit:
                        if not username or not password:
                            render_error_card("Validation Error", "Please provide both username/email and password.")
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
                                    "Verify your username and password, or contact system administrator.",
                                )

        with col_info:
            with st.container(border=True):
                st.markdown(
                    """
                    <div style="font-size: 14px; font-weight: 700; color: #0f172a; margin-bottom: 12px;">
                        Platform Capabilities
                    </div>
                    <ul style="padding-left: 18px; margin: 0; font-size: 13px; color: #334155; line-height: 1.8;">
                        <li><strong>Automated PDF Extraction:</strong> Multi-engine OCR & technical table parsing.</li>
                        <li><strong>5-Layer Matching Engine:</strong> Deterministic, fuzzy, rule-based & LLM matching.</li>
                        <li><strong>Excel Preservation:</strong> Exact cell styles, formulas & workbook structure.</li>
                        <li><strong>100% Local & Private:</strong> Zero data leakage with local Ollama inference.</li>
                    </ul>
                    """,
                    unsafe_allow_html=True,
                )

    st.stop()


# ==========================================
# AUTHENTICATED: Sidebar & Dashboard
# ==========================================

# Health Indicator in Sidebar
health = client.check_health()
render_health_indicator(health)

st.sidebar.markdown(
    """
    <div style="padding: 4px 0 16px 0; border-bottom: 1px solid #e2e8f0; margin-bottom: 16px;">
        <div style="font-size: 16px; font-weight: 800; color: #0f172a;">RFP Automation</div>
        <div style="font-size: 12px; color: #64748b;">Enterprise Technical Compliance</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# User Profile Badge & Sign Out in Sidebar Footer
user_info = st.session_state.get("user_info") or {}
uname = user_info.get("username", "Evaluator")
is_admin = bool(user_info.get("is_admin", False))
role_label = "ADMINISTRATOR" if is_admin else "EVALUATOR"
role_color = "blue" if is_admin else "geekblue"

st.sidebar.markdown(
    f"""
    <div class="sidebar-profile-card">
        <div class="sidebar-username">{uname}</div>
        <div style="font-size: 11px; color: #64748b; margin-bottom: 6px;">{user_info.get('email', '')}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

sac.tags(
    items=[sac.Tag(label=role_label, color=role_color)],
    align="start",
    size="sm",
    key="sidebar_user_role_tag",
)

if st.sidebar.button("Sign Out", use_container_width=True, type="secondary"):
    cookie_manager.delete(cookie="rfp_auth_token", key="logout_delete_cookie")
    st.session_state["authenticated"] = False
    st.session_state["token"] = None
    st.session_state["user_info"] = None
    client.set_token(None)
    st.rerun()

# Main Dashboard Landing (When logged in)
render_header(
    title="RFP Evaluation Workspace",
    subtitle="Automate technical compliance evaluation between vendor specifications and RFP response sheets.",
    tag_text="System Active",
)

col_a, col_b, col_c = st.columns(3)

with col_a:
    with st.container(border=True):
        st.markdown('<div style="font-size: 16px; font-weight: 700; color: #0f172a;">New Evaluation</div>', unsafe_allow_html=True)
        st.markdown('<p style="font-size: 13px; color: #64748b; min-height: 40px;">Upload PDF datasheets and Excel RFP sheets to start automated evaluation.</p>', unsafe_allow_html=True)
        st.page_link("pages/1_Upload.py", label="Open Upload & Configure", icon=":material/upload_file:")

with col_b:
    with st.container(border=True):
        st.markdown('<div style="font-size: 16px; font-weight: 700; color: #0f172a;">Review & Approvals</div>', unsafe_allow_html=True)
        st.markdown('<p style="font-size: 13px; color: #64748b; min-height: 40px;">Inspect specification citations, review AI confidence, and override decisions.</p>', unsafe_allow_html=True)
        st.page_link("pages/3_Review.py", label="Open Review Workspace", icon=":material/fact_check:")

with col_c:
    with st.container(border=True):
        st.markdown('<div style="font-size: 16px; font-weight: 700; color: #0f172a;">Evaluation History</div>', unsafe_allow_html=True)
        st.markdown('<p style="font-size: 13px; color: #64748b; min-height: 40px;">View past evaluation runs, download populated Excel files, and check analytics.</p>', unsafe_allow_html=True)
        st.page_link("pages/4_History.py", label="Open Run History", icon=":material/history:")
