# TenderFlow — Frontend UI Requirements

> **Purpose:** This document describes every screen, component, interaction, and data shape needed to build the TenderFlow frontend. The AI builder has NO access to the backend — use the mock data provided for every screen.

---

## App Overview

**TenderFlow** is a web app that automates RFP/tender compliance evaluation. Users upload a PDF technical datasheet and an Excel compliance template. AI evaluates each requirement in the Excel against the PDF specs and populates the Excel with compliance results.

**Color Scheme:** Dark navy sidebar (#1a1a2e), white content area, blue accents (#4a90d9), green for compliant, red for non-compliant, amber for ambiguous, gray for not-found.

---

## Authentication Screens

### 1. Login Page

Full-screen centered card on a subtle gradient background.

**Fields:**
- Email or Username (text input, required)
- Password (password input, required)
- Remember Me (checkbox, default unchecked)

**Buttons:**
- "Sign In" (primary, full-width)
- "Create Account" (text link below form)

**Mock Data:**
```
Email: admin@tender.local
Password: admin123
```

### 2. Registration Page

Same layout as login.

**Fields:**
- Username (text input, required)
- Email (email input, required)
- Password (password input, required)
- Confirm Password (password input, required)

**Notes:**
- First registered user automatically becomes admin
- Passwords must match
- Show validation errors inline

---

## Main Layout

**Sidebar (fixed, left side, ~240px wide):**
- App logo/brand: "TenderFlow" with a small icon
- Navigation items (icons + labels):
  - Dashboard (grid icon)
  - History (clock icon)
  - Settings (gear icon)
- Divider
- Sign Out button at bottom

**Top area:** Page title + optional breadcrumbs

**Content area:** Fills remaining space, scrollable

---

## Screen 1: Dashboard (Workspace)

The main screen. A 4-stage linear pipeline shown as a horizontal stepper/progress indicator at the top.

### Stage Stepper
Shows 4 stages with connecting lines:
1. **Upload** (checkmark when done)
2. **Processing** (spinner when active, checkmark when done)
3. **Review** (checkmark when done)
4. **Export** (checkmark when done)

Current stage is highlighted in blue. Completed stages show green checkmarks. Future stages are grayed out.

---

### Stage 1: Upload & Configure

**Layout:** Two-column or stacked cards

**Left Card — PDF Document:**
- Drag-and-drop zone with dashed border
- Icon: document/upload icon
- Text: "Drop your PDF datasheet here or click to browse"
- Subtext: "Technical specification document (max 100MB)"
- Accepted: .pdf only
- After upload: show filename, file size, page count

**Right Card — Excel Workbook:**
- Same drag-and-drop zone
- Text: "Drop your Excel compliance template here or click to browse"
- Subtext: "RFP compliance workbook (max 100MB)"
- Accepted: .xlsx, .xls
- After upload: show filename, file size, sheet count

**Below cards — Model Selection:**
- Label: "AI Inference Model"
- Dropdown with options:
  - Qwen 3 8B (recommended) — 5.2 GB RAM, 32K context
  - Qwen 3 4B — 2.8 GB RAM, 32K context
  - Qwen 2.5 3B — 2.1 GB RAM, 32K context
  - Phi-3.5 Mini — 2.2 GB RAM, 128K context
  - Gemma 3 4B — 3.3 GB RAM, 128K context
  - Llama 3.2 3B — 2.0 GB RAM, 128K context
- Each option shows: model name, RAM requirement, context window

**Action Button:**
- "Start Compliance Analysis" (large, primary, full-width or centered)
- Disabled until both files are uploaded
- Shows loading spinner during initial validation

**Mock uploaded state:**
```
PDF: "Dell_PowerEdge_R760_Specs.pdf" — 2.4 MB — 48 pages
Excel: "RFP_Compliance_Template.xlsx" — 156 KB — 6 sheets
Model: Qwen 3 8B
```

---

### Stage 2: Processing Monitor

Shown while the pipeline is running.

**Top — Progress Bar:**
- Full-width progress bar with percentage label
- Animated/pulsing while active

**4 Metric Cards (horizontal row):**
| Card | Label | Mock Value |
|------|-------|------------|
| 1 | Run ID | RUN-20260830-001 |
| 2 | PDF Document | Dell_PowerEdge_R760_Specs.pdf |
| 3 | Excel Template | RFP_Compliance_Template.xlsx |
| 4 | AI Model | Qwen 3 8B |

**Active Task:**
- Bold text showing current step, e.g. "Evaluating requirement 23 of 156..."
- Subtext: brief description of what the AI is doing

**Pipeline Step Logs (expandable section):**
- Collapsible "Live Pipeline Step Logs" accordion
- Inside: timestamped log entries, newest first
- Each entry: timestamp + step name + status (running/done/error)

**Mock log entries:**
```
[14:32:01] Analyzing Excel workbook structure... ✓
[14:32:04] Detected 6 sheets, 156 requirements ✓
[14:32:05] Extracting facts from PDF (48 pages)... ✓
[14:32:12] Extracted 89 technical specifications ✓
[14:32:13] Evaluating requirements with AI... (running)
```

**Action:**
- "Cancel Run" button (red outline) — only visible during processing
- Confirmation dialog before cancelling

**Auto-refresh:** Page refreshes every 2 seconds during processing (simulate with polling).

---

### Stage 3: Review & Approvals

Shown after processing completes.

**Top — KPI Summary Cards (6 cards in a row):**

| Metric | Mock Value | Color |
|--------|-----------|-------|
| Total Requirements | 156 | Blue |
| Compliant | 98 | Green |
| Non-Compliant | 31 | Red |
| Ambiguous | 12 | Amber/Orange |
| Not Found | 8 | Gray |
| Needs Review | 7 | Purple |

**Bulk Actions Bar:**
- "Approve High-Confidence (≥90%)" button
- "Approve All Compliant" button
- Filter segmented control/tabs:
  - All (156)
  - Needs Review (7)
  - Compliant (98)
  - Non-Compliant (31)
  - Ambiguous (12)
  - Not Found (8)

**Requirement Cards (scrollable list):**

Each requirement is an expandable card:

**Collapsed state:**
- Row number + requirement text (truncated)
- Status pill (color-coded badge): Compliant / Non-Compliant / Ambiguous / Not Found / Needs Review
- Confidence badge: High (green) / Medium (amber) / Low (red)
- Chevron to expand

**Expanded state:**
- **Requirement:** Full requirement text
- **Status:** Colored badge + text
- **Confidence:** Badge with percentage, e.g. "92% — High"
- **Resolving Layer:** Which of the 5 compliance layers determined the result
  - Exact Match / Rule-Based / Unit Conversion / Semantic Match / LLM Reasoning
- **Matched Specification:** The value from the PDF that satisfies (or fails) the requirement
- **AI Reasoning:** Paragraph explaining the determination
- **Source Evidence:** Citation list, e.g. "Page 12, Table 3 — Row 4" with confidence
- **Review Actions:**
  - "Approve" button (green)
  - "Mark Non-Compliant" button (red)
  - "Override Status" dropdown (pick any status)
  - "Edit Value" — inline text edit for the matched spec
  - "Save Override" button

**Mock requirement card:**
```
#42 — "Server must support minimum 64GB DDR5 ECC RAM"

Status: Compliant ✓
Confidence: 95% — High
Resolving Layer: Unit Conversion
Matched Specification: "Up to 2TB DDR5 RDIMM, 8x DIMM slots"
AI Reasoning: "The Dell PowerEdge R760 supports up to 2TB DDR5 
RDIMM memory across 8 DIMM slots. The requirement of 64GB minimum 
is satisfied as 64GB configurations are available. The unit 
conversion layer normalized '64GB DDR5 ECC RAM' against the 
specification's 'DDR5 RDIMM' memory type."
Source Evidence:
  — Page 14, Section "Memory" — Technical Specifications Table
  — Page 23, Table 5 — Memory Configuration Options
```

---

### Stage 4: Export & Finalize

**Compliance Summary Card:**
- Large percentage display: "Overall Compliance: 63%"
- Horizontal stacked bar showing: Compliant (green) / Non-Compliant (red) / Other (gray)
- Breakdown table:
  | Status | Count | Percentage |
  |--------|-------|------------|
  | Compliant | 98 | 62.8% |
  | Non-Compliant | 31 | 19.9% |
  | Ambiguous | 12 | 7.7% |
  | Not Found | 8 | 5.1% |
  | Needs Review | 7 | 4.5% |

**Download Section:**
- "Download Populated Excel" button (large, primary)
- Shows filename: `RFP_Compliance_Template_populated_20260830_143521.xlsx`

**Navigation:**
- "Return to Review" button (secondary)
- "Start New Evaluation" button (secondary) — resets to Stage 1

---

## Screen 2: History

**Search & Filter Bar:**
- Search input: "Search by filename, run ID, or model..."
- Status filter segmented control:
  - All
  - Completed
  - Processing
  - Cancelled
  - Failed

**Run Cards (scrollable list):**

Each card shows:
- Run ID (e.g. RUN-20260830-001)
- Status badge: Completed (green) / Processing (blue, animated) / Cancelled (gray) / Failed (red)
- Timestamp: "Aug 30, 2026 — 2:32 PM"
- Files: PDF icon + "Dell_PowerEdge_R760_Specs.pdf" → Excel icon + "RFP_Compliance_Template.xlsx"
- Model: "Qwen 3 8B"
- Stats row: ✓ 98 Compliant | ✗ 31 Non-Compliant | ? 12 Ambiguous | — 8 Not Found

**Actions per card:**
- "Open in Workspace" button — loads that run into the Dashboard
- "Download Excel" button — downloads the populated file
- "Re-evaluate" button — starts a new run with same files

**Mock runs:**
```
RUN-20260830-001 — Completed — Aug 30, 2026 2:35 PM
  Dell_PowerEdge_R760_Specs.pdf → RFP_Compliance_Template.xlsx
  Model: Qwen 3 8B
  ✓ 98 | ✗ 31 | ? 12 | — 7

RUN-20260829-003 — Completed — Aug 29, 2026 11:15 AM
  HP_ProLiant_DL380_Gen11_Specs.pdf → Vendor_Comparison_Matrix.xlsx
  Model: Qwen 3 4B
  ✓ 142 | ✗ 8 | ? 3 | — 3

RUN-20260828-001 — Failed — Aug 28, 2026 4:20 PM
  Corrupted_File.pdf → Template.xlsx
  Model: Phi-3.5 Mini
  Error: "PDF extraction failed — file appears corrupted"
```

---

## Screen 3: Settings

**Layout:** Single column with cards

### Card 1: Default AI Model
- Label: "Default Inference Model"
- Dropdown (same 6 models as Dashboard)
- "Save Preference" button
- Success toast on save

### Card 2: Supported Models Catalog
- Table/list of all 6 models with columns:
  | Model | Parameters | RAM Required | Context Window | Status |
  |-------|-----------|-------------|----------------|--------|
  | Qwen 3 8B | 8B | 5.2 GB | 32K tokens | ✓ Available |
  | Qwen 3 4B | 4B | 2.8 GB | 32K tokens | ✓ Available |
  | Qwen 2.5 3B | 3B | 2.1 GB | 32K tokens | ✓ Available |
  | Phi-3.5 Mini | 3.8B | 2.2 GB | 128K tokens | ✓ Available |
  | Gemma 3 4B | 4B | 3.3 GB | 128K tokens | ✓ Available |
  | Llama 3.2 3B | 3B | 2.0 GB | 128K tokens | ✓ Available |

### Card 3: System Diagnostics
- 3 status indicators with colored dots:
  - Backend API: ✓ Connected (green)
  - PostgreSQL Database: ✓ Connected (green)
  - Ollama Engine: ✓ Connected (green)
- Each shows latency, e.g. "12ms response time"
- "Refresh Diagnostics" button
- Expandable "Raw Health Data" section with JSON

---

## Data Shapes (for mock data)

Use these TypeScript-style interfaces to structure your mock data:

```typescript
// User
interface User {
  id: string;
  username: string;
  email: string;
  is_admin: boolean;
  is_active: boolean;
}

// Processing Run
interface ProcessingRun {
  id: string;
  run_id: string; // e.g. "RUN-20260830-001"
  status: "pending" | "processing" | "completed" | "cancelled" | "failed";
  progress: number; // 0-100
  current_step: string;
  model_used: string;
  pdf_filename: string;
  excel_filename: string;
  total_requirements: number;
  compliant_count: number;
  non_compliant_count: number;
  ambiguous_count: number;
  not_found_count: number;
  needs_review_count: number;
  started_at: string; // ISO datetime
  completed_at: string | null;
  error_message: string | null;
}

// Requirement Result
interface RequirementResult {
  id: string;
  requirement_index: number;
  requirement_text: string;
  section: string;
  row_number: number;
  status: "compliant" | "non_compliant" | "partially_compliant" | "ambiguous" | "not_found" | "needs_review";
  confidence: number; // 0-1
  resolving_layer: "exact_match" | "rule_based" | "unit_conversion" | "semantic_match" | "llm_reasoning";
  matched_specification: string;
  ai_reasoning: string;
  reviewed_by: string | null;
  is_overridden: boolean;
}

// Evidence
interface Evidence {
  id: string;
  source_page: number;
  source_table_id: string | null;
  value: string;
  confidence: number;
  extraction_method: string;
  citation: string; // e.g. "Page 12, Table 3"
}

// LLM Model
interface LLMModel {
  id: string;
  name: string;
  parameters: string;
  ram_required: string;
  context_window: string;
  is_available: boolean;
}

// Health Status
interface HealthStatus {
  backend: { status: string; latency_ms: number };
  database: { status: string; latency_ms: number };
  ollama: { status: string; latency_ms: number };
}
```

---

## Global UI Patterns

### Loading States
- Skeleton placeholders for cards while data loads
- Spinner overlays for actions (upload, process, download)
- Progress bar with percentage for long operations

### Empty States
- **No runs yet:** Illustration + "Start your first compliance analysis" + CTA button
- **No results for filter:** "No requirements match this filter" + clear filter link

### Error States
- Toast notifications (top-right, auto-dismiss 5s): success (green), error (red), warning (amber), info (blue)
- Inline validation errors below form fields
- Full-page error boundary with "Retry" button

### Responsive
- Sidebar collapses to icons on tablets
- Cards stack vertically on mobile
- Minimum supported width: 768px

### Accessibility
- All interactive elements keyboard-navigable
- Color is never the only indicator (always paired with icons or text)
- Proper ARIA labels on form inputs

---

## Tech Notes for the AI Builder

1. **All data is mock** — no API calls needed. Use local state or JSON files.
2. **React + TypeScript** recommended, but any modern framework works.
3. **Tailwind CSS** or similar utility-first CSS for styling.
4. **Component library:** shadcn/ui, Radix, or Ant Design are good fits.
5. **Icons:** Lucide, Heroicons, or Ant Design icons.
6. **State management:** React useState/useReducer is sufficient. No Redux needed.
7. **Routing:** React Router or Next.js file-based routing.
8. **The stepper/wizard pattern** is critical — it guides the user through the 4 stages.
9. **The review screen** is the most complex — make sure expandable cards work well.
10. **File upload zones** should support drag-and-drop + click-to-browse.
