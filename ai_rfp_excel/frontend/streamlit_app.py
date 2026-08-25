import os
import time
from datetime import datetime
from typing import Optional

import httpx
import streamlit as st

FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8000")

st.set_page_config(
    page_title="AI RFP Excel Generator",
    page_icon=":bar_chart:",
    layout="wide",
)


def init_session_state():
    defaults = {
        "token": None,
        "user": None,
        "current_page": "upload",
        "processing_run_id": None,
        "processing_status": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


def api_request(method: str, endpoint: str, data: dict = None, files: dict = None) -> Optional[dict]:
    headers = {}
    if st.session_state.token:
        headers["Authorization"] = f"Bearer {st.session_state.token}"

    try:
        url = f"{FASTAPI_URL}{endpoint}"
        if method == "GET":
            response = httpx.get(url, headers=headers, timeout=30.0)
        elif method == "POST":
            response = httpx.post(url, json=data, headers=headers, timeout=30.0)
        elif method == "DELETE":
            response = httpx.delete(url, headers=headers, timeout=30.0)
        else:
            return None

        if response.status_code == 200 or response.status_code == 201:
            return response.json()
        elif response.status_code == 401:
            st.session_state.token = None
            st.session_state.user = None
            st.error("Session expired. Please log in again.")
            return None
        else:
            st.error(f"API Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.error(f"Connection error: {str(e)}")
        return None


def login_page():
    st.title("AI RFP Excel Generator")
    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        tab_login, tab_register = st.tabs(["Login", "Register"])

        with tab_login:
            st.subheader("Login")
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")

            if st.button("Login", use_container_width=True):
                if email and password:
                    result = api_request("POST", "/auth/login", {
                        "email": email,
                        "password": password,
                    })
                    if result:
                        st.session_state.token = result["access_token"]
                        st.session_state.user = result["user"]
                        st.rerun()
                else:
                    st.warning("Please enter email and password")

        with tab_register:
            st.subheader("Register")
            name = st.text_input("Name", key="register_name")
            email = st.text_input("Email", key="register_email")
            password = st.text_input("Password", type="password", key="register_password")
            confirm_password = st.text_input("Confirm Password", type="password", key="register_confirm")

            if st.button("Register", use_container_width=True):
                if name and email and password:
                    if password != confirm_password:
                        st.error("Passwords do not match")
                    else:
                        result = api_request("POST", "/auth/register", {
                            "name": name,
                            "email": email,
                            "password": password,
                        })
                        if result:
                            st.session_state.token = result["access_token"]
                            st.session_state.user = result["user"]
                            st.success("Registration successful!")
                            st.rerun()
                else:
                    st.warning("Please fill in all fields")


def check_health():
    try:
        response = httpx.get(f"{FASTAPI_URL}/health", timeout=5.0)
        return response.json()
    except Exception:
        return {"status": "unreachable"}


def sidebar():
    with st.sidebar:
        st.header("System Status")
        health = check_health()

        if health.get("status") == "healthy":
            st.success("System: Healthy")
        elif health.get("status") == "degraded":
            st.warning("System: Degraded")
        else:
            st.error("System: Unreachable")

        if health.get("ollama") == "healthy":
            st.success("Ollama: Connected")
        else:
            st.error("Ollama: Disconnected")

        if health.get("database") == "healthy":
            st.success("Database: Connected")
        else:
            st.error("Database: Disconnected")

        st.markdown("---")

        if st.session_state.user:
            st.info(f"Logged in as: {st.session_state.user.get('name', 'User')}")
            if st.session_state.user.get("is_admin"):
                st.caption("Admin")

            if st.button("Logout"):
                st.session_state.token = None
                st.session_state.user = None
                st.rerun()


def upload_page():
    st.header("Upload Files")

    col1, col2 = st.columns(2)

    with col1:
        pdf_file = st.file_uploader("Reference PDF", type=["pdf"])

    with col2:
        excel_file = st.file_uploader("Excel Template", type=["xlsx", "xls"])

    st.markdown("---")

    col_model1, col_model2 = st.columns([2, 1])

    with col_model1:
        models = [
            "qwen3:4b",
            "qwen2.5:3b",
            "phi3.5:3.8b",
            "gemma3:4b",
            "llama3.2:3b",
        ]
        model_labels = {
            "qwen3:4b": "Qwen 3 4B - 2.5GB RAM, 262K context",
            "qwen2.5:3b": "Qwen 2.5 3B - 1.8GB RAM, 32K context",
            "phi3.5:3.8b": "Phi-3.5 Mini 3.8B - 2.2GB RAM, 128K context",
            "gemma3:4b": "Gemma 3 4B - 2.4GB RAM, 32K context",
            "llama3.2:3b": "Llama 3.2 3B - 1.7GB RAM, 128K context",
        }

        selected_model = st.selectbox(
            "AI Model",
            models,
            format_func=lambda x: model_labels.get(x, x),
            index=0,
        )

    with col_model2:
        st.markdown("&nbsp;")
        st.caption("Select model for processing")

    if pdf_file and excel_file:
        st.success(f"PDF: {pdf_file.name} | Excel: {excel_file.name}")

        if st.button("Start Processing", type="primary", use_container_width=True):
            with st.spinner("Uploading files..."):
                files = {
                    "pdf": (pdf_file.name, pdf_file.getvalue(), "application/pdf"),
                    "excel": (excel_file.name, excel_file.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                }

                try:
                    headers = {}
                    if st.session_state.token:
                        headers["Authorization"] = f"Bearer {st.session_state.token}"

                    response = httpx.post(
                        f"{FASTAPI_URL}/process",
                        files=files,
                        data={"model": selected_model},
                        headers=headers,
                        timeout=60.0,
                    )

                    if response.status_code == 200:
                        result = response.json()
                        st.session_state.processing_run_id = result.get("run_id")
                        st.session_state.processing_status = "processing"
                        st.success("Processing started!")
                        st.rerun()
                    else:
                        st.error(f"Failed to start processing: {response.text}")
                except Exception as e:
                    st.error(f"Error: {str(e)}")


def processing_page():
    run_id = st.session_state.processing_run_id

    if not run_id:
        st.info("No processing job active. Upload files to start.")
        return

    st.header("Processing")

    headers = {}
    if st.session_state.token:
        headers["Authorization"] = f"Bearer {st.session_state.token}"

    try:
        resp = httpx.get(f"{FASTAPI_URL}/process/{run_id}/status", headers=headers, timeout=10.0)
        status_data = resp.json()
    except Exception:
        status_data = {"status": "UNKNOWN", "progress": 0, "current_step": "Connecting..."}

    progress = status_data.get("progress", 0)
    step = status_data.get("current_step", "Waiting...")
    status = status_data.get("status", "UNKNOWN")

    progress_bar = st.progress(progress)
    status_text = st.empty()
    status_text.text(step)

    if status == "COMPLETED":
        progress_bar.progress(1.0)
        status_text.text("Done!")
        st.success("Processing completed successfully!")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Review Results"):
                st.session_state.current_page = "review"
                st.rerun()
        with col2:
            try:
                dl_resp = httpx.get(
                    f"{FASTAPI_URL}/process/{run_id}/download",
                    headers=headers,
                    timeout=30.0,
                    follow_redirects=True,
                )
                if dl_resp.status_code == 200:
                    st.download_button(
                        label="Download Excel",
                        data=dl_resp.content,
                        file_name=f"compliance_result_{run_id[:8]}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                else:
                    st.error("Download not available yet")
            except Exception as e:
                st.error(f"Download error: {e}")

    elif status == "FAILED":
        progress_bar.progress(0)
        st.error(f"Processing failed: {status_data.get('error_message', 'Unknown error')}")

    else:
        st.rerun()


def review_page():
    st.header("Review Results")

    st.info("Review workflow will show compliance results with evidence")

    st.markdown("---")

    st.subheader("Sample Review Item")

    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        st.markdown("**Requirement:** Minimum 32 cores per controller")
        st.markdown("**Result:** COMPLIANT")
        st.markdown("**Confidence:** 95%")
        st.markdown("**Evidence:** 32 cores per controller found on Page 15, Table T15-02")

    with col2:
        if st.button("Approve", key="approve_1"):
            st.success("Approved!")

    with col3:
        if st.button("Reject", key="reject_1"):
            st.error("Rejected!")

    st.markdown("---")

    col_bulk1, col_bulk2, col_bulk3 = st.columns(3)

    with col_bulk1:
        if st.button("Approve All High Confidence"):
            st.success("All high confidence results approved!")

    with col_bulk2:
        if st.button("Approve All Compliant"):
            st.success("All compliant results approved!")

    with col_bulk3:
        if st.button("Generate Excel"):
            st.info("Excel generation will be triggered")


def history_page():
    st.header("Processing History")

    col1, col2 = st.columns([3, 1])

    with col1:
        search = st.text_input("Search by filename")

    with col2:
        st.markdown("&nbsp;")
        filter_status = st.selectbox("Filter by status", ["All", "Completed", "Processing", "Failed"])

    st.markdown("---")

    st.info("Processing history will be loaded from the database")

    sample_history = [
        {"filename": "RFP_v1.pdf + Template_v1.xlsx", "status": "Completed", "date": "2026-08-25", "run_id": "1"},
        {"filename": "RFP_v2.pdf + Template_v1.xlsx", "status": "Processing", "date": "2026-08-25", "run_id": "2"},
    ]

    for item in sample_history:
        col1, col2, col3, col4 = st.columns([4, 1, 1, 1])

        with col1:
            st.markdown(f"**{item['filename']}**")

        with col2:
            if item["status"] == "Completed":
                st.success(item["status"])
            elif item["status"] == "Processing":
                st.warning(item["status"])
            else:
                st.error(item["status"])

        with col3:
            st.caption(item["date"])

        with col4:
            if st.button("View", key=f"view_{item['run_id']}"):
                st.info(f"Viewing run {item['run_id']}")


def settings_page():
    st.header("Settings")

    tab_model, tab_account = st.tabs(["AI Model", "Account"])

    with tab_model:
        st.subheader("AI Model Settings")

        models = [
            "qwen3:4b",
            "qwen2.5:3b",
            "phi3.5:3.8b",
            "gemma3:4b",
            "llama3.2:3b",
        ]
        model_labels = {
            "qwen3:4b": "Qwen 3 4B - 2.5GB RAM, 262K context",
            "qwen2.5:3b": "Qwen 2.5 3B - 1.8GB RAM, 32K context",
            "phi3.5:3.8b": "Phi-3.5 Mini 3.8B - 2.2GB RAM, 128K context",
            "gemma3:4b": "Gemma 3 4B - 2.4GB RAM, 32K context",
            "llama3.2:3b": "Llama 3.2 3B - 1.7GB RAM, 128K context",
        }

        current_model = st.session_state.user.get("preferred_model", "qwen3:4b") if st.session_state.user else "qwen3:4b"

        default_model = st.selectbox(
            "Default Model",
            models,
            format_func=lambda x: model_labels.get(x, x),
            index=models.index(current_model) if current_model in models else 0,
        )

        if st.button("Save Default Model"):
            st.success(f"Default model saved: {default_model}")

        st.markdown("---")

        st.subheader("Model Availability")
        st.info("Run `ollama pull <model>` to download models")

        for model in models:
            st.code(f"ollama pull {model}", language="bash")

    with tab_account:
        st.subheader("Account Settings")

        if st.session_state.user:
            st.info(f"Name: {st.session_state.user.get('name')}")
            st.info(f"Email: {st.session_state.user.get('email')}")
            st.info(f"Role: {'Admin' if st.session_state.user.get('is_admin') else 'User'}")

        st.markdown("---")
        st.caption("Contact admin to reset password")


def main():
    if not st.session_state.token:
        login_page()
        return

    sidebar()

    page = st.session_state.get("current_page", "upload")

    if st.session_state.processing_status == "processing":
        processing_page()
        return

    tab1, tab2, tab3, tab4 = st.tabs(["Upload", "Review", "History", "Settings"])

    with tab1:
        upload_page()

    with tab2:
        review_page()

    with tab3:
        history_page()

    with tab4:
        settings_page()


if __name__ == "__main__":
    main()
