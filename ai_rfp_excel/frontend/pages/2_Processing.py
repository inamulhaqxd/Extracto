import time

import streamlit as st

from ai_rfp_excel.frontend.api_client import APIClient
from ai_rfp_excel.frontend.components import render_error_card, render_health_indicator

st.set_page_config(page_title="Processing Run", page_icon="⚡", layout="wide")

client: APIClient = st.session_state.get("api_client", APIClient())
health = client.check_health()
render_health_indicator(health)

if not st.session_state.get("authenticated"):
    st.warning("⚠️ Please log in to view processing runs.")
    st.page_link("streamlit_app.py", label="Go to Login Screen", icon="🔐")
    st.stop()

run_id = st.session_state.get("current_run_id")

st.title("⚡ Live Processing & Matching Pipeline")
st.markdown("Automated PDF specification extraction, requirement parsing, and 5-layer compliance resolution.")
st.markdown("---")

if not run_id:
    st.info("No active run selected. Please start a run from the Upload page or select one from History.")
    st.page_link("pages/1_Upload.py", label="Go to Upload Page", icon="📤")
    st.page_link("pages/4_History.py", label="Go to History Page", icon="📜")
    st.stop()

# Fetch latest status
try:
    run_data = client.get_run(run_id)
except Exception as e:
    render_error_card("Communication Error", f"Could not retrieve status for Run {run_id}: {e!s}")
    st.stop()

status = run_data.get("status", "pending")
progress = float(run_data.get("progress", 0.0))
current_step = run_data.get("current_step", "Processing...")
model_used = run_data.get("model_used", "N/A")
pdf_name = run_data.get("pdf_filename") or st.session_state.get("active_pdf_filename", "N/A")
wb_name = run_data.get("workbook_filename") or st.session_state.get("active_excel_filename", "N/A")

# Top Metadata Bar
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Run ID", run_id[:8] + "...")
with col2:
    st.metric("Status", status.upper())
with col3:
    st.metric("Model", model_used)
with col4:
    st.metric("Progress", f"{int(progress)}%")

st.markdown("---")

# Progress and status section
if status in ("pending", "processing"):
    st.subheader("Current Step:")
    st.info(f"🔄 **{current_step}**")
    st.progress(min(1.0, progress / 100.0))

    # Cancel Button
    col_c1, col_c2 = st.columns([1, 4])
    with col_c1:
        if st.button("⛔ Cancel Run", type="secondary", use_container_width=True):
            if client.cancel_run(run_id):
                st.warning("Run cancellation requested.")
                st.rerun()

    # Poll every 2 seconds
    time.sleep(2.0)
    st.rerun()

elif status == "completed":
    st.success("🎉 Processing completed successfully!")
    st.progress(1.0)
    st.markdown(f"**Final Step:** `{current_step}`")

    # Metrics row
    tot = run_data.get("total_requirements", 0)
    comp = run_data.get("compliant_count", 0)
    non_comp = run_data.get("non_compliant_count", 0)
    amb = run_data.get("ambiguous_count", 0)
    nf = run_data.get("not_found_count", 0)
    low_conf = run_data.get("low_confidence_count", 0)

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Total Reqs", tot)
    m2.metric("Compliant", comp)
    m3.metric("Non-Compliant", non_comp)
    m4.metric("Ambiguous", amb)
    m5.metric("Not Found", nf)
    m6.metric("Needs Review", low_conf)

    st.markdown("---")
    st.subheader("Next Action:")
    st.write("Inspect requirement citations, evaluate AI confidence, and approve or override decisions.")
    st.page_link("pages/3_Review.py", label="Open Review & Approval Workspace ➡️", icon="🔍")

elif status == "cancelled":
    st.warning("⚠️ This run was cancelled by the user.")
    st.page_link("pages/1_Upload.py", label="Start New Run", icon="📤")

elif status == "failed":
    error_msg = run_data.get("error_message") or "Unknown execution error"
    render_error_card("Run Failed", error_msg, "Check backend and Ollama server logs.")
    st.page_link("pages/1_Upload.py", label="Try Again with Another Document", icon="🔄")
