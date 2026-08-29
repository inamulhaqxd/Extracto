---
title: TenderFlow UI System, Stage Gating, and Streamlit HTML Rendering Patterns
date: 2026-08-29
work_type: refactor
tags: [streamlit, ui-theming, pipeline-gating, sac-components, docker-cache]
confidence: high
references:
  - ai_rfp_excel/frontend/components.py
  - ai_rfp_excel/frontend/views/workspace.py
  - ai_rfp_excel/frontend/views/settings.py
  - ai_rfp_excel/frontend/streamlit_app.py
  - .streamlit/config.toml
---

## Summary

This session completed a comprehensive UI/UX overhaul of the TenderFlow RFP evaluation application:
1. Rebranded the interface to **TenderFlow** with a minimalist, high-contrast monochrome design system without hardcoded colors.
2. Eliminated default Streamlit top whitespace and streamlined the sidebar to navigation and authentication controls.
3. Decoupled AI model selection from the Stage 1 Upload screen into a persistent Settings preference.
4. Enforced strict stage-gating on the pipeline progress indicator (`sac.steps`), preventing users from clicking into uncompleted future stages.
5. Resolved a critical Streamlit markdown bug where indented HTML strings were parsed as raw `<pre><code>` blocks by switching to `st.html()`.

---

## Reusable Insights

### 1. Streamlit Pure HTML vs Markdown Code Block Pitfall
- **Problem**: When using `st.markdown(html_str, unsafe_allow_html=True)`, if the multi-line string has 4 or more leading spaces of indentation (common with Python multi-line f-strings inside functions), the CommonMark parser treats the lines as an indented markdown code block (`<pre><code>`), outputting escaped HTML tags as literal text.
- **Pattern**: In Streamlit 1.30+, use `st.html(html_str)` for raw HTML containers instead of `st.markdown`.
- **Alternative**: If `st.markdown` must be used, always pass `textwrap.dedent(html_str).strip()` and verify zero leading whitespace on HTML tags.

```python
# PREFERRED in Streamlit 1.30+:
st.html(f'<div class="header"><h2>{html.escape(title)}</h2></div>')

# AVOID (Prone to markdown code-block parsing when indented):
st.markdown("""
        <div>
            <h2>Title</h2>
        </div>
    """, unsafe_allow_html=True)
```

---

### 2. Strict Pipeline Stage Gating with `sac.steps`
- **Pattern**: When using interactive step components like `streamlit_antd_components.steps`, users can click ahead to uncompleted steps unless state boundaries are enforced.
- **Solution**: Derive `max_accessible_stage` dynamically from the current pipeline `run_data` status:
  - No active run -> `max_accessible_stage = 0` (Upload only)
  - `status in ("processing", "pending", "queued")` -> `max_accessible_stage = 1`
  - `status == "review_required"` -> `max_accessible_stage = 2`
  - `status == "completed"` -> `max_accessible_stage = 3`
- If `chosen_step > max_accessible_stage`, reject navigation, display a toast notification, and remain on the active stage.

```python
if chosen_step is not None and isinstance(chosen_step, int) and chosen_step != st.session_state["workspace_stage"]:
    if chosen_step <= max_accessible_stage:
        st.session_state["workspace_stage"] = chosen_step
        st.rerun()
    else:
        st.toast("This stage is locked until previous pipeline steps complete.")
        st.rerun()
```

---

### 3. CSS Variable Design System Tokens in Streamlit
- Centralize all design tokens (`--theme-bg`, `--theme-surface`, `--theme-border`, `--theme-text-*`, `--theme-radius-*`) inside `:root` in `inject_custom_css()` in `components.py`.
- Mirror root colors in `.streamlit/config.toml` under `[theme]` to ensure base Streamlit controls automatically inherit primary and background colors.
- Target Streamlit component classes directly via CSS variables (e.g. `div[data-testid="stTextInput"]`, `div[data-testid="stButton"]`, `.ant-steps-item-process`).

---

### 4. Decoupling Global Preferences from Core Workflow
- Operational dashboards (Stage 1: Upload) should stay streamlined and focused on primary input artifacts (datasheet PDF + workbook template).
- Persistent configurations (e.g. default Ollama local inference model) belong in `Settings`, backed by session state (`st.session_state["default_model"]`) and backend sync endpoints (`client.set_model_preference()`).

---

### 5. Docker BuildKit Pip Cache Mounts
- To prevent slow package redownloads when rebuilds are triggered:
  ```dockerfile
  RUN --mount=type=cache,target=/root/.cache/pip \
      pip install --no-cache-dir -r requirements.txt
  ```
- With volume mounts (`.:/app`) and `watchfiles` / `uvicorn --reload`, container code updates sync in <0.1s without rebuilding containers.

---

## Verification Strategy
Always execute after modifying frontend components or views:
```bash
python -m ruff check ai_rfp_excel/app ai_rfp_excel/frontend --ignore E501
python -m mypy ai_rfp_excel/app ai_rfp_excel/frontend --ignore-missing-imports --explicit-package-bases
python -m pytest ai_rfp_excel/tests/test_streamlit_ui.py
```
