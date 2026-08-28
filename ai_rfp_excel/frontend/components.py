from typing import Any


def render_health_indicator(health_data: dict[str, Any]) -> None:
    """Render backend and Ollama health indicator in the sidebar."""
    import streamlit as st

    status = health_data.get("status", "unknown")

    if status == "healthy":
        st.sidebar.markdown(
            '<div style="display:flex; align-items:center; gap:8px; margin-bottom:12px;">'
            '<span style="height:10px; width:10px; background-color:#28a745; border-radius:50%; display:inline-block;"></span>'
            '<span style="font-size:12px; font-weight:600; color:#28a745;">System Online & Healthy</span>'
            "</div>",
            unsafe_allow_html=True,
        )
    elif status == "degraded":
        st.sidebar.markdown(
            '<div style="display:flex; align-items:center; gap:8px; margin-bottom:12px;">'
            '<span style="height:10px; width:10px; background-color:#ffc107; border-radius:50%; display:inline-block;"></span>'
            '<span style="font-size:12px; font-weight:600; color:#ffc107;">System Degraded (Check Ollama)</span>'
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.markdown(
            '<div style="display:flex; align-items:center; gap:8px; margin-bottom:12px;">'
            '<span style="height:10px; width:10px; background-color:#dc3545; border-radius:50%; display:inline-block;"></span>'
            '<span style="font-size:12px; font-weight:600; color:#dc3545;">Backend Disconnected</span>'
            "</div>",
            unsafe_allow_html=True,
        )


def render_status_pill(status: str) -> str:
    """Return HTML string for styled status badges."""
    s_upper = status.upper()
    if "COMPLIANT" in s_upper and "NON" not in s_upper and "PARTIAL" not in s_upper:
        bg = "#e2f0d9"
        color = "#276a3c"
        label = "COMPLIANT"
    elif "NON_COMPLIANT" in s_upper:
        bg = "#fce4d6"
        color = "#c00000"
        label = "NON-COMPLIANT"
    elif "PARTIAL" in s_upper or "AMBIGUOUS" in s_upper:
        bg = "#fff2cc"
        color = "#b25900"
        label = "AMBIGUOUS" if "AMBIGUOUS" in s_upper else "PARTIAL"
    else:
        bg = "#f2f2f2"
        color = "#595959"
        label = "NOT FOUND"

    return f'<span style="background-color:{bg}; color:{color}; padding:3px 8px; border-radius:12px; font-size:11px; font-weight:700;">{label}</span>'


def render_confidence_badge(confidence: float) -> str:
    """Return HTML string for confidence score badge."""
    pct = int(confidence * 100)
    if confidence >= 0.90:
        color = "#28a745"
        label = f"{pct}% High"
    elif confidence >= 0.70:
        color = "#fd7e14"
        label = f"{pct}% Medium"
    else:
        color = "#dc3545"
        label = f"{pct}% Low (Review)"

    return f'<span style="color:{color}; font-weight:700; font-size:12px;">{label}</span>'


def render_error_card(title: str, message: str, suggestion: str | None = None) -> None:
    """Render a clean, plain language error card."""
    import streamlit as st

    sugg_html = f'<p style="margin:4px 0 0 0; font-size:12px; color:#6c757d;"><strong>Suggestion:</strong> {suggestion}</p>' if suggestion else ""
    st.markdown(
        f'<div style="background-color:#f8d7da; border-left:4px solid #dc3545; padding:12px 16px; border-radius:4px; margin-bottom:16px;">'
        f'<h4 style="margin:0 0 4px 0; color:#721c24; font-size:14px;">⚠️ {title}</h4>'
        f'<p style="margin:0; font-size:13px; color:#495057;">{message}</p>'
        f"{sugg_html}"
        f"</div>",
        unsafe_allow_html=True,
    )

