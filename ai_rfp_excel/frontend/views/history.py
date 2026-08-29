import streamlit as st
import streamlit_antd_components as sac

from ai_rfp_excel.frontend.api_client import APIClient
from ai_rfp_excel.frontend.components import (
    render_header,
    render_status_pill,
)


def render_history(client: APIClient) -> None:
    """Render past evaluation runs history and download manager."""
    render_header(
        title="Evaluation Run History",
        subtitle="Search past runs, review compliance determinations, and download populated workbooks.",
        tag_text="Archive",
    )

    # Filter and Search Controls
    col_search, col_filter = st.columns([1.5, 1], gap="medium")

    with col_search:
        search_query = st.text_input(
            "Search Runs",
            placeholder="Search by file name, vendor, model, or run ID...",
            key="history_search_input",
        )

    with col_filter:
        filter_opts = ["All", "Completed", "Processing", "Cancelled", "Failed"]
        selected_status = sac.segmented(
            items=[sac.SegmentedItem(label=opt) for opt in filter_opts],
            index=0,
            size="sm",
            return_index=False,
            key="history_status_filter_segmented",
        )

    # Fetch runs
    status_filter = str(selected_status) if selected_status != "All" else None
    runs = client.list_runs(status_filter=status_filter)

    # Apply keyword search
    if search_query:
        q = search_query.lower().strip()
        runs = [
            r for r in runs
            if q in str(r.get("pdf_filename", "")).lower()
            or q in str(r.get("workbook_filename", "")).lower()
            or q in str(r.get("model_used", "")).lower()
            or q in str(r.get("vendor_name", "")).lower()
            or q in str(r.get("run_id", "")).lower()
        ]

    if not runs:
        with st.container(border=True):
            st.markdown(
                """
                <div style="text-align: center; padding: 24px;">
                    <div style="font-size: 16px; font-weight: 700; color: #0f172a; margin-bottom: 8px;">
                        No Evaluation Runs Found
                    </div>
                    <div style="font-size: 13px; color: #64748b; margin-bottom: 16px;">
                        No runs match the selected filter criteria or no evaluation has been initiated yet.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Start New Evaluation", type="primary", use_container_width=True):
                st.session_state["active_nav"] = "RFP Workspace"
                st.session_state["workspace_stage"] = 0
                st.rerun()
        return

    st.markdown(f"<div style='font-size:13px; color:#64748b; margin:12px 0 16px 0;'>Showing <strong>{len(runs)}</strong> evaluation runs</div>", unsafe_allow_html=True)

    # Render run cards
    for r in runs:
        r_id = str(r.get("run_id", ""))
        r_status = str(r.get("status", "unknown")).upper()
        pdf_fn = str(r.get("pdf_filename") or "Technical Datasheet")
        wb_fn = str(r.get("workbook_filename") or "RFP Template")
        gen_file = str(r.get("generated_file") or "")
        started = str(r.get("started_at") or "N/A")
        model = str(r.get("model_used") or "N/A")
        total_reqs = int(r.get("total_requirements", 0))
        comp_count = int(r.get("compliant_count", 0))
        non_comp_count = int(r.get("non_compliant_count", 0))
        amb_count = int(r.get("ambiguous_count", 0))

        with st.container(border=True):
            st.markdown(
                f"""
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px;">
                    <div>
                        <div style="font-size:15px; font-weight:700; color:#0f172a;">
                            {pdf_fn} &nbsp;&rarr;&nbsp; {wb_fn}
                        </div>
                        <div style="font-size:12px; color:#64748b; margin-top:4px;">
                            Run ID: <code>{r_id}</code> &nbsp;|&nbsp; Model: {model} &nbsp;|&nbsp; Started: {started}
                        </div>
                    </div>
                    <div>
                        {render_status_pill(r_status)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Metadata and Stats row
            if total_reqs > 0:
                s1, s2, s3, s4 = st.columns(4)
                with s1:
                    st.caption(f"**Total Specs:** {total_reqs}")
                with s2:
                    st.caption(f"**Compliant:** {comp_count}")
                with s3:
                    st.caption(f"**Non-Compliant:** {non_comp_count}")
                with s4:
                    st.caption(f"**Ambiguous/Review:** {amb_count}")

            st.markdown("<div style='margin-bottom: 8px;'></div>", unsafe_allow_html=True)

            c_act1, c_act2, c_act3 = st.columns([1.2, 1.2, 2], gap="small")

            with c_act1:
                if st.button("Open in Workspace", key=f"hist_open_{r_id}", use_container_width=True):
                    st.session_state["current_run_id"] = r_id
                    st.session_state["active_nav"] = "RFP Workspace"
                    if r_status in ("PENDING", "PROCESSING", "QUEUED"):
                        st.session_state["workspace_stage"] = 1
                    elif r_status in ("COMPLETED", "REVIEW_REQUIRED"):
                        st.session_state["workspace_stage"] = 2
                    else:
                        st.session_state["workspace_stage"] = 1
                    st.rerun()

            with c_act2:
                if gen_file and r_status == "COMPLETED":
                    file_bytes = client.download_file(gen_file)
                    if file_bytes:
                        st.download_button(
                            label="Download Excel",
                            data=file_bytes,
                            file_name=gen_file,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"hist_dl_{r_id}",
                            use_container_width=True,
                        )
                    else:
                        st.caption("File unavailable")
                else:
                    st.caption("Output file pending" if r_status != "COMPLETED" else "No file generated")

            with c_act3:
                if st.button("Re-evaluate (New Run)", key=f"hist_re_{r_id}", type="secondary"):
                    st.session_state["current_run_id"] = r_id
                    st.session_state["active_nav"] = "RFP Workspace"
                    st.session_state["workspace_stage"] = 0
                    st.rerun()
