---
type: Spec
title: Local AI-Based RFP PDF-to-Excel Automation System
---

## Problem

Technical/RFP/Bill of Material documents need to be analyzed and their specifications matched against Excel workbook templates. This is currently a manual, error-prone, and time-consuming process. The system must be completely local and private — no document data may leave the environment.

## Proposed Outcome

An AI-powered system that:
1. Ingests PDF documents (text, tables, images, scanned pages)
2. Extracts and normalizes technical specifications
3. Analyzes Excel workbook structure dynamically
4. Matches requirements against reference data using hybrid AI + deterministic rules
5. Populates Excel templates with compliance results and evidence
6. Supports human review and manual overrides
7. Runs entirely on local infrastructure with no external API calls

## User Stories

1. As a team member, I want to upload a reference PDF and Excel template simultaneously so I can start processing immediately.
2. As a team member, I want to see real-time processing progress so I know how long to wait.
3. As a team member, I want to review AI-generated compliance results with full evidence before finalizing the Excel.
4. As a team member, I want to approve, reject, or override any AI decision during review.
5. As a team member, I want to bulk-approve high-confidence results to speed up review.
6. As a team member, I want to download the populated Excel file when satisfied with the results.
7. As a team member, I want to see my processing history and find specific runs by name or date.
8. As a team member, I want to re-run processing with a different Excel template using the same PDF extraction.
9. As a team member, I want to cancel a processing job if I uploaded the wrong file.
10. As a team member, I want to see only my own documents and runs.
11. As an admin, I want to manage user accounts (add/remove users).
12. As an admin, I want to view all users' processing runs and system health.
13. As an admin, I want to reset user passwords when requested.
14. As an admin, I want full control over system data and configuration.

## Requirements

### Authentication & Users

1. Users authenticate with name/email and password. [L19]
2. Passwords are stored using bcrypt hashing. [L20]
3. First registered user becomes the admin. [L40]
4. Only admin can create new user accounts. [L57]
5. Admin can reset any user's password. [L58]
6. Each user sees only their own documents and runs. [L21]
7. Admin can see all users' runs and data. [L21]
8. No self-service password reset for MVP. [L58]

### PDF Ingestion

9. System accepts PDF files up to 100MB. [L60]
10. System processes all PDF content types equally from day one: text, tables, images, scanned pages. [L2]
11. PDF pages are rendered at 300 DPI using PyMuPDF for OCR and analysis. [L29]
12. Multiple PDF parsers are orchestrated via a router + strategy pattern. [L14]
13. For mixed pages (text + images), multiple parsers run and results are merged. [L14]
14. OCR uses Tesseract with PaddleOCR fallback for low-quality results. [L37]
15. Images with technical content are processed via OCR + text model post-processing (no vision model). [L38]
16. Page-level provenance is preserved throughout extraction. [L14]
17. Duplicate PDF uploads are detected via hashing and user is warned. [L52]

### Excel Analysis

18. System accepts Excel files up to 50MB. [L60]
19. Excel structure is analyzed deterministically (sheets, headers, merged cells, vendor columns). [L15]
20. Requirements are detected dynamically — no hardcoded cell addresses. [L15]
21. All sheets are processed automatically. [L59]
22. LLM maps canonical fields to Excel locations semantically. [L15]
23. Excel template versioning is hash-based. [L28]

### AI Processing

24. Local LLM is Llama 3.2 3B via Ollama. [L1]
25. No vision model — rely on OCR + text model post-processing for images. [L1]
26. LLM abstraction is a single LocalLLMProvider class wrapping Ollama. [L13]
27. Model configuration (name, base URL, temperature, timeout) is in .env file. [L18]
28. Ollama runs with Parallel=2 and KeepAlive=5m for team use. [L39]
29. Structured JSON output is validated with Pydantic before use. [L31]
30. Invalid LLM output triggers one retry with error context. [L31]
31. If retry fails, operation is marked as failed — never use bad data silently. [L31]
32. AI prompts are stored as Python functions in separate files. [L36]

### Compliance Engine

33. Compliance states: COMPLIANT, PARTIALLY_COMPLIANT, NON_COMPLIANT, NOT_FOUND, AMBIGUOUS. [L17]
34. Compliance is resolved in layers: exact → rules → unit conversion → semantic → LLM. [L17]
35. Lower layers are skipped if higher-confidence result is found. [L17]
36. Every AI decision includes evidence with source reference (page, table, image). [L48]
37. AI must not invent specifications — mark as NOT_FOUND if evidence is absent. [L17]
38. Conflicting evidence is marked as AMBIGUOUS with both sources preserved. [L17]

### Human Review

39. High-confidence results (>=0.90) are auto-approved. [L10]
40. Low-confidence results are flagged for review. [L10]
41. Users can approve, reject, or override any AI decision. [L46]
42. All manual changes are logged with user name and timestamp. [L46]
43. Bulk actions available: approve all high-confidence, approve all compliant, select multiple. [L49]
44. No undo/redo for MVP — changes save immediately. [L47]
45. Evidence display shows requirement, decision, confidence, evidence text, source reference. [L48]
46. Source references show page number and table/image ID — user opens PDF separately. [L51]

### Excel Generation

47. Primary output is populated Excel workbook only. [L50]
48. Original workbook formatting, merged cells, formulas are preserved. [L50]
49. A summary sheet is added with compliance breakdown and confidence distribution. [L45]
50. Generated files are downloaded via Streamlit download button. [L34]
51. File naming pattern: {original_name}_populated_{timestamp}.xlsx. [L34]

### Processing Pipeline

52. Architecture follows pipeline pattern — each phase is an independent module. [L11]
53. ProcessingContext object passes state between pipeline steps. [L12]
54. Partial results are saved after each step for crash recovery. [L9]
55. Users can retry from the failed step without starting over. [L9]
56. Per-step timeouts: LLM 120s, OCR 60s. No overall job timeout. [L23]
57. FIFO job queue — jobs processed in submission order. [L32]
58. Users can cancel running jobs — run marked as CANCELLED. [L53]
59. Batch processing for large PDFs (10 pages at a time). [L60]

### Concurrency & Storage

60. Background tasks + polling for concurrent processing. [L7]
61. Two-zone file storage: uploads (temp) + processed (permanent). [L8]
62. Uploads cleaned after processing completes. [L8]
63. Processed results kept indefinitely. [L42]
64. SQLAlchemy built-in connection pooling (pool_size=5, max_overflow=10). [L24]
65. PostgreSQL backed up daily via Docker volume + cron. [L33]

### User Interface

66. FastAPI backend built first, Streamlit client second. [L3]
67. Streamlit remembers all session state across pages. [L41]
68. Simultaneous PDF + Excel upload widgets. [L30]
69. Progress bar with polling every 2-3 seconds. [L22]
70. Processing status shows current step (Extracting tables... OCR processing...). [L22]
71. Cancel button displayed during processing. [L53]
72. Error display uses plain language error cards — no raw tracebacks. [L44]
73. Health indicator in Streamlit sidebar (green/red). [L35]
74. Search and filter in processing history. [L54]
75. Re-run capability: reuse PDF extraction, swap Excel template. [L55]

### System Configuration

76. Configuration via .env file + Pydantic BaseSettings. [L18]
77. Environment variables override .env values. [L18]
78. Configurable: Ollama URL, model names, DB connection, file paths, thresholds. [L18]

### Logging & Monitoring

79. Structured JSON logs via structlog. [L26]
80. Console output for Docker, file output for audit. [L26]
81. Daily log rotation. [L26]
82. GET /health endpoint checks Ollama + PostgreSQL. [L35]

### Docker Deployment

83. 4 Docker Compose services: FastAPI + Streamlit + PostgreSQL + Ollama. [L25]
84. Shared Docker network for inter-service communication. [L25]
85. Volumes for Ollama models and PostgreSQL data. [L25]
86. Auto-setup on first run: pull model, run migrations, create admin. [L40]

### Testing

87. pytest with fixtures for DB, sample files, mocked LLM. [L16]
88. Test directories per phase: ingestion/, excel/, ai/, matching/, integration/. [L16]

## Technical Decisions

- **Pipeline Architecture**: Each phase (ingestion → normalization → AI extraction → matching → Excel population) is an independent module with defined inputs/outputs. Data flows through a ProcessingContext object. [L11, L12]
- **No Vision Model**: Hardware constraints limit to Llama 3.2 3B text model only. Images are processed via OCR + text model post-processing. [L1, L38]
- **Hybrid Compliance Engine**: Deterministic rules handle exact matches and arithmetic. LLM handles semantic and ambiguous cases. Layered approach minimizes LLM calls. [L17]
- **Dual OCR Strategy**: Tesseract for basic text, PaddleOCR fallback for tables and low-quality scans. [L37]
- **Admin-Only User Management**: No self-registration. Admin creates all accounts. Simplifies access control for small team. [L57]
- **Two-Zone File Storage**: Temporary uploads cleaned after processing. Permanent results kept indefinitely. Docker-mountable paths. [L8, L42]
- **Polling Over WebSocket**: Simpler implementation. Progress stored in DB, Streamlit polls every 2-3 seconds. Sufficient for team use. [L7, L22]
- **FIFO Job Queue**: No priority system. First in, first out. Simple and fair for small team. [L32]

## Testing Strategy

- **Unit tests**: Per-module tests with mocked dependencies (LLM, DB, file system)
- **Integration tests**: End-to-end pipeline tests with sample PDFs and Excel files
- **PDF tests**: Text-only, table-heavy, image-heavy, scanned, mixed, poor-quality
- **Excel tests**: Original, renamed columns, added/removed sheets, merged cells, hidden rows
- **AI tests**: Exact match, semantic match, partial match, contradictory evidence, missing info
- **Mock LLM**: All automated tests mock Ollama HTTP calls — no real model required
- **Fixtures**: Sample PDFs, Excel files, expected outputs stored in tests/fixtures/

## Out of Scope

- Vision model (Llama 3.2 vision) — not feasible with current hardware
- ChromaDB vector search — introduced after MVP-4 if needed
- WebSocket real-time progress updates
- Email notifications
- Self-service password reset
- Undo/redo in review workflow
- PDF report export (Excel only)
- Rate limiting
- External API calls or cloud services
- Multi-language OCR (English only for MVP)

## Blocking Questions

None — all architecture decisions are resolved.

## Open Questions

- What is the expected average PDF page count for typical use cases?
- What is the expected number of requirements per Excel template?
- Are there specific compliance rules that need custom deterministic logic beyond numeric comparison?

## Follow-Ups

- After MVP-6 (validation), evaluate OCR quality and consider PaddleOCR upgrade if needed
- After MVP-4 (matching), evaluate whether ChromaDB semantic search improves results
- After MVP-7 (UI), gather user feedback on review workflow ergonomics
- Consider PDF inline viewer in Streamlit if users request it

## Notes

- PRD source: `prd.md` in project root
- 61 architecture decisions resolved via interview
- System must work offline after initial model/package installation
- All LLM output must be validated with Pydantic before use
- Deterministic Python handles: file handling, PDF extraction, OCR orchestration, database operations, arithmetic, unit conversion, rule validation, Excel cell operations, formatting, final validation
- AI handles: understanding, classification, semantic mapping, complex reasoning, requirement interpretation, evidence selection
