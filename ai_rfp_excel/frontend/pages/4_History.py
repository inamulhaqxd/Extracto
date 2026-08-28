import streamlit as st

from ai_rfp_excel.frontend.api_client import APIClient
from ai_rfp_excel.frontend.components import (
    render_health_indicator,
    render_status_pill,
)

st.set_page_config(page_title="Run History & Re-runs", page_icon="📜", layout="wide")

client: APIClient = st.session_state.get("api_client", APIClient())
health = client.check_health()
render_health_indicator(health)

if not st.session_state.get("authenticated"):
    st.warning("⚠️ Please log in to view run history.")
    st.page_link("streamlit_app.py", label="Go to Login Screen", icon="🔐")
    st.stop()

st.title("📜 Processing Runs History")
st.markdown("Inspect previous evaluation runs, download outputs, or trigger re-runs.")
st.markdown("---")

# Filter and Search Bar
f_col1, f_col2 = st.columns([1, 2])
with f_col1:
    status_filter = st.selectbox("Filter Status:", options=["All", "Completed", "Processing", "Cancelled", "Failed"])
with f_col2:
    search_query = st.text_input("Search by filename or model:", placeholder="e.g. server_specs, dell, qwen3")

# Fetch runs list
runs = client.list_runs(status_filter=status_filter)

# Apply Search
if search_query:
    q = search_query.lower()
    runs = [
        r for r in runs
        if q in (r.get("pdf_filename") or "").lower()
        or q in (r.get("workbook_filename") or "").lower()
        or q in (r.get("model_used") or "").lower()
        or q in r.get("run_id", "").lower()
    ]

if not runs:
    st.info("No runs found matching the selected criteria.")
    st.page_link("pages/1_Upload.py", label="Start a New Evaluation Run", icon="📤")
    st.stop()

st.write(f"Displaying **{len(runs)}** runs")

# Render Runs Cards
for r in runs:
    r_id = r.get("run_id")
    r_status = r.get("status", "unknown")
    pdf_fn = r.get("pdf_filename") or "PDF Document"
    wb_fn = r.get("workbook_filename") or "Excel Workbook"
    gen_file = r.get("generated_file")
    started = r.get("started_at") or "N/A"
    model = r.get("model_used") or "N/A"
    total_reqs = r.get("total_requirements", 0)

    with st.container():
        st.markdown(
            f'<div style="border:1px solid #dee2e6; border-radius:8px; padding:16px; margin-bottom:14px; background-color:#ffffff;">'
            f'<div style="display:flex; justify-content:space-between; align-items:center;">'
            f'  <h4 style="margin:0; font-size:16px;">📄 {pdf_fn} &nbsp; ➔ &nbsp; 📑 {wb_fn}</h4>'
            f'  <div>{render_status_pill(r_status)}</div>'
            f'</div>'
            f'<p style="margin:6px 0 10px 0; font-size:12px; color:#6c757d;">'
            f'  <strong>Run ID:</strong> <code>{r_id}</code> | <strong>Model:</strong> {model} | <strong>Started:</strong> {started} | <strong>Requirements:</strong> {total_reqs}'
            f'</p>'
            f'</div>',
            unsafe_allow_html=True,
        )

        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            if st.button("🔍 Open in Review", key=f"rev_btn_{r_id}", use_container_width=True):
                st.session_state["current_run_id"] = r_id
                st.page_link("pages/3_Review.py", label="Go to Review Workspace", icon="🔍")

        with c2:
            if gen_file:
                download_url = client.get_download_url(gen_file)
                st.markdown(
                    f'<a href="{download_url}" target="_blank" style="text-decoration:none;">'
                    f'<button style="background-color:#17a2b8; color:white; padding:8px 16px; border:none; border-radius:4px; font-weight:600; width:100%; cursor:pointer;">'
                    f'📥 Download Excel'
                    f'</button>'
                    f'</a>',
                    unsafe_allow_html=True,
                )

        with c3:
            if st.button("🔄 Re-run Evaluation (Reuse Specs)", key=f"rerun_{r_id}"):
                st.session_state["current_run_id"] = r_id
                st.info(f"Re-run triggered for {r_id}. Navigating to upload/configuration...")
                st.page_link("pages/1_Upload.py", label="Configure Re-run Options", icon="📤")

        st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
