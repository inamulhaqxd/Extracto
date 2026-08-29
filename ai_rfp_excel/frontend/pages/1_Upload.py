import streamlit as st

from ai_rfp_excel.frontend.api_client import APIClient
from ai_rfp_excel.frontend.components import render_error_card, render_health_indicator

st.set_page_config(page_title="Upload & Configure Run", page_icon="📤", layout="wide")

client: APIClient = st.session_state.get("api_client", APIClient())
health = client.check_health()
render_health_indicator(health)

if not st.session_state.get("authenticated"):
    st.warning("⚠️ Please log in from the main page to upload documents.")
    st.page_link("streamlit_app.py", label="Go to Login Screen", icon="🔐")
    st.stop()

st.title("📤 Upload Documents & Configure Run")
st.markdown("Select an AI model, upload your technical PDF datasheet, and provide the Excel RFP template.")
st.markdown("---")

# 1. AI Model Selection Section
st.subheader("1. Select Local AI Model")
models = client.get_models()
if not models:
    # Default fallback models
    models = [
        {"model_tag": "qwen3:4b", "tag": "qwen3:4b", "display_name": "Qwen 3 4B (Default)", "ram_usage": "2.5GB", "context_length": "262K", "is_available": True},
        {"model_tag": "qwen2.5:3b", "tag": "qwen2.5:3b", "display_name": "Qwen 2.5 3B", "ram_usage": "1.9GB", "context_length": "128K", "is_available": True},
        {"model_tag": "phi3.5:3.8b", "tag": "phi3.5:3.8b", "display_name": "Phi-3.5 Mini 3.8B", "ram_usage": "2.2GB", "context_length": "128K", "is_available": True},
        {"model_tag": "gemma3:4b", "tag": "gemma3:4b", "display_name": "Gemma 3 4B", "ram_usage": "2.5GB", "context_length": "8K", "is_available": True},
        {"model_tag": "llama3.2:3b", "tag": "llama3.2:3b", "display_name": "Llama 3.2 3B", "ram_usage": "2.0GB", "context_length": "128K", "is_available": True},
    ]

model_options = {}
for m in models:
    if isinstance(m, dict):
        tag = m.get("model_tag") or m.get("tag", "")
        name = m.get("display_name") or m.get("name", tag)
        ram = m.get("ram_usage") or f"~{m.get('ram_required_gb', 4)}GB"
        ctx = m.get("context_length") or str(m.get("context_window", "32K"))
        label = f"{name} ({tag}) - RAM: {ram}, Context: {ctx}"
        model_options[label] = m

selected_label = st.selectbox(
    "Choose inference model for complex requirement evaluation:",
    options=list(model_options.keys()),
    index=0,
    help="Higher parameter models offer higher reasoning capability for ambiguous technical specifications.",
)

selected_model_data = model_options[selected_label]
if not selected_model_data.get("is_available", True):
    st.warning(f"⚠️ Model `{selected_model_data['model_tag']}` is not currently downloaded in local Ollama. The system will attempt to load or use available fallbacks.")

# Vendor Name
vendor_name = st.text_input("Target Vendor or OEM Name (Optional):", placeholder="e.g. Dell PowerStore, HPE ProLiant, Cisco UCS")

st.markdown("---")

# 2. File Upload Widgets
st.subheader("2. Upload Reference PDF & Target Excel Workbook")
col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 📄 Technical Reference PDF")
    st.caption("Upload product datasheets, hardware manuals, or architecture whitepapers.")
    pdf_file = st.file_uploader("Upload PDF Document", type=["pdf"], key="upload_pdf")

with col2:
    st.markdown("#### 📑 RFP Excel Template")
    st.caption("Upload the customer's response workbook (.xlsx, .xlsm).")
    excel_file = st.file_uploader("Upload Excel Template", type=["xlsx", "xlsm", "xls"], key="upload_excel")

st.markdown("---")

# 3. Submission button
if st.button("🚀 Start Compliance Evaluation Run", type="primary", use_container_width=True):
    if not pdf_file or not excel_file:
        render_error_card("Missing Files", "Both a reference PDF and an Excel template workbook must be selected.")
    else:
        with st.spinner("Uploading and analyzing files..."):
            try:
                # 1. Upload PDF
                pdf_bytes = pdf_file.getvalue()
                pdf_res = client.upload_pdf(pdf_bytes, pdf_file.name)
                pdf_id = str(pdf_res.get("document_id") or "")

                # 2. Upload Excel
                excel_bytes = excel_file.getvalue()
                excel_res = client.upload_excel(excel_bytes, excel_file.name)
                excel_id = str(excel_res.get("workbook_id") or "")

                # 3. Create Run
                model_tag_val = selected_model_data.get("model_tag")
                chosen_model: str | None = str(model_tag_val) if model_tag_val is not None else None

                run_res = client.create_run(
                    pdf_document_id=pdf_id,
                    workbook_id=excel_id,
                    model_name=chosen_model,
                    vendor_name=vendor_name or None,
                )

                run_id = str(run_res.get("run_id") or "")
                st.session_state["current_run_id"] = run_id
                st.session_state["active_pdf_filename"] = pdf_file.name
                st.session_state["active_excel_filename"] = excel_file.name

                st.success(f"Run {run_id} started successfully!")
                st.page_link("pages/2_Processing.py", label="View Live Processing Progress ➡️", icon="⚡")

            except Exception as e:
                render_error_card("Processing Launch Error", str(e), "Verify backend connectivity and file formats.")
