from typing import Any

import streamlit as st

from ai_rfp_excel.frontend.api_client import APIClient
from ai_rfp_excel.frontend.components import (
    render_header,
    render_metric_card,
)


def render_settings(client: APIClient) -> None:
    """Render system settings, Ollama model configurations, and backend diagnostics."""
    render_header(
        title="System Settings & Model Configuration",
        subtitle="Configure local Ollama AI models, manage inference preferences, and inspect system health diagnostics.",
        tag_text="Settings",
    )

    # 1. AI Model Selection & Preference
    with st.container(border=True):
        st.markdown(
            '<div style="font-size: 16px; font-weight: 700; color: #0f172a; margin-bottom: 8px;">'
            "Default Inference Model Preference"
            "</div>",
            unsafe_allow_html=True,
        )
        st.caption("Select the default local LLM used for complex technical reasoning and spec extraction.")

        models = client.get_models()
        if not models:
            models = [
                {"model_tag": "qwen3:4b", "display_name": "Qwen 3 4B (Recommended)", "ram_usage": "2.5GB", "context_length": "262K", "is_available": True, "is_default": True},
                {"model_tag": "qwen2.5:3b", "display_name": "Qwen 2.5 3B", "ram_usage": "1.9GB", "context_length": "128K", "is_available": True},
                {"model_tag": "phi3.5:3.8b", "display_name": "Phi-3.5 Mini 3.8B", "ram_usage": "2.2GB", "context_length": "128K", "is_available": True},
                {"model_tag": "gemma3:4b", "display_name": "Gemma 3 4B", "ram_usage": "2.5GB", "context_length": "8K", "is_available": True},
                {"model_tag": "llama3.2:3b", "display_name": "Llama 3.2 3B", "ram_usage": "2.0GB", "context_length": "128K", "is_available": True},
            ]

        model_map: dict[str, dict[str, Any]] = {
            str(m.get("model_tag") or m.get("tag", "")): m for m in models if isinstance(m, dict)
        }
        model_tags = list(model_map.keys())

        # Determine current active default model (load persisted preference if not yet in session)
        if "default_model" not in st.session_state or not st.session_state["default_model"]:
            persisted_pref = client.get_model_preference()
            st.session_state["default_model"] = persisted_pref or "qwen3:4b"

        current_default = st.session_state.get("default_model", "qwen3:4b")
        default_idx = model_tags.index(current_default) if current_default in model_tags else 0

        selected_tag = st.selectbox(
            "Default Inference Model",
            options=model_tags,
            format_func=lambda tag: f"{model_map[tag].get('display_name', tag)} ({tag}) — RAM: {model_map[tag].get('ram_usage', '~4GB')}, Context: {model_map[tag].get('context_length', '32K')}",
            index=default_idx,
            key="settings_model_selectbox",
            help="This model is automatically used by the Dashboard when initiating tender compliance evaluations.",
        )

        col_save, _ = st.columns([1.5, 3])
        with col_save:
            if st.button("Save Default Model Preference", type="primary", use_container_width=True):
                st.session_state["default_model"] = selected_tag
                success = client.set_model_preference(selected_tag)
                if success:
                    st.toast(f"Default model preference permanently saved as {selected_tag}.")
                    st.success(f"Default model preference permanently saved as `{selected_tag}`.")
                else:
                    st.toast(f"Default model set to {selected_tag}.")
                    st.success(f"Default model preference set to `{selected_tag}`.")


    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

    # 2. Supported Local Models Catalog
    with st.container(border=True):
        st.markdown(
            '<div style="font-size: 16px; font-weight: 700; color: #0f172a; margin-bottom: 12px;">'
            "Supported Local LLM Models Catalog"
            "</div>",
            unsafe_allow_html=True,
        )

        grid_col1, grid_col2 = st.columns(2, gap="medium")
        for idx, m in enumerate(models):
            target_col = grid_col1 if idx % 2 == 0 else grid_col2
            with target_col:
                tag = str(m.get("model_tag") or m.get("tag", ""))
                name = str(m.get("display_name") or m.get("name", tag))
                ram = str(m.get("ram_usage") or f"~{m.get('ram_required_gb', 4)}GB")
                ctx = str(m.get("context_length") or m.get("context_window", "32K"))
                is_avail = bool(m.get("is_available", True))
                avail_status = "Available (Ollama Ready)" if is_avail else "Download Required"
                status_color = "#059669" if is_avail else "#d97706"

                st.markdown(
                    f"""
                    <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:14px; margin-bottom:12px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div style="font-weight:700; font-size:14px; color:#0f172a;">{name}</div>
                            <span style="font-size:11px; font-weight:600; color:{status_color}; background:#ffffff; padding:2px 8px; border-radius:4px; border:1px solid #e2e8f0;">{avail_status}</span>
                        </div>
                        <div style="font-size:12px; color:#64748b; margin-top:4px;">Tag: <code>{tag}</code></div>
                        <div style="font-size:12px; color:#475569; margin-top:6px;">
                            RAM Required: <strong>{ram}</strong> &nbsp;|&nbsp; Context Window: <strong>{ctx} tokens</strong>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

    # 3. System Health & Infrastructure Diagnostics
    with st.container(border=True):
        st.markdown(
            '<div style="font-size: 16px; font-weight: 700; color: #0f172a; margin-bottom: 12px;">'
            "System Diagnostics & Service Health"
            "</div>",
            unsafe_allow_html=True,
        )

        health = client.check_health()
        status_val = health.get("status", "unknown")

        h1, h2, h3 = st.columns(3)
        with h1:
            st.markdown(render_metric_card("Backend API", status_val.upper(), "FastAPI REST Server", status="success" if status_val == "healthy" else "danger"), unsafe_allow_html=True)
        with h2:
            db_status = health.get("database", "connected" if status_val == "healthy" else "unknown")
            st.markdown(render_metric_card("PostgreSQL DB", str(db_status).upper(), "Async Connection Pool", status="success" if db_status == "connected" else "warning"), unsafe_allow_html=True)
        with h3:
            ollama_status = health.get("ollama", "online" if status_val == "healthy" else "degraded")
            st.markdown(render_metric_card("Ollama Engine", str(ollama_status).upper(), "Local Model Server", status="success" if ollama_status == "online" else "warning"), unsafe_allow_html=True)

        st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)
        with st.expander("Raw Health Diagnostic Response"):
            st.json(health)
