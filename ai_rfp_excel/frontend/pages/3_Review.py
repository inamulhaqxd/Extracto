import streamlit as st

from ai_rfp_excel.frontend.api_client import APIClient
from ai_rfp_excel.frontend.components import (
    render_confidence_badge,
    render_error_card,
    render_health_indicator,
    render_status_pill,
)

st.set_page_config(page_title="Review & Approvals", page_icon="🔍", layout="wide")

client: APIClient = st.session_state.get("api_client", APIClient())
health = client.check_health()
render_health_indicator(health)

if not st.session_state.get("authenticated"):
    st.warning("⚠️ Please log in to review compliance results.")
    st.page_link("streamlit_app.py", label="Go to Login Screen", icon="🔐")
    st.stop()

run_id = st.session_state.get("current_run_id")

st.title("🔍 Compliance Review & Approval Workspace")
st.markdown("Inspect source citations, evaluate AI confidence, and approve or override compliance determinations.")
st.markdown("---")

if not run_id:
    st.info("No active run selected. Please select a completed run from History.")
    st.page_link("pages/4_History.py", label="Go to Run History", icon="📜")
    st.stop()

# Fetch latest run status and decisions
try:
    run_data = client.get_run(run_id)
except Exception as e:
    render_error_card("Communication Error", f"Could not load run data: {e!s}")
    st.stop()

if run_data.get("status") != "completed":
    st.warning(f"Run is currently `{run_data.get('status')}`. Please wait for completion before reviewing.")
    st.page_link("pages/2_Processing.py", label="View Live Progress", icon="⚡")
    st.stop()

decisions = run_data.get("decisions", [])
generated_file = run_data.get("generated_file")

# 1. Executive KPIs Bar
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Total Requirements", run_data.get("total_requirements", 0))
m2.metric("Compliant", run_data.get("compliant_count", 0))
m3.metric("Non-Compliant", run_data.get("non_compliant_count", 0))
m4.metric("Ambiguous", run_data.get("ambiguous_count", 0))
m5.metric("Not Found", run_data.get("not_found_count", 0))
m6.metric("Needs Review", run_data.get("low_confidence_count", 0))

st.markdown("---")

# 2. Download Final Excel Section
col_d1, col_d2 = st.columns([3, 1])
with col_d1:
    st.subheader("📑 Final Output Spreadsheet")
    st.caption("Workbook formatted with original fonts, styles, merged cells, formulas, and Compliance Summary tab.")
with col_d2:
    if generated_file:
        download_url = client.get_download_url(generated_file)
        st.markdown(
            f'<a href="{download_url}" target="_blank" style="text-decoration:none;">'
            f'<button style="background-color:#28a745; color:white; padding:10px 20px; border:none; border-radius:6px; font-weight:700; width:100%; cursor:pointer;">'
            f'📥 Download Populated Excel'
            f'</button>'
            f'</a>',
            unsafe_allow_html=True,
        )

st.markdown("---")

# 3. Bulk Action Tools
st.subheader("⚡ Bulk Approval Actions")
b1, b2, b3 = st.columns(3)

with b1:
    if st.button("✅ Approve All High-Confidence (>=90%)", use_container_width=True):
        updates = []
        for d in decisions:
            if d.get("confidence", 0.0) >= 0.90:
                updates.append({
                    "requirement_id": d["requirement_id"],
                    "status": d["status"],
                    "confidence": d["confidence"],
                    "review_notes": "Bulk approved (High confidence rule/exact match).",
                })
        if updates:
            client.submit_review(run_id, updates)
            st.toast(f"Approved {len(updates)} high-confidence requirements!", icon="✅")
            st.rerun()

with b2:
    if st.button("👍 Approve All Compliant", use_container_width=True):
        updates = []
        for d in decisions:
            if "COMPLIANT" in d["status"].upper() and "NON" not in d["status"].upper() and "PARTIAL" not in d["status"].upper():
                updates.append({
                    "requirement_id": d["requirement_id"],
                    "status": "COMPLIANT",
                    "confidence": d["confidence"],
                    "review_notes": "Bulk approved compliant items.",
                })
        if updates:
            client.submit_review(run_id, updates)
            st.toast(f"Approved {len(updates)} compliant requirements!", icon="✅")
            st.rerun()

with b3:
    st.caption("Changes are immediately applied to the populated workbook upon action.")

st.markdown("---")

# 4. Filters Bar
st.subheader("📋 Requirement Decisions & Provenance Citations")
filter_status = st.selectbox(
    "Filter by Compliance Status:",
    options=["All", "Needs Review (<70% or Ambiguous)", "Compliant", "Non-Compliant", "Ambiguous", "Not Found"],
    index=0,
)

# Apply Filter
filtered_decisions = decisions
if filter_status == "Needs Review (<70% or Ambiguous)":
    filtered_decisions = [d for d in decisions if d.get("needs_review") or d.get("confidence", 1.0) < 0.70]
elif filter_status == "Compliant":
    filtered_decisions = [d for d in decisions if "COMPLIANT" in d["status"].upper() and "NON" not in d["status"].upper() and "PARTIAL" not in d["status"].upper()]
elif filter_status == "Non-Compliant":
    filtered_decisions = [d for d in decisions if "NON_COMPLIANT" in d["status"].upper()]
elif filter_status == "Ambiguous":
    filtered_decisions = [d for d in decisions if "AMBIGUOUS" in d["status"].upper() or "PARTIAL" in d["status"].upper()]
elif filter_status == "Not Found":
    filtered_decisions = [d for d in decisions if "NOT_FOUND" in d["status"].upper()]

st.write(f"Showing **{len(filtered_decisions)}** of **{len(decisions)}** requirements")

# 5. Interactive Cards List
for idx, d in enumerate(filtered_decisions, start=1):
    req_id = d.get("requirement_id", f"REQ-{idx}")
    req_text = d.get("requirement_text", "")
    curr_status = d.get("status", "NOT_FOUND")
    conf = float(d.get("confidence", 1.0))
    layer = d.get("resolving_layer", "N/A")
    reasoning = d.get("reasoning", "")
    evidence_list = d.get("evidence", [])
    review_notes = d.get("review_notes", "")

    with st.expander(f"**{req_id}**: {req_text[:80]}...", expanded=(d.get("needs_review") or conf < 0.70)):
        card_col1, card_col2 = st.columns([3, 2])

        with card_col1:
            st.markdown(f"**Requirement:** {req_text}")
            st.markdown(f"**Status:** {render_status_pill(curr_status)} | **Confidence:** {render_confidence_badge(conf)} | **Layer:** `{layer}`", unsafe_allow_html=True)
            st.markdown(f"**AI Reasoning:** {reasoning}")

            if evidence_list:
                st.markdown("**📌 Source Provenance Evidence:**")
                for ev in evidence_list:
                    citation = ev.get("citation", "Document")
                    val = ev.get("value", "")
                    ev_reasoning = ev.get("reasoning", "")
                    st.info(f"📍 **{citation}**: `{val}`\n\n_{ev_reasoning}_")
            else:
                st.caption("No specific source citation available (Specification was not identified in PDF).")

            if review_notes:
                st.markdown(f"✍️ **Existing Reviewer Note:** `{review_notes}`")

        with card_col2:
            st.markdown("##### ✏️ Human Review Actions")
            action_col1, action_col2 = st.columns(2)
            with action_col1:
                if st.button("✅ Approve", key=f"app_{req_id}", use_container_width=True):
                    client.submit_review(run_id, [{
                        "requirement_id": req_id,
                        "status": curr_status,
                        "confidence": 1.0,
                        "review_notes": "Manually approved by tender reviewer.",
                    }])
                    st.toast(f"Approved {req_id}", icon="✅")
                    st.rerun()

            with action_col2:
                if st.button("❌ Reject", key=f"rej_{req_id}", use_container_width=True):
                    client.submit_review(run_id, [{
                        "requirement_id": req_id,
                        "status": "NON_COMPLIANT",
                        "confidence": 1.0,
                        "review_notes": "Marked non-compliant by tender reviewer.",
                    }])
                    st.toast(f"Rejected {req_id}", icon="❌")
                    st.rerun()

            # Override dropdown
            override_status = st.selectbox(
                "Override Compliance Status:",
                options=["COMPLIANT", "PARTIALLY_COMPLIANT", "NON_COMPLIANT", "AMBIGUOUS", "NOT_FOUND"],
                index=0,
                key=f"ov_sel_{req_id}",
            )
            note_input = st.text_input("Reviewer Clarification / Remarks:", key=f"note_{req_id}", placeholder="e.g. Approved per vendor addendum")

            if st.button("Save Override", key=f"save_ov_{req_id}", type="primary", use_container_width=True):
                client.submit_review(run_id, [{
                    "requirement_id": req_id,
                    "status": override_status,
                    "confidence": 1.0,
                    "review_notes": note_input or "Manual override applied.",
                }])
                st.toast(f"Updated {req_id} to {override_status}!", icon="💾")
                st.rerun()
