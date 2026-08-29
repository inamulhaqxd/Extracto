import html
from typing import Any

import streamlit as st


def inject_custom_css() -> None:
    """Inject modern enterprise slate CSS design system tokens into Streamlit."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        :root {
            --primary-600: #4f46e5;
            --primary-700: #4338ca;
            --slate-50: #f8fafc;
            --slate-100: #f1f5f9;
            --slate-200: #e2e8f0;
            --slate-300: #cbd5e1;
            --slate-400: #94a3b8;
            --slate-500: #64748b;
            --slate-600: #475569;
            --slate-700: #334155;
            --slate-800: #1e293b;
            --slate-900: #0f172a;
            --success-50: #ecfdf5;
            --success-600: #059669;
            --success-700: #047857;
            --warning-50: #fffbeb;
            --warning-600: #d97706;
            --warning-700: #b45309;
            --danger-50: #fef2f2;
            --danger-600: #dc2626;
            --danger-700: #b91c1c;
            --card-radius: 10px;
            --card-shadow: 0 1px 3px 0 rgba(15, 23, 42, 0.08), 0 1px 2px -1px rgba(15, 23, 42, 0.08);
            --card-shadow-hover: 0 4px 6px -1px rgba(15, 23, 42, 0.1), 0 2px 4px -2px rgba(15, 23, 42, 0.1);
        }

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }

        /* Enterprise card layout */
        .enterprise-card {
            background-color: #ffffff;
            border: 1px solid var(--slate-200);
            border-radius: var(--card-radius);
            padding: 20px 24px;
            box-shadow: var(--card-shadow);
            margin-bottom: 20px;
            transition: box-shadow 0.2s ease-in-out, border-color 0.2s ease-in-out;
        }
        .enterprise-card:hover {
            box-shadow: var(--card-shadow-hover);
            border-color: var(--slate-300);
        }

        /* Full-screen Login Card */
        .login-wrapper {
            max-width: 960px;
            margin: 40px auto;
            background: #ffffff;
            border: 1px solid var(--slate-200);
            border-radius: 12px;
            box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.08), 0 8px 10px -6px rgba(15, 23, 42, 0.04);
            overflow: hidden;
        }

        /* Metric stat card */
        .metric-card {
            background: #ffffff;
            border: 1px solid var(--slate-200);
            border-radius: 8px;
            padding: 16px 20px;
            box-shadow: var(--card-shadow);
        }
        .metric-label {
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--slate-500);
            margin-bottom: 4px;
        }
        .metric-value {
            font-size: 24px;
            font-weight: 700;
            color: var(--slate-900);
            line-height: 1.2;
        }
        .metric-desc {
            font-size: 12px;
            color: var(--slate-500);
            margin-top: 4px;
        }

        /* Status Pills */
        .status-pill {
            display: inline-flex;
            align-items: center;
            padding: 3px 10px;
            border-radius: 9999px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
        }
        .status-pill-compliant {
            background-color: var(--success-50);
            color: var(--success-700);
            border: 1px solid #a7f3d0;
        }
        .status-pill-non-compliant {
            background-color: var(--danger-50);
            color: var(--danger-700);
            border: 1px solid #fecaca;
        }
        .status-pill-ambiguous {
            background-color: var(--warning-50);
            color: var(--warning-700);
            border: 1px solid #fde68a;
        }
        .status-pill-missing {
            background-color: var(--slate-100);
            color: var(--slate-600);
            border: 1px solid var(--slate-200);
        }

        /* Confidence Badge */
        .confidence-badge {
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.02em;
        }

        /* Custom Alert Cards */
        .enterprise-alert {
            padding: 14px 18px;
            border-radius: 8px;
            margin-bottom: 16px;
            border-left: 4px solid;
            font-size: 13px;
        }
        .enterprise-alert-error {
            background-color: var(--danger-50);
            border-left-color: var(--danger-600);
            color: var(--slate-900);
        }
        .enterprise-alert-warning {
            background-color: var(--warning-50);
            border-left-color: var(--warning-600);
            color: var(--slate-900);
        }
        .enterprise-alert-info {
            background-color: #eff6ff;
            border-left-color: #3b82f6;
            color: var(--slate-900);
        }
        .enterprise-alert-title {
            font-weight: 700;
            font-size: 14px;
            margin-bottom: 4px;
        }

        /* User Profile in Sidebar */
        .sidebar-profile-card {
            background: var(--slate-50);
            border: 1px solid var(--slate-200);
            border-radius: 8px;
            padding: 12px;
            margin-top: 16px;
            margin-bottom: 12px;
        }
        .sidebar-username {
            font-weight: 600;
            font-size: 13px;
            color: var(--slate-900);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(title: str, subtitle: str | None = None, tag_text: str | None = None) -> None:
    """Render a clean, high-contrast enterprise header without emojis."""
    tag_html = (
        f'<span style="background-color:#eef2ff; color:#4f46e5; border:1px solid #c7d2fe; font-size:11px; font-weight:700; padding:2px 8px; border-radius:4px; margin-left:8px; vertical-align:middle; text-transform:uppercase;">{html.escape(tag_text)}</span>'
        if tag_text
        else ""
    )
    sub_html = (
        f'<p style="margin:4px 0 0 0; font-size:14px; color:#64748b; font-weight:400;">{html.escape(subtitle)}</p>'
        if subtitle
        else ""
    )

    st.markdown(
        f"""
        <div style="margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid #e2e8f0;">
            <h2 style="margin:0; font-size:22px; font-weight:700; color:#0f172a; display:inline-block;">
                {html.escape(title)}
            </h2>
            {tag_html}
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_card(title: str, content_html: str | None = None, subtitle: str | None = None) -> None:
    """Render an elevated enterprise content card."""
    sub_html = (
        f'<p style="margin:2px 0 12px 0; font-size:13px; color:#64748b;">{html.escape(subtitle)}</p>'
        if subtitle
        else ""
    )
    body_html = content_html or ""
    st.markdown(
        f"""
        <div class="enterprise-card">
            <div style="font-size:16px; font-weight:700; color:#0f172a;">{html.escape(title)}</div>
            {sub_html}
            <div>{body_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(
    label: str,
    value: str | int | float,
    description: str | None = None,
    status: str | None = None,
) -> str:
    """Return HTML string for enterprise metric card."""
    desc_html = f'<div class="metric-desc">{html.escape(description)}</div>' if description else ""
    status_border = ""
    if status == "success":
        status_border = "border-left: 4px solid #059669;"
    elif status == "danger":
        status_border = "border-left: 4px solid #dc2626;"
    elif status == "warning":
        status_border = "border-left: 4px solid #d97706;"

    return (
        f'<div class="metric-card" style="{status_border}">'
        f'<div class="metric-label">{html.escape(label)}</div>'
        f'<div class="metric-value">{html.escape(str(value))}</div>'
        f"{desc_html}"
        f"</div>"
    )


def render_health_indicator(health_data: dict[str, Any]) -> None:
    """Render clean vector/dot health indicator in the sidebar without emojis."""
    status = health_data.get("status", "unknown")

    if status == "healthy":
        dot_color = "#059669"
        text_color = "#047857"
        label = "System Online"
    elif status == "degraded":
        dot_color = "#d97706"
        text_color = "#b45309"
        label = "System Degraded"
    else:
        dot_color = "#dc2626"
        text_color = "#b91c1c"
        label = "Backend Offline"

    st.sidebar.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:8px; padding:6px 10px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; margin-bottom:12px;">
            <span style="height:8px; width:8px; background-color:{dot_color}; border-radius:50%; display:inline-block;"></span>
            <span style="font-size:12px; font-weight:600; color:{text_color};">{label}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_status_pill(status: str) -> str:
    """Return HTML string for styled enterprise status pills (zero emojis)."""
    s_upper = status.upper()
    if "COMPLIANT" in s_upper and "NON" not in s_upper and "PARTIAL" not in s_upper:
        pill_cls = "status-pill status-pill-compliant"
        label = "COMPLIANT"
    elif "NON_COMPLIANT" in s_upper or "NON-COMPLIANT" in s_upper:
        pill_cls = "status-pill status-pill-non-compliant"
        label = "NON-COMPLIANT"
    elif "PARTIAL" in s_upper or "AMBIGUOUS" in s_upper:
        pill_cls = "status-pill status-pill-ambiguous"
        label = "AMBIGUOUS" if "AMBIGUOUS" in s_upper else "PARTIAL"
    else:
        pill_cls = "status-pill status-pill-missing"
        label = "NOT FOUND"

    return f'<span class="{pill_cls}">{label}</span>'


def render_confidence_badge(confidence: float) -> str:
    """Return HTML string for confidence score badge (zero emojis)."""
    pct = int(confidence * 100)
    if confidence >= 0.90:
        color = "#059669"
        label = f"{pct}% High"
    elif confidence >= 0.70:
        color = "#d97706"
        label = f"{pct}% Medium"
    else:
        color = "#dc2626"
        label = f"{pct}% Low"

    return f'<span class="confidence-badge" style="color:{color};">{label}</span>'


def render_error_card(title: str, message: str, suggestion: str | None = None) -> None:
    """Render a clean, plain language enterprise error card (zero emojis)."""
    sugg_html = (
        f'<div style="margin-top:6px; font-size:12px; color:#475569;">'
        f'<strong>Suggestion:</strong> {html.escape(suggestion)}</div>'
        if suggestion
        else ""
    )

    st.markdown(
        f"""
        <div class="enterprise-alert enterprise-alert-error">
            <div class="enterprise-alert-title" style="color:#b91c1c;">{html.escape(title)}</div>
            <div style="color:#334155; font-size:13px;">{html.escape(message)}</div>
            {sugg_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_info_card(title: str, message: str) -> None:
    """Render an informational enterprise alert card."""
    st.markdown(
        f"""
        <div class="enterprise-alert enterprise-alert-info">
            <div class="enterprise-alert-title" style="color:#1d4ed8;">{html.escape(title)}</div>
            <div style="color:#334155; font-size:13px;">{html.escape(message)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
