import streamlit as st

from ai_rfp_excel.frontend.api_client import APIClient
from ai_rfp_excel.frontend.components import render_error_card, render_health_indicator

st.set_page_config(page_title="Settings & System Diagnostics", page_icon="⚙️", layout="wide")

client: APIClient = st.session_state.get("api_client", APIClient())
health = client.check_health()
render_health_indicator(health)

if not st.session_state.get("authenticated"):
    st.warning("⚠️ Please log in to view settings.")
    st.page_link("streamlit_app.py", label="Go to Login Screen", icon="🔐")
    st.stop()

st.title("⚙️ System Settings & AI Model Preferences")
st.markdown("Configure default local AI models and inspect system infrastructure diagnostics.")
st.markdown("---")

# 1. AI Model Preference
st.subheader("1. Default AI Model Preference")
st.caption("Choose which local model is pre-selected for compliance reasoning during new evaluation runs.")

models = client.get_models()
if not models:
    models = [
        {"model_tag": "qwen3:4b", "display_name": "Qwen 3 4B (Recommended Default)", "ram_required_gb": 4.5, "context_window": 32768, "is_available": True},
        {"model_tag": "qwen2.5:3b", "display_name": "Qwen 2.5 3B", "ram_required_gb": 3.5, "context_window": 32768, "is_available": True},
        {"model_tag": "phi3.5:3.8b", "display_name": "Phi-3.5 Mini 3.8B", "ram_required_gb": 4.0, "context_window": 128000, "is_available": True},
        {"model_tag": "gemma3:4b", "display_name": "Gemma 3 4B", "ram_required_gb": 4.5, "context_window": 8192, "is_available": True},
        {"model_tag": "llama3.2:3b", "display_name": "Llama 3.2 3B", "ram_required_gb": 3.5, "context_window": 8192, "is_available": True},
    ]

model_map = {m["model_tag"]: m for m in models}
model_tags = list(model_map.keys())

selected_tag = st.selectbox(
    "Default AI Model:",
    options=model_tags,
    format_func=lambda tag: f"{model_map[tag]['display_name']} ({tag}) - RAM: ~{model_map[tag].get('ram_required_gb', 4)}GB, Context: {model_map[tag].get('context_window', 32768)}",
    index=0,
)

if st.button("💾 Save Default Model Preference", type="primary"):
    if client.set_model_preference(selected_tag):
        st.success(f"Default model preference saved as `{selected_tag}`!")
    else:
        render_error_card("Failed to Save", "Could not persist model preference to backend.")

st.markdown("---")

# 2. Supported Local Models Catalog
st.subheader("2. Supported Local Models Catalog")
col1, col2 = st.columns(2)

for idx, m in enumerate(models):
    target_col = col1 if idx % 2 == 0 else col2
    with target_col:
        st.markdown(
            f'<div style="border:1px solid #e9ecef; border-radius:6px; padding:12px; margin-bottom:10px; background-color:#fdfdfd;">'
            f'<strong>{m["display_name"]}</strong> (<code>{m["model_tag"]}</code>)<br>'
            f'<small>RAM Required: ~{m.get("ram_required_gb", "4")}GB | Context Window: {m.get("context_window", "32768")} tokens</small>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown("---")

# 3. Backend Health & Infrastructure Diagnostics
st.subheader("3. System Diagnostics & Services Health")
st.json(health)
