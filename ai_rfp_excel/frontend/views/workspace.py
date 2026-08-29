import time
from typing import Any

import streamlit as st
import streamlit_antd_components as sac

from ai_rfp_excel.frontend.api_client import APIClient
from ai_rfp_excel.frontend.components import (
    render_confidence_badge,
    render_error_card,
    render_header,
    render_metric_card,
    render_status_pill,
)


def render_workspace(client: APIClient) -> None:
    """Render the unified 4-stage RFP evaluation workspace."""
    if "workspace_stage" not in st.session_state:
        st.session_state["workspace_stage"] = 0

    run_id: str | None = st.session_state.get("current_run_id")

    # Fetch latest run status if active
    run_data: dict[str, Any] | None = None
    if run_id:
        try:
            run_data = client.get_run(run_id)
        except Exception:
            run_data = None

    # Determine highest unlocked stage based on pipeline progress
    max_accessible_stage = 0
    if run_data:
        status = str(run_data.get("status", "")).lower()
        if status in ("completed", "review_required"):
            max_accessible_stage = 3
        elif status in ("processing", "pending", "queued"):
            max_accessible_stage = 1
        elif status in ("failed", "cancelled"):
            max_accessible_stage = 1

    # Automatic stage synchronization if on an invalid stage
    if st.session_state["workspace_stage"] > max_accessible_stage:
        st.session_state["workspace_stage"] = max_accessible_stage

    # Workspace Header with Stage Numbering
    stage_names = ["Upload & Configure", "Processing Monitor", "Review & Approvals", "Export & Finalize"]
    current_stage_idx = st.session_state["workspace_stage"]
    stage_numbering_text = f"Stage {current_stage_idx + 1} of 4 — {stage_names[current_stage_idx]}"

    render_header(
        title="TenderFlow Dashboard",
        subtitle=stage_numbering_text,
    )

    # Interactive Step Indicator
    steps_items: list[sac.StepsItem | dict[str, Any] | str] = [
        sac.StepsItem(title="Upload & Configure", description="Datasheet & Template", icon="cloud-upload"),
        sac.StepsItem(title="Processing Monitor", description="Real-time Pipeline", icon="activity"),
        sac.StepsItem(title="Review & Approvals", description="Compliance Verification", icon="check2-square"),
        sac.StepsItem(title="Export & Finalize", description="Excel Workbook", icon="file-earmark-arrow-down"),
    ]

    chosen_step = sac.steps(
        items=steps_items,
        index=st.session_state["workspace_stage"],
        placement="horizontal",
        size="sm",
        return_index=True,
        key="workspace_steps_nav",
    )

    # Handle manual step click with strict locking on uncompleted stages
    if chosen_step is not None and isinstance(chosen_step, int) and chosen_step != st.session_state["workspace_stage"]:
        if chosen_step <= max_accessible_stage:
            st.session_state["workspace_stage"] = chosen_step
            st.rerun()
        else:
            st.toast("This stage is locked until previous pipeline steps complete.")
            st.rerun()

    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

    # Render Active Stage
    stage = st.session_state["workspace_stage"]
    if stage == 0:
        _render_stage_upload(client)
    elif stage == 1:
        _render_stage_monitor(client, run_id, run_data)
    elif stage == 2:
        _render_stage_review(client, run_id, run_data)
    elif stage == 3:
        _render_stage_export(client, run_id, run_data)


def _render_stage_upload(client: APIClient) -> None:
    """Stage 1: Upload technical documents and launch analysis."""
    if "default_model" not in st.session_state or not st.session_state["default_model"]:
        persisted_pref = client.get_model_preference()
        st.session_state["default_model"] = persisted_pref or "qwen3:4b"

    default_model = st.session_state.get("default_model", "qwen3:4b")

    col_pdf, col_excel = st.columns([1, 1], gap="large")

    with col_pdf:
        with st.container(border=True):
            st.markdown(
                '<div style="font-size: 15px; font-weight: 700; color: var(--theme-text-primary); margin-bottom: 8px;">'
                "1. Technical Specification PDF"
                "</div>",
                unsafe_allow_html=True,
            )
            st.caption("Upload vendor datasheet, specification manual, or hardware documentation.")
            pdf_file = st.file_uploader(
                "Upload PDF Datasheet",
                type=["pdf"],
                help="Vendor datasheet or product specification manual.",
                key="workspace_pdf_uploader",
                label_visibility="collapsed",
            )

    with col_excel:
        with st.container(border=True):
            st.markdown(
                '<div style="font-size: 15px; font-weight: 700; color: var(--theme-text-primary); margin-bottom: 8px;">'
                "2. Tender RFP Workbook Template"
                "</div>",
                unsafe_allow_html=True,
            )
            st.caption("Upload customer compliance response spreadsheet to evaluate and populate.")
            excel_file = st.file_uploader(
                "Upload Excel Workbook",
                type=["xlsx", "xlsm", "xls"],
                help="Customer tender requirement response workbook.",
                key="workspace_excel_uploader",
                label_visibility="collapsed",
            )

    st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)

    # Model Selection Bar
    models = client.get_models()
    if not models:
        models = [
            {"model_tag": "qwen3:4b", "display_name": "Qwen 3 4B (Recommended)"},
            {"model_tag": "qwen2.5:3b", "display_name": "Qwen 2.5 3B"},
            {"model_tag": "phi3.5:3.8b", "display_name": "Phi-3.5 Mini 3.8B"},
            {"model_tag": "gemma3:4b", "display_name": "Gemma 3 4B"},
            {"model_tag": "llama3.2:3b", "display_name": "Llama 3.2 3B"},
        ]
    model_map: dict[str, dict[str, Any]] = {
        str(m.get("model_tag") or m.get("tag", "")): m for m in models if isinstance(m, dict)
    }
    model_tags = list(model_map.keys())
    default_idx = model_tags.index(default_model) if default_model in model_tags else 0

    chosen_model = st.selectbox(
        "Active AI Inference Model",
        options=model_tags,
        format_func=lambda tag: f"{model_map[tag].get('display_name', tag)} ({tag})",
        index=default_idx,
        key="workspace_upload_model_select",
        help="Local LLM model to execute tender evaluation. Defaults to your saved Settings preference.",
    )

    st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)

    if st.button("Start Compliance Analysis", type="primary", use_container_width=True):
        if not pdf_file or not excel_file:
            render_error_card("Missing Documents", "Both a technical reference PDF and an Excel RFP workbook must be uploaded.")
        else:
            with st.spinner("Uploading documents and initiating compliance pipeline..."):
                try:
                    pdf_bytes = pdf_file.getvalue()
                    pdf_res = client.upload_pdf(pdf_bytes, pdf_file.name)
                    pdf_id = str(pdf_res.get("document_id") or "")

                    excel_bytes = excel_file.getvalue()
                    excel_res = client.upload_excel(excel_bytes, excel_file.name)
                    excel_id = str(excel_res.get("workbook_id") or "")

                    run_res = client.create_run(
                        pdf_document_id=pdf_id,
                        workbook_id=excel_id,
                        model_name=chosen_model,
                        vendor_name=None,
                    )

                    new_run_id = str(run_res.get("run_id") or "")
                    st.session_state["current_run_id"] = new_run_id
                    st.session_state["active_pdf_filename"] = pdf_file.name
                    st.session_state["active_excel_filename"] = excel_file.name
                    st.session_state["workspace_stage"] = 1
                    st.toast("Evaluation run initiated successfully.")
                    st.rerun()

                except Exception as e:
                    render_error_card("Launch Failed", str(e), "Verify backend connectivity and uploaded file validity.")


def _render_stage_monitor(client: APIClient, run_id: str | None, run_data: dict[str, Any] | None) -> None:
    """Stage 2: Real-time progress monitoring, live logs, and cancel action."""
    if not run_id or not run_data:
        st.info("No active evaluation run in progress. Please start a new run from Stage 1.")
        if st.button("Go to Upload & Configure", type="primary"):
            st.session_state["workspace_stage"] = 0
            st.rerun()
        return

    status = str(run_data.get("status", "pending")).lower()
    progress = float(run_data.get("progress", 0.0))
    current_step = str(run_data.get("current_step", "Processing pipeline..."))
    model_used = str(run_data.get("model_used", "N/A"))
    pdf_name = str(run_data.get("pdf_filename") or st.session_state.get("active_pdf_filename", "N/A"))
    wb_name = str(run_data.get("workbook_filename") or st.session_state.get("active_excel_filename", "N/A"))

    # Top Metadata Cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(render_metric_card("Run ID", f"{run_id[:8]}...", f"Status: {status.upper()}"), unsafe_allow_html=True)
    with c2:
        st.markdown(render_metric_card("Datasheet PDF", pdf_name[:20], "Reference Document"), unsafe_allow_html=True)
    with c3:
        st.markdown(render_metric_card("RFP Template", wb_name[:20], "Target Workbook"), unsafe_allow_html=True)
    with c4:
        st.markdown(render_metric_card("AI Model", model_used, f"Progress: {int(progress)}%"), unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(
            f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">'
            f'<span style="font-size:16px; font-weight:700; color:#0f172a;">Pipeline Progress: {int(progress)}%</span>'
            f'{render_status_pill(status)}'
            f"</div>",
            unsafe_allow_html=True,
        )

        st.progress(min(1.0, max(0.0, progress / 100.0)))
        st.markdown(f"<div style='font-size:13px; color:#475569; margin-top:8px;'><strong>Active Task:</strong> {current_step}</div>", unsafe_allow_html=True)

    # Live Logs / Details Accordion
    with st.expander("Live Pipeline Step Logs", expanded=(status in ("pending", "processing", "queued"))):
        st.code(
            f"[{time.strftime('%H:%M:%S')}] Status: {status.upper()}\n"
            f"[{time.strftime('%H:%M:%S')}] Step: {current_step}\n"
            f"[{time.strftime('%H:%M:%S')}] Progress: {progress:.1f}%\n"
            f"[{time.strftime('%H:%M:%S')}] Model: {model_used}\n"
            f"[{time.strftime('%H:%M:%S')}] Document: {pdf_name}\n"
            f"[{time.strftime('%H:%M:%S')}] Workbook: {wb_name}",
            language="log",
        )

    # Action buttons based on status
    if status in ("pending", "processing", "queued"):
        col_act1, _ = st.columns([1, 4])
        with col_act1:
            if st.button("Cancel Run", type="secondary", use_container_width=True):
                if client.cancel_run(run_id):
                    st.warning("Cancellation requested.")
                    st.rerun()

        time.sleep(2.0)
        st.rerun()

    elif status == "completed":
        st.success("Pipeline analysis completed successfully.")
        if st.button("Proceed to Compliance Review", type="primary", use_container_width=True):
            st.session_state["workspace_stage"] = 2
            st.rerun()

    elif status == "cancelled":
        st.warning("This evaluation run was cancelled.")
        if st.button("Start New Run", type="primary"):
            st.session_state["workspace_stage"] = 0
            st.rerun()

    elif status == "failed":
        err = str(run_data.get("error_message") or "Unknown execution failure")
        render_error_card("Pipeline Error", err, "Review backend logs or try re-running with another model.")
        if st.button("Retry Evaluation", type="primary"):
            st.session_state["workspace_stage"] = 0
            st.rerun()


def _render_stage_review(client: APIClient, run_id: str | None, run_data: dict[str, Any] | None) -> None:
    """Stage 3: Review specification citations, AI reasoning, and inline human overrides."""
    if not run_id or not run_data:
        st.info("No completed evaluation run to review. Please select or complete a run first.")
        return

    if run_data.get("status") not in ("completed", "review_required"):
        st.warning(f"Run is currently in `{run_data.get('status')}` state. Please wait for completion.")
        if st.button("View Processing Monitor"):
            st.session_state["workspace_stage"] = 1
            st.rerun()
        return

    decisions: list[dict[str, Any]] = run_data.get("decisions", [])

    # KPI Stat Row
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1:
        st.markdown(render_metric_card("Total Reqs", run_data.get("total_requirements", 0)), unsafe_allow_html=True)
    with k2:
        st.markdown(render_metric_card("Compliant", run_data.get("compliant_count", 0), status="success"), unsafe_allow_html=True)
    with k3:
        st.markdown(render_metric_card("Non-Compliant", run_data.get("non_compliant_count", 0), status="danger"), unsafe_allow_html=True)
    with k4:
        st.markdown(render_metric_card("Ambiguous", run_data.get("ambiguous_count", 0), status="warning"), unsafe_allow_html=True)
    with k5:
        st.markdown(render_metric_card("Not Found", run_data.get("not_found_count", 0)), unsafe_allow_html=True)
    with k6:
        st.markdown(render_metric_card("Needs Review", run_data.get("low_confidence_count", 0), status="warning"), unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 16px;'></div>", unsafe_allow_html=True)

    # Bulk Approval Toolbar
    with st.container(border=True):
        st.markdown('<div style="font-size: 14px; font-weight: 700; color: #0f172a; margin-bottom: 8px;">Bulk Approvals</div>', unsafe_allow_html=True)
        b1, b2, b3 = st.columns([1.5, 1.5, 3])
        with b1:
            if st.button("Approve High-Confidence (>=90%)", use_container_width=True):
                updates = [
                    {"requirement_id": d["requirement_id"], "status": d["status"], "confidence": d.get("confidence", 1.0), "review_notes": "Bulk approved high-confidence item."}
                    for d in decisions
                    if float(d.get("confidence", 0.0)) >= 0.90
                ]
                if updates:
                    client.submit_review(run_id, updates)
                    st.toast(f"Approved {len(updates)} requirements.")
                    st.rerun()
        with b2:
            if st.button("Approve All Compliant Items", use_container_width=True):
                updates = [
                    {"requirement_id": d["requirement_id"], "status": "COMPLIANT", "confidence": d.get("confidence", 1.0), "review_notes": "Bulk approved compliant item."}
                    for d in decisions
                    if "COMPLIANT" in str(d.get("status", "")).upper() and "NON" not in str(d.get("status", "")).upper()
                ]
                if updates:
                    client.submit_review(run_id, updates)
                    st.toast(f"Approved {len(updates)} compliant requirements.")
                    st.rerun()
        with b3:
            st.caption("Approved requirements are immediately recorded and prepared for export.")

    st.markdown("<div style='margin-bottom: 16px;'></div>", unsafe_allow_html=True)

    # Filter by compliance status using sac.segmented
    filter_opts = ["All", "Needs Review", "Compliant", "Non-Compliant", "Ambiguous", "Not Found"]
    selected_filter = sac.segmented(
        items=[sac.SegmentedItem(label=opt) for opt in filter_opts],
        index=0,
        size="sm",
        return_index=False,
        key="review_filter_segmented",
    )

    filtered_decisions = decisions
    if selected_filter == "Needs Review":
        filtered_decisions = [d for d in decisions if d.get("needs_review") or float(d.get("confidence", 1.0)) < 0.70]
    elif selected_filter == "Compliant":
        filtered_decisions = [d for d in decisions if "COMPLIANT" in str(d.get("status", "")).upper() and "NON" not in str(d.get("status", "")).upper()]
    elif selected_filter == "Non-Compliant":
        filtered_decisions = [d for d in decisions if "NON_COMPLIANT" in str(d.get("status", "")).upper() or "NON-COMPLIANT" in str(d.get("status", "")).upper()]
    elif selected_filter == "Ambiguous":
        filtered_decisions = [d for d in decisions if "AMBIGUOUS" in str(d.get("status", "")).upper() or "PARTIAL" in str(d.get("status", "")).upper()]
    elif selected_filter == "Not Found":
        filtered_decisions = [d for d in decisions if "NOT_FOUND" in str(d.get("status", "")).upper()]

    st.markdown(f"<div style='font-size:13px; color:#64748b; margin:8px 0 16px 0;'>Showing <strong>{len(filtered_decisions)}</strong> of <strong>{len(decisions)}</strong> requirements</div>", unsafe_allow_html=True)

    for idx, d in enumerate(filtered_decisions, start=1):
        req_id = str(d.get("requirement_id", f"REQ-{idx}"))
        req_text = str(d.get("requirement_text", ""))
        curr_status = str(d.get("status", "NOT_FOUND"))
        matched_val = str(d.get("matched_value") or "")
        conf = float(d.get("confidence", 1.0))
        layer = str(d.get("resolving_layer", "N/A"))
        reasoning = str(d.get("reasoning", ""))
        evidence_list: list[dict[str, Any]] = d.get("evidence", [])
        review_notes = str(d.get("review_notes", ""))

        exp_title = f"{req_id}: {req_text[:80]}..."
        with st.expander(exp_title, expanded=(d.get("needs_review") or conf < 0.70)):
            card_col1, card_col2 = st.columns([3, 2], gap="medium")

            with card_col1:
                st.markdown(f"**Requirement:** {req_text}")
                st.markdown(
                    f"**Status:** {render_status_pill(curr_status)} &nbsp;|&nbsp; "
                    f"**Confidence:** {render_confidence_badge(conf)} &nbsp;|&nbsp; "
                    f"**Layer:** `{layer}`",
                    unsafe_allow_html=True,
                )
                if matched_val:
                    st.markdown(f"**AI Populated Specification / Value:** `{matched_val}`")

                if reasoning:
                    st.markdown(f"**AI Reasoning:** {reasoning}")

                if evidence_list:
                    st.markdown("**Source Provenance Evidence:**")
                    for ev in evidence_list:
                        citation = ev.get("citation", "PDF Reference")
                        val = ev.get("value", "")
                        ev_reason = ev.get("reasoning", "")
                        st.info(f"**{citation}**: `{val}`\n\n_{ev_reason}_")
                    else:
                        st.caption("No direct citation identified in reference datasheet.")

                if review_notes:
                    st.markdown(f"**Reviewer Remarks:** `{review_notes}`")

            with card_col2:
                st.markdown('<div style="font-size: 13px; font-weight: 700; color: #0f172a; margin-bottom: 8px;">Review Actions</div>', unsafe_allow_html=True)
                act1, act2 = st.columns(2)
                with act1:
                    if st.button("Approve", key=f"ws_app_{req_id}", use_container_width=True):
                        client.submit_review(run_id, [{
                            "requirement_id": req_id,
                            "status": curr_status,
                            "matched_value": matched_val,
                            "confidence": 1.0,
                            "review_notes": "Approved by reviewer.",
                        }])
                        st.toast(f"Approved {req_id}.")
                        st.rerun()

                with act2:
                    if st.button("Mark Non-Compliant", key=f"ws_rej_{req_id}", use_container_width=True):
                        client.submit_review(run_id, [{
                            "requirement_id": req_id,
                            "status": "NON_COMPLIANT",
                            "matched_value": matched_val,
                            "confidence": 1.0,
                            "review_notes": "Marked non-compliant by reviewer.",
                        }])
                        st.toast(f"Marked {req_id} non-compliant.")
                        st.rerun()

                override_sel = st.selectbox(
                    "Override Status",
                    options=["COMPLIANT", "PARTIALLY_COMPLIANT", "NON_COMPLIANT", "AMBIGUOUS", "NOT_FOUND"],
                    index=0,
                    key=f"ws_ov_sel_{req_id}",
                )
                override_val = st.text_input("Edit Offered Spec", value=matched_val, key=f"ws_val_{req_id}", placeholder="e.g. 128GB DDR5 4800MHz")
                remarks = st.text_input("Clarification Note", key=f"ws_rem_{req_id}", placeholder="e.g. Approved per vendor spec sheet addendum")

                if st.button("Save Override", key=f"ws_save_{req_id}", type="primary", use_container_width=True):
                    client.submit_review(run_id, [{
                        "requirement_id": req_id,
                        "status": override_sel,
                        "matched_value": override_val or matched_val,
                        "confidence": 1.0,
                        "review_notes": remarks or "Manual override applied.",
                    }])
                    st.toast(f"Updated {req_id}.")
                    st.rerun()

    st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)
    if st.button("Proceed to Export & Finalize", type="primary", use_container_width=True, key="ws_btn_proceed_export"):
        st.session_state["workspace_stage"] = 3
        st.rerun()


def _render_stage_export(client: APIClient, run_id: str | None, run_data: dict[str, Any] | None) -> None:
    """Stage 4: Compliance summary overview, direct Excel workbook download, and restart."""
    if not run_id or not run_data:
        st.info("No evaluation data available to export. Please start a run from Stage 1.")
        return

    generated_file = str(run_data.get("generated_file") or "")
    total_reqs = int(run_data.get("total_requirements", 0))
    comp_count = int(run_data.get("compliant_count", 0))
    non_comp_count = int(run_data.get("non_compliant_count", 0))
    comp_rate = (comp_count / total_reqs * 100.0) if total_reqs > 0 else 0.0

    col_sum, col_dl = st.columns([1.2, 1], gap="large")

    with col_sum:
        with st.container(border=True):
            st.markdown(
                '<div style="font-size: 16px; font-weight: 700; color: #0f172a; margin-bottom: 12px;">'
                "Compliance Summary Report"
                "</div>",
                unsafe_allow_html=True,
            )

            st.markdown(render_metric_card("Overall Compliance", f"{comp_rate:.1f}%", f"{comp_count} of {total_reqs} specs satisfied", status="success" if comp_rate >= 80 else "warning"), unsafe_allow_html=True)

            st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)
            st.markdown(
                f"""
                <ul style="padding-left: 18px; font-size: 13px; color: #334155; line-height: 1.8;">
                    <li><strong>Total Specifications Evaluated:</strong> {total_reqs}</li>
                    <li><strong>Compliant Specifications:</strong> {comp_count}</li>
                    <li><strong>Non-Compliant Specifications:</strong> {non_comp_count}</li>
                    <li><strong>Ambiguous / Needs Review:</strong> {run_data.get('ambiguous_count', 0) + run_data.get('low_confidence_count', 0)}</li>
                </ul>
                """,
                unsafe_allow_html=True,
            )

    with col_dl:
        with st.container(border=True):
            st.markdown(
                '<div style="font-size: 16px; font-weight: 700; color: #0f172a; margin-bottom: 12px;">'
                "Download Populated Workbook"
                "</div>",
                unsafe_allow_html=True,
            )
            st.caption("Includes original sheet formatting, formula structures, filled compliance responses, and citation audit trail.")

            if generated_file:
                file_bytes = client.download_file(generated_file)
                if file_bytes:
                    st.download_button(
                        label="Download Populated Excel (.xlsx)",
                        data=file_bytes,
                        file_name=generated_file,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True,
                    )
                else:
                    st.warning("File is generating or temporarily unavailable for download.")
            else:
                st.info("Output file will be available once evaluation completes.")

    st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)

    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("Return to Review Workspace", use_container_width=True):
            st.session_state["workspace_stage"] = 2
            st.rerun()

    with col_btn2:
        if st.button("Start New Evaluation", use_container_width=True, type="secondary"):
            st.session_state["current_run_id"] = None
            st.session_state["workspace_stage"] = 0
            st.rerun()
