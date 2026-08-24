---
type: Interview Ledger
parent: spec.md
---

## Records

### L1

Status: current

Question: Which local models should the system target?

Answer: Llama 3.2 3B (text model only). No vision model due to hardware constraints.

Decision: Use Llama 3.2 3B via Ollama for all AI tasks. No vision model. Rely on OCR + text model post-processing for image content.

Constraints:
- ~2GB VRAM only
- Structured JSON output needs tight prompting and validation retries
- Context window is smaller (~8K tokens) — chunking strategy is critical
- Evidence extraction confidence scores should be treated more conservatively

### L2

Status: current

Question: What types of PDFs will you process most often?

Answer: All equally. Need full pipeline for text+tables+images+OCR from day one.

Decision: MVP-1 includes text + tables + images + OCR + vision analysis (replaced by OCR + text model) all together.

### L3

Status: current

Question: Should we build the FastAPI backend first, then Streamlit as a client?

Answer: Backend first (Recommended)

Decision: Build FastAPI backend with all endpoints first. Then build Streamlit as a thin client calling those endpoints.

Reason: Backend is testable independently, Streamlit can be replaced with React later, API contracts are locked before UI exists.

### L4

Status: current

Question: Which ORM/migration tool should we use for PostgreSQL?

Answer: SQLAlchemy 2.0 + Alembic (Recommended)

Decision: Use SQLAlchemy 2.0 for ORM and Alembic for database migrations.

### L5

Status: current

Question: When should we introduce ChromaDB vector search?

Answer: After MVP-4 (Recommended)

Decision: Build deterministic matching first (MVP-1 through MVP-4). Add ChromaDB only when semantic retrieval is needed for complex requirements.

### L6

Status: current

Question: Will this system be used by a single person locally, or shared across a team/network?

Answer: Team shared (same network)

Decision: System will be used by multiple users on a local network. Need basic auth or API key.

### L7

Status: current

Question: How should concurrent processing jobs be handled when multiple users upload files?

Answer: Background tasks + polling (Recommended)

Decision: Use FastAPI BackgroundTasks for processing. Client polls GET /runs/{run_id} for status. No WebSocket.

### L8

Status: current

Question: How should file storage be organized for uploaded files and processed results?

Answer: Two-zone storage (Recommended)

Decision: Uploads directory (temporary, cleaned after processing) + Processed directory (permanent results, versioned). Both Docker-mountable.

### L9

Status: current

Question: How should processing failures be handled when jobs fail mid-way?

Answer: Partial save + retry (Recommended)

Decision: Store partial results on failure. Show which step failed. Allow retry from the failed step.

### L10

Status: current

Question: How should the human review workflow operate for team-shared use?

Answer: Bulk approve + selective review (Recommended)

Decision: Auto-approve high-confidence (>0.90). Flag low-confidence for review. Reviewer bulk-approves all high-confidence, then reviews flagged items only.

### L11

Status: current

Question: Which core architectural pattern should the system follow?

Answer: Pipeline pattern (Recommended)

Decision: Each phase is an independent module with defined input/output. Data flows through steps. Matches PRD architecture. Easy to test, retry, and swap components.

### L12

Status: current

Question: How should data flow between pipeline steps?

Answer: ProcessingContext object (Recommended)

Decision: Single context object passed through pipeline. Contains all state. Serialized to DB after each step. Enables retry-from-failure.

### L13

Status: current

Question: How should the LLM abstraction layer be designed?

Answer: Single provider class (Recommended)

Decision: LocalLLMProvider wraps Ollama. Handles chat, vision (N/A), embeddings. Configurable model names, retry logic, structured output parsing.

### L14

Status: current

Question: How should multiple PDF parsers be orchestrated for different page types?

Answer: Router + strategy pattern, merge multiple parsers per page.

Decision: PDFRouter detects page type (text/table/image/scanned/mixed) then delegates to appropriate parser(s). For mixed pages, run multiple parsers and merge results.

### L15

Status: current

Question: How should the Excel structure be analyzed and requirements detected dynamically?

Answer: Deterministic analyzer + AI mapper, simplified.

Decision: Python scans structure (sheets, headers, merged cells, vendor columns) deterministically. LLM maps canonical fields to Excel locations.

### L16

Status: current

Question: What testing framework and structure should be used?

Answer: pytest + fixtures (Recommended)

Decision: pytest with fixtures for DB, sample files, mocked LLM. Test directories per phase.

### L17

Status: current

Question: How should the compliance engine resolve requirements against reference data?

Answer: Layered resolution (Recommended)

Decision: Exact → rules → unit conversion → semantic → LLM. Each layer tries to resolve. Skip higher layers if lower layer is confident. Minimizes LLM calls.

### L18

Status: current

Question: How should system configuration be managed across Docker and local development?

Answer: .env + Pydantic BaseSettings (Recommended)

Decision: .env file for Docker, Pydantic BaseSettings for type-safe loading. Environment variables override .env.

### L19

Status: current

Question: What authentication mechanism for team-shared network use?

Answer: Name/email + password

Decision: Users log in with name/email and password. Simple identification with password security.

### L20

Status: current

Question: How should user passwords be stored in the database?

Answer: bcrypt hashing (Recommended)

Decision: Use bcrypt hashing via passlib. Passwords never stored in plain text.

### L21

Status: current

Question: Should users see only their own documents, or everyone's documents?

Answer: Own documents only, admin sees all.

Decision: Each user sees only their uploads and runs. Admin can see all runs.

### L22

Status: current

Question: How should users see processing progress for large documents?

Answer: Polling + progress bar (Recommended)

Decision: Backend stores progress in DB. Streamlit polls every 2-3 seconds. Shows progress bar + current step text.

### L23

Status: current

Question: How should processing timeouts be handled for large, complex documents?

Answer: Per-step timeouts

Decision: Each pipeline step has its own timeout (LLM: 120s, OCR: 60s). Step failure saves partial results. No overall job timeout.

### L24

Status: current

Question: How should PostgreSQL connections be managed for concurrent users?

Answer: SQLAlchemy built-in pooling (Recommended)

Decision: SQLAlchemy's QueuePool. Configure pool_size=5, max_overflow=10. Sessions managed via FastAPI DI.

### L25

Status: current

Question: Which services should be included in the Docker Compose stack?

Answer: 4 services (Recommended)

Decision: FastAPI + Streamlit + PostgreSQL + Ollama. All on shared Docker network. Volumes for model and data persistence.

### L26

Status: current

Question: How should logging be implemented for debugging and audit trails?

Answer: structlog + file rotation (Recommended)

Decision: Structured JSON logs via structlog. Console output for Docker. File output for audit. Daily rotation.

### L27

Status: current

Question: How should users be notified when their processing job completes or fails?

Answer: In-app status only (Recommended)

Decision: Status badges in Streamlit. User checks the Runs page. No external notifications for MVP.

### L28

Status: current

Question: How should the system handle Excel template changes across versions?

Answer: Hash-based versioning (Recommended)

Decision: Hash uploaded file. Match to previous version if same hash. Re-analyze if different. Store versions with numbers.

### L29

Status: current

Question: How should PDF pages be rendered for OCR and vision analysis?

Answer: PyMuPDF 300 DPI render (Recommended)

Decision: Render full page as image at 300 DPI using fitz. Captures everything on the page.

### L30

Status: current

Question: Should users upload PDF and Excel files simultaneously or sequentially?

Answer: Simultaneous upload (Recommended)

Decision: Two file upload widgets side by side. User uploads both, then clicks Start.

### L31

Status: current

Question: How should invalid LLM JSON output be handled?

Answer: Pydantic + retry + fallback (Recommended)

Decision: Parse with Pydantic. If invalid, retry once with error context. If still invalid, mark as failed. Never use bad data silently.

### L32

Status: current

Question: How should multiple simultaneous processing jobs be queued?

Answer: FIFO queue (Recommended)

Decision: First in, first out. Jobs processed in submission order. Shows queue position.

### L33

Status: current

Question: How should PostgreSQL data be backed up for the team-shared system?

Answer: Docker volume + daily cron (Recommended)

Decision: PostgreSQL data in Docker volume. Daily pg_dump to backups/ directory. Date-stamped files.

### L34

Status: current

Question: How should users download the generated Excel files?

Answer: Streamlit download button (Recommended)

Decision: File stored on server. Download button in Streamlit UI. Browser downloads directly.

### L35

Status: current

Question: How should system health be monitored and displayed to users?

Answer: Health endpoint + sidebar indicator (Recommended)

Decision: GET /health checks Ollama + PostgreSQL. Streamlit sidebar shows green/red status.

### L36

Status: current

Question: How should AI prompts be organized and managed?

Answer: Prompt functions in files (Recommended)

Decision: Each prompt is a Python function in app/ai/prompts/. Takes context, returns formatted string.

### L37

Status: current

Question: Which OCR engine should be used for scanned pages and image text extraction?

Answer: Multiple engines with fallback (Recommended)

Decision: Tesseract first, PaddleOCR fallback for low quality. Best OCR quality.

### L38

Status: current

Question: Without a vision model, how should images with technical content be processed?

Answer: OCR + text model post-processing (Recommended)

Decision: OCR extracts all text from images. Text model then parses and structures the extracted text.

### L39

Status: current

Question: How should Ollama manage resources for concurrent team use?

Answer: Parallel=2 + KeepAlive (Recommended)

Decision: Allow 2 concurrent requests. Keep model loaded 5 min. Additional requests queue.

### L40

Status: current

Question: What should happen on first system startup?

Answer: Auto-setup on first run (Recommended)

Decision: Auto-pull Ollama model, run DB migrations, first user becomes admin.

### L41

Status: current

Question: When a user navigates between pages in the app, should it remember their information?

Answer: Remember everything (Recommended)

Decision: App remembers who you are, what you uploaded, your progress. Standard session state.

### L42

Status: current

Question: How long should uploaded files and processing results be retained?

Answer: Keep indefinitely (Recommended)

Decision: Keep all files and results forever. Users manually delete if needed.

### L43

Status: current

Question: Should there be limits on how often users can submit processing jobs?

Answer: No limits for MVP (Recommended)

Decision: No rate limiting. FIFO queue handles ordering.

### L44

Status: current

Question: How should processing errors be displayed to non-technical users?

Answer: Plain language error cards (Recommended)

Decision: Clear error message per failed step. What went wrong, what user can do. No raw tracebacks.

### L45

Status: current

Question: Should the system generate a processing summary report?

Answer: Excel only (corrected from initial recommendation)

Decision: Summary sheet added to generated Excel file. No separate report format.

### L46

Status: current

Question: Can a human user change the AI's compliance answers in the Excel?

Answer: Yes, change anything (Recommended)

Decision: User can change any AI answer. All changes logged with user name and timestamp.

### L47

Status: current

Question: Should the review screen support undo/redo for user edits?

Answer: No undo for MVP (Recommended)

Decision: Changes save immediately. User can re-run AI analysis to reset.

### L48

Status: current

Question: How detailed should the evidence be shown during human review?

Answer: Full evidence + source reference (Recommended)

Decision: Show requirement, decision, confidence, evidence text, source page/table. User opens original PDF separately.

### L49

Status: current

Question: Should users be able to approve or reject multiple requirements at once during review?

Answer: Yes, bulk actions (Recommended)

Decision: Approve all high-confidence, approve all compliant, select multiple for batch action.

### L50

Status: current

Question: What export formats should be supported beyond the populated Excel file?

Answer: Excel only

Decision: Primary output is populated Excel workbook only.

### L51

Status: current

Question: How should PDF source references be shown during review?

Answer: Page number + reference only (Recommended)

Decision: Show 'Page 15, Table T15-02' in review UI. User opens original PDF separately.

### L52

Status: current

Question: Should the system detect duplicate PDF uploads?

Answer: Yes, hash-based detection (Recommended)

Decision: Hash uploaded PDF. Warn if duplicate found. Offer to reuse previous results or re-process.

### L53

Status: current

Question: Should users be able to cancel a processing job that's already running?

Answer: Yes, cancel button (Recommended)

Decision: Show cancel button during processing. Mark run as CANCELLED. Save partial results.

### L54

Status: current

Question: How should users find specific processing runs in their history?

Answer: Search + filter (Recommended)

Decision: Search by filename, filter by date/status, sort by date.

### L55

Status: current

Question: Should users be able to re-run processing with different Excel templates using the same PDF?

Answer: Yes, re-run with new Excel (Recommended)

Decision: Reuse PDF extraction results, swap Excel template. Saves time.

### L56

Status: current

Question: What should the admin user be able to do that regular users cannot?

Answer: Full admin control

Decision: Admin can view all runs, manage users, view health/logs, trigger backups, modify any data.

### L57

Status: current

Question: How should new users create accounts in the system?

Answer: Admin-only registration

Decision: Only admin can create new user accounts.

### L58

Status: current

Question: How should forgotten passwords be handled?

Answer: Admin resets password (Recommended)

Decision: User contacts admin. Admin sets new password. No self-service reset.

### L59

Status: current

Question: Should the system process all Excel sheets automatically, or let the user choose?

Answer: Process all sheets (Recommended)

Decision: System analyzes all sheets automatically. Detects which have requirements.

### L60

Status: current

Question: How should very large PDF files (500+ pages) be handled?

Answer: Batch processing + size limits (Recommended)

Decision: Max 100MB PDF, 50MB Excel. Process in batches of 10 pages. Show progress. Allow cancellation.

### L61

Status: current

Question: When a team member opens the app, what should they see first?

Answer: Name/email login (Recommended)

Decision: Simple login screen with name/email and password authentication.
