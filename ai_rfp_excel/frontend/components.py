import html
from typing import Any

import streamlit as st


def inject_custom_css() -> None:
    """Inject modern minimalist TenderFlow CSS design system tokens into Streamlit."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

        :root {
            /* Base Theme Colors */
            --theme-bg: #ffffff;
            --theme-surface: #ffffff;
            --theme-surface-subtle: #f9fafb;
            --theme-border: #e5e7eb;
            --theme-border-subtle: #f3f4f6;
            --theme-border-strong: #111827;

            /* Typography Colors */
            --theme-text-primary: #111827;
            --theme-text-secondary: #4b5563;
            --theme-text-muted: #9ca3af;
            --theme-text-subtle: #6b7280;

            /* Action & Button Tokens */
            --theme-button-bg: #111827;
            --theme-button-text: #ffffff;
            --theme-button-hover: #000000;
            --theme-button-secondary-bg: #f9fafb;
            --theme-button-secondary-border: #e5e7eb;
            --theme-button-secondary-text: #111827;

            /* Radius Tokens */
            --theme-radius-none: 0px;
            --theme-radius-sm: 4px;
            --theme-radius-md: 6px;
            --theme-radius-lg: 8px;
            --theme-radius-xl: 12px;
            --theme-radius-pill: 9999px;

            /* Shadows */
            --theme-shadow-subtle: 0 1px 2px 0 rgba(0, 0, 0, 0.04);
            --theme-shadow-card: 0 1px 3px 0 rgba(0, 0, 0, 0.06), 0 1px 2px -1px rgba(0, 0, 0, 0.04);
            --theme-shadow-hover: 0 4px 6px -1px rgba(0, 0, 0, 0.08), 0 2px 4px -2px rgba(0, 0, 0, 0.04);
            --theme-shadow-dialog: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.05);

            /* Semantic Status Tokens */
            --status-success-bg: #ecfdf5;
            --status-success-border: #a7f3d0;
            --status-success-text: #047857;
            --status-warning-bg: #fffbeb;
            --status-warning-border: #fde68a;
            --status-warning-text: #b45309;
            --status-danger-bg: #fef2f2;
            --status-danger-border: #fecaca;
            --status-danger-text: #b91c1c;
            --status-neutral-bg: #f3f4f6;
            --status-neutral-border: #e5e7eb;
            --status-neutral-text: #4b5563;
        }

        html, body, [class*="css"], .stApp {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: var(--theme-bg);
            color: var(--theme-text-primary);
        }

        /* Eliminate excessive top whitespace above dashboard */
        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 2rem !important;
            padding-left: 2.5rem !important;
            padding-right: 2.5rem !important;
            max-width: 100% !important;
        }
        header[data-testid="stHeader"] {
            background: transparent !important;
            height: 1.5rem !important;
        }

        /* Top-Left TenderFlow Brand Mark */
        .tenderflow-brand-header {
            position: absolute;
            top: 24px;
            left: 32px;
            display: flex;
            align-items: center;
            gap: 8px;
            z-index: 100;
        }
        .tenderflow-brand-bar {
            width: 5px;
            height: 18px;
            background-color: var(--theme-button-bg);
            border-radius: 1px;
            display: inline-block;
        }
        .tenderflow-brand-text {
            font-size: 14px;
            font-weight: 800;
            letter-spacing: 0.08em;
            color: var(--theme-text-primary);
            text-transform: uppercase;
        }

        /* Minimalist Login Center Container */
        .tenderflow-login-wrapper {
            max-width: 420px;
            margin: 60px auto 40px auto;
            padding: 0 16px;
        }
        .tenderflow-login-title {
            font-size: 32px;
            font-weight: 400;
            letter-spacing: -0.03em;
            color: var(--theme-text-primary);
            margin-bottom: 6px;
            line-height: 1.2;
        }
        .tenderflow-login-subtitle {
            font-size: 14px;
            color: var(--theme-text-subtle);
            margin-bottom: 32px;
            font-weight: 400;
        }
        .tenderflow-field-label {
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--theme-text-secondary);
            margin-bottom: 6px;
            display: block;
        }

        /* Footer Branding */
        .tenderflow-footer {
            text-align: center;
            margin-top: 48px;
            padding: 24px 0;
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.12em;
            color: var(--theme-text-muted);
            text-transform: uppercase;
        }

        /* Buttons & Form controls theming */
        div[data-testid="stForm"] {
            border: none !important;
            padding: 0 !important;
            background: transparent !important;
        }
        div[data-testid="stFormSubmitButton"] > button {
            background-color: var(--theme-button-bg) !important;
            color: var(--theme-button-text) !important;
            border: 1px solid var(--theme-button-bg) !important;
            border-radius: var(--theme-radius-sm) !important;
            font-weight: 700 !important;
            font-size: 13px !important;
            letter-spacing: 0.08em !important;
            text-transform: uppercase !important;
            padding: 12px 24px !important;
            height: 44px !important;
            transition: all 0.15s ease-in-out !important;
            box-shadow: var(--theme-shadow-subtle) !important;
        }
        div[data-testid="stFormSubmitButton"] > button:hover {
            background-color: var(--theme-button-hover) !important;
            border-color: var(--theme-button-hover) !important;
            transform: translateY(-1px);
        }

        /* Clean Input Fields - password toggle removed */
        div[data-testid="stTextInput"] div[data-baseweb="input"] {
            border: 1px solid var(--theme-border) !important;
            border-radius: var(--theme-radius-sm) !important;
            background-color: var(--theme-surface) !important;
            transition: border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out !important;
        }
        div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
            border-color: var(--theme-border-strong) !important;
            box-shadow: 0 0 0 1px var(--theme-border-strong) !important;
        }
        div[data-testid="stTextInput"] input {
            border: none !important;
            background-color: transparent !important;
            color: var(--theme-text-primary) !important;
            font-size: 14px !important;
            padding: 10px 14px !important;
            box-shadow: none !important;
        }
        div[data-testid="stTextInput"] input:focus {
            outline: none !important;
            box-shadow: none !important;
        }
        div[data-testid="stTextInput"] button {
            display: none !important;
        }
        div[data-testid="stTextInput"] label {
            font-size: 11px !important;
            font-weight: 600 !important;
            letter-spacing: 0.08em !important;
            text-transform: uppercase !important;
            color: var(--theme-text-secondary) !important;
            margin-bottom: 6px !important;
        }

        /* Checkbox Theming */
        div[data-testid="stCheckbox"] label span {
            font-size: 13px !important;
            color: var(--theme-text-secondary) !important;
        }

        /* sac.steps Active Step Bold Styling */
        .ant-steps-item-process .ant-steps-item-title,
        .ant-steps-item-process > .ant-steps-item-container > .ant-steps-item-content > .ant-steps-item-title,
        div[class*="ant-steps-item-process"] div[class*="ant-steps-item-title"],
        div[class*="ant-steps-item-process"] span[class*="ant-steps-item-title"] {
            font-weight: 800 !important;
            color: var(--theme-text-primary) !important;
            letter-spacing: -0.01em !important;
        }
        .ant-steps-item-process .ant-steps-item-description,
        div[class*="ant-steps-item-process"] div[class*="ant-steps-item-description"] {
            font-weight: 600 !important;
            color: var(--theme-text-secondary) !important;
        }
        .ant-steps-item-finish .ant-steps-item-title,
        div[class*="ant-steps-item-finish"] div[class*="ant-steps-item-title"] {
            font-weight: 500 !important;
            color: var(--theme-text-secondary) !important;
        }
        .ant-steps-item-wait .ant-steps-item-title,
        div[class*="ant-steps-item-wait"] div[class*="ant-steps-item-title"] {
            font-weight: 400 !important;
            color: var(--theme-text-muted) !important;
        }


        /* Enterprise card layout */
        .enterprise-card {
            background-color: var(--theme-surface);
            border: 1px solid var(--theme-border);
            border-radius: var(--theme-radius-lg);
            padding: 20px 24px;
            box-shadow: var(--theme-shadow-card);
            margin-bottom: 20px;
            transition: box-shadow 0.2s ease-in-out, border-color 0.2s ease-in-out;
        }
        .enterprise-card:hover {
            box-shadow: var(--theme-shadow-hover);
            border-color: var(--theme-text-muted);
        }

        /* Metric stat card */
        .metric-card {
            background: var(--theme-surface);
            border: 1px solid var(--theme-border);
            border-radius: var(--theme-radius-md);
            padding: 16px 20px;
            box-shadow: var(--theme-shadow-card);
        }
        .metric-label {
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--theme-text-muted);
            margin-bottom: 4px;
        }
        .metric-value {
            font-size: 24px;
            font-weight: 700;
            color: var(--theme-text-primary);
            line-height: 1.2;
        }
        .metric-desc {
            font-size: 12px;
            color: var(--theme-text-muted);
            margin-top: 4px;
        }

        /* Status Pills */
        .status-pill {
            display: inline-flex;
            align-items: center;
            padding: 3px 10px;
            border-radius: var(--theme-radius-pill);
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
        }
        .status-pill-compliant {
            background-color: var(--status-success-bg);
            color: var(--status-success-text);
            border: 1px solid var(--status-success-border);
        }
        .status-pill-non-compliant {
            background-color: var(--status-danger-bg);
            color: var(--status-danger-text);
            border: 1px solid var(--status-danger-border);
        }
        .status-pill-ambiguous {
            background-color: var(--status-warning-bg);
            color: var(--status-warning-text);
            border: 1px solid var(--status-warning-border);
        }
        .status-pill-missing {
            background-color: var(--status-neutral-bg);
            color: var(--status-neutral-text);
            border: 1px solid var(--status-neutral-border);
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
            border-radius: var(--theme-radius-md);
            margin-bottom: 16px;
            border-left: 4px solid;
            font-size: 13px;
        }
        .enterprise-alert-error {
            background-color: var(--status-danger-bg);
            border-left-color: var(--status-danger-text);
            color: var(--theme-text-primary);
        }
        .enterprise-alert-warning {
            background-color: var(--status-warning-bg);
            border-left-color: var(--status-warning-text);
            color: var(--theme-text-primary);
        }
        .enterprise-alert-info {
            background-color: var(--theme-surface-subtle);
            border-left-color: var(--theme-button-bg);
            color: var(--theme-text-primary);
        }
        .enterprise-alert-title {
            font-weight: 700;
            font-size: 13px;
            margin-bottom: 4px;
        }

        /* User Profile in Sidebar */
        .sidebar-profile-card {
            background: var(--theme-surface-subtle);
            border: 1px solid var(--theme-border);
            border-radius: var(--theme-radius-md);
            padding: 12px;
            margin-top: 16px;
            margin-bottom: 12px;
        }
        .sidebar-username {
            font-weight: 600;
            font-size: 13px;
            color: var(--theme-text-primary);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(title: str, subtitle: str | None = None, tag_text: str | None = None) -> None:
    """Render a clean, high-contrast enterprise header without emojis."""
    tag_html = (
        f'<span style="background-color:var(--theme-surface-subtle); color:var(--theme-text-primary); border:1px solid var(--theme-border); font-size:11px; font-weight:700; padding:2px 8px; border-radius:var(--theme-radius-sm); margin-left:8px; vertical-align:middle; text-transform:uppercase;">{html.escape(tag_text)}</span>'
        if tag_text
        else ""
    )
    sub_html = (
        f'<div style="margin:4px 0 0 0; font-size:14px; color:var(--theme-text-secondary); font-weight:400;">{html.escape(subtitle)}</div>'
        if subtitle
        else ""
    )

    header_html = (
        f'<div style="margin-top:0; margin-bottom:20px; padding-bottom:14px; border-bottom:1px solid var(--theme-border);">'
        f'<h2 style="margin:0; font-size:22px; font-weight:700; color:var(--theme-text-primary); display:inline-block;">{html.escape(title)}</h2>'
        f'{tag_html}'
        f'{sub_html}'
        f'</div>'
    )

    st.html(header_html)


def render_card(title: str, content_html: str | None = None, subtitle: str | None = None) -> None:
    """Render an elevated enterprise content card."""
    sub_html = (
        f'<p style="margin:2px 0 12px 0; font-size:13px; color:#64748b;">{html.escape(subtitle)}</p>'
        if subtitle
        else ""
    )
    body_html = content_html or ""
    card_html = (
        f'<div class="enterprise-card">'
        f'<div style="font-size:16px; font-weight:700; color:#0f172a;">{html.escape(title)}</div>'
        f'{sub_html}'
        f'<div>{body_html}</div>'
        f'</div>'
    )
    st.html(card_html)




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
