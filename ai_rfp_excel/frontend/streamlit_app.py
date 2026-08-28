import streamlit as st

from ai_rfp_excel.frontend.api_client import APIClient
from ai_rfp_excel.frontend.components import render_error_card, render_health_indicator

st.set_page_config(
    page_title="AI RFP Excel Automation System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize Session State
if "api_client" not in st.session_state:
    st.session_state["api_client"] = APIClient()

client: APIClient = st.session_state["api_client"]

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["token"] = None
    st.session_state["user_info"] = None
    st.session_state["current_run_id"] = None

# Sidebar Health Check & Navigation Header
health = client.check_health()
render_health_indicator(health)

st.sidebar.markdown("### 🤖 RFP Automation")
st.sidebar.markdown("Private, local AI RFP PDF-to-Excel matching system.")

if st.session_state["authenticated"]:
    user = st.session_state["user_info"] or {}
    st.sidebar.markdown(f"**Logged in as:** `{user.get('username', 'User')}` ({user.get('role', 'tender_manager')})")
    if st.sidebar.button("🚪 Log Out", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state["token"] = None
        st.session_state["user_info"] = None
        client.set_token(None)
        st.rerun()

# Authentication Guard / Login Screen
if not st.session_state["authenticated"]:
    st.markdown("## 🔐 RFP System Login")
    st.markdown("Please enter your credentials to access the AI RFP analysis pipeline.")

    col1, col2 = st.columns([1, 1])
    with col1:
        with st.form("login_form"):
            username = st.text_input("Username or Email", placeholder="e.g. admin or tender_manager")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Sign In", type="primary", use_container_width=True)

            if submit:
                if not username or not password:
                    render_error_card("Validation Error", "Please provide both username and password.")
                else:
                    success, res = client.login(username, password)
                    if success and isinstance(res, dict):
                        st.session_state["authenticated"] = True
                        st.session_state["token"] = res.get("access_token")
                        st.session_state["user_info"] = res.get("user")
                        client.set_token(res.get("access_token"))
                        st.toast("Login successful!", icon="✅")
                        st.rerun()
                    else:
                        error_msg = str(res)
                        render_error_card("Authentication Failed", error_msg, "Ensure username and password are correct.")

    with col2:
        st.info(
            "💡 **System Capabilities:**\n\n"
            "- 📄 **Native & Scanned PDF OCR**: Extracts specs from complex server/storage datasheets\n"
            "- 📑 **Excel Structure Preservation**: Preserves original fonts, formulas, merged cells\n"
            "- ⚡ **5-Layer Compliance Engine**: Fast exact, rule-based, and unit conversions\n"
            "- 🔒 **100% Local & Private**: Powered by local Ollama AI models"
        )
    st.stop()

# Main Dashboard Landing (When logged in)
st.title("📊 AI RFP PDF-to-Excel Automation System")
st.markdown("Automate technical compliance evaluation between vendor specifications and RFP response sheets.")
st.markdown("---")

col_a, col_b, col_c = st.columns(3)

with col_a:
    st.subheader("1. Start New Evaluation")
    st.write("Upload PDF datasheets and your Excel RFP template to initiate automated compliance analysis.")
    st.page_link("pages/1_Upload.py", label="Go to Upload & Configure", icon="📤")

with col_b:
    st.subheader("2. Review & Approvals")
    st.write("Inspect requirement citations, evaluate AI confidence, and override decisions.")
    st.page_link("pages/3_Review.py", label="Go to Review Workspace", icon="🔍")

with col_c:
    st.subheader("3. Past Runs & History")
    st.write("Access previously processed runs, download populated Excel files, or re-run evaluations.")
    st.page_link("pages/4_History.py", label="Go to Run History", icon="📜")
