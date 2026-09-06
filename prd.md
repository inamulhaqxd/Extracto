# Project: Local AI-Based RFP PDF-to-Excel Automation System

## 1. Project Objective

Build a completely LOCAL, PRIVATE, and MODULAR AI system that automatically analyzes a reference PDF and an Excel workbook/template and generates a correctly populated Excel workbook.

The system is intended for technical/RFP/Bill of Material/technical specification documents.

The reference PDF may contain:

* Copyable text
* Tables
* Images
* Screenshots
* Scanned pages
* Diagrams
* Product specification images
* Text embedded inside images
* Mixed text + tables + images
* Multiple vendors/products
* Server specifications
* GPU specifications
* Storage specifications
* Networking equipment
* Cloud/virtualization information
* BOM information
* Part/model numbers
* Quantities
* Technical requirements
* Compliance information

The Excel workbook may contain:

* Multiple sheets
* Different sheet names in future versions
* Merged cells
* Formatted tables
* Headers
* Sections/subsections
* Requirements
* Vendor columns
* Compliance columns
* Remarks columns
* Formulas
* Existing formatting
* Hidden rows/columns
* Different layouts
* Different column names
* New or removed sheets
* New or removed requirements
* Changed ordering
* Changed formatting

The system MUST NOT depend on fixed cell addresses or fixed PDF layouts.

The system must remain functional when the reference PDF and Excel template change in future.

---

# 2. Absolute Constraints

## 2.1 Completely Local

No information may leave the local environment.

Do NOT use:

* OpenAI API
* Gemini API
* Claude API
* Cloud OCR
* Cloud embeddings
* Cloud vector databases
* Cloud document processing
* External AI APIs

Use local models and local processing only.

Recommended local AI infrastructure:

* Ollama
* A suitable local instruct/vision model
* Local embedding model
* PostgreSQL
* ChromaDB only when actually required

The architecture must work without Internet access after all required models/packages are installed.

---

# 3. Core Architecture

Implement the following architecture:

```text
Reference PDF
      |
      v
Document Ingestion
      |
      +---- Text Extraction
      |
      +---- Table Extraction
      |
      +---- Image Extraction
      |
      +---- OCR
      |
      +---- Layout Analysis
      |
      v
Normalized Document Representation
      |
      v
Local AI Extraction
      |
      v
Canonical Knowledge Representation
      |
      +--------------------------+
      |                          |
      v                          v
Excel Workbook Analyzer    Requirement Analyzer
      |                          |
      +------------+-------------+
                   |
                   v
          AI Matching Engine
                   |
                   v
       Compliance + Evidence
                   |
                   v
          Excel Population
                   |
                   v
             Validation
                   |
                   v
        Human Review if Needed
                   |
                   v
          Final Excel File
```

Do not bypass the intermediate structured representation.

---

# 4. Technology Stack

Use:

### Backend

Python 3.11+

FastAPI

### Frontend

Next.js frontend with Tailwind CSS and shadcn/ui components.

### PDF

Use a combination of appropriate local tools such as:

* PyMuPDF
* Docling
* pdfplumber
* Camelot/other table extraction tools where appropriate
* Tesseract or another LOCAL OCR engine
* Local vision-language model where required

Do not assume one PDF parser will work for every PDF.

Create an abstraction layer so parsers can be replaced.

### Excel

Use:

* openpyxl

Do not recreate the workbook from scratch unless explicitly necessary.

Use the original workbook as the template and preserve its structure and formatting.

### AI

Use:

* Ollama

The model must be configurable through environment/configuration rather than hardcoded.

The system should support both:

1. Text/instruct model
2. Vision-language model

The vision model is required for images, scanned content, screenshots, diagrams, and information that cannot reliably be extracted as text.

### Database

Use:

* PostgreSQL

### Vector search

Use:

* ChromaDB

Only introduce vector search where semantic retrieval is actually useful.

Do not turn every structured database problem into RAG.

### Validation

Use:

* Pydantic
* Python validation logic

### Deployment

Use:

* Docker
* docker-compose

---

# 5. Phase 0 — Project Setup

Create the project with a clean structure:

```text
ai_rfp_excel/
│
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │
│   ├── ingestion/
│   │   ├── pdf/
│   │   ├── images/
│   │   ├── ocr/
│   │   └── tables/
│   │
│   ├── document/
│   │   ├── models.py
│   │   ├── normalizer.py
│   │   └── chunker.py
│   │
│   ├── ai/
│   │   ├── ollama_client.py
│   │   ├── text_model.py
│   │   ├── vision_model.py
│   │   ├── extraction.py
│   │   ├── classification.py
│   │   ├── matching.py
│   │   └── prompts/
│   │
│   ├── excel/
│   │   ├── analyzer.py
│   │   ├── structure.py
│   │   ├── requirements.py
│   │   ├── mapper.py
│   │   ├── writer.py
│   │   └── validator.py
│   │
│   ├── knowledge/
│   │   ├── canonical_schema.py
│   │   ├── equipment.py
│   │   └── specifications.py
│   │
│   ├── matching/
│   │   ├── semantic.py
│   │   ├── rules.py
│   │   └── compliance.py
│   │
│   ├── evidence/
│   │   ├── models.py
│   │   └── resolver.py
│   │
│   ├── database/
│   │   ├── models.py
│   │   ├── connection.py
│   │   └── repository.py
│   │
│   ├── validation/
│   │
│   └── config.py
│
├── frontend/
│   └── (Next.js Application)
│
├── tests/
│
├── data/
│   ├── uploads/
│   ├── extracted/
│   ├── images/
│   ├── ocr/
│   ├── processed/
│   └── generated/
│
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

Do not put everything in one Python file.

---

# 6. Phase 1 — PDF Ingestion

Build a robust PDF ingestion pipeline.

When a PDF is uploaded:

```text
PDF
 |
 +-- Detect number of pages
 |
 +-- Extract text
 |
 +-- Detect tables
 |
 +-- Extract tables
 |
 +-- Extract embedded images
 |
 +-- Render pages when necessary
 |
 +-- Detect scanned/image-only pages
 |
 +-- OCR where necessary
 |
 +-- Analyze images
 |
 +-- Preserve page numbers
 |
 +-- Preserve source locations
```

The ingestion system must distinguish between:

### Type A

Native/copyable PDF text.

### Type B

Native PDF tables.

### Type C

Embedded images.

### Type D

Scanned pages.

### Type E

Mixed pages.

Do not assume the entire document has one format.

---

# 7. PDF Text Extraction

For every page store:

```json
{
  "document_id": "...",
  "page_number": 1,
  "content_type": "text",
  "text": "...",
  "source": "native_pdf"
}
```

Preserve:

* page number
* text
* document ID
* extraction method
* confidence if applicable

Do not lose page-level provenance.

---

# 8. Table Extraction

Tables are extremely important.

Extract:

* headers
* rows
* columns
* merged cells where possible
* table position
* page number
* surrounding section heading

Example:

```json
{
  "page": 12,
  "table_id": "T12-01",
  "headers": [
    "Part/Model No.",
    "Configuration",
    "Unit Qty"
  ],
  "rows": [
    [
      "SYS-222C-TN",
      "X14DBHM + CSE-DC201...",
      "1"
    ]
  ]
}
```

The system must preserve the relationship between the table and its page.

---

# 9. Image Extraction

Extract embedded images from the PDF.

For every image store:

```text
document_id
page_number
image_id
image_path
bounding_box if available
extraction_method
```

Images may contain:

* Product labels
* Technical specifications
* Screenshots
* Tables
* Diagrams
* Architecture diagrams
* Hardware information
* Text that is not available in the PDF text layer

Never ignore images.

---

# 10. OCR

If a page contains scanned content or an image contains meaningful text:

Run LOCAL OCR.

OCR output must retain:

* page number
* image ID if applicable
* extracted text
* OCR confidence if available

Do not overwrite native PDF text.

Keep:

```text
native_text
ocr_text
```

separately.

Later normalization can combine them.

---

# 11. Vision AI

If an image contains information that OCR cannot adequately understand, send the image to the LOCAL vision-language model.

The vision model should answer structured questions such as:

* What is shown?
* Is this a table?
* What product/model is visible?
* What specifications are visible?
* Is there a diagram?
* Are there labels?
* Is there technical information?
* Is there text that OCR missed?

The model must return structured JSON.

Example:

```json
{
  "image_type": "technical_specification",
  "detected_information": [
    {
      "field": "storage_capacity",
      "value": "15TB",
      "confidence": 0.94
    },
    {
      "field": "disk_type",
      "value": "NVMe-TLC",
      "confidence": 0.92
    }
  ]
}
```

Never allow the vision model to invent missing specifications.

Use:

```text
UNKNOWN
```

when information is unavailable.

---

# 12. Page-Level Document Representation

Create a unified internal representation:

```json
{
  "document_id": "DOC-001",
  "pages": [
    {
      "page_number": 1,
      "text": "...",
      "tables": [],
      "images": [],
      "ocr": [],
      "vision_analysis": []
    }
  ]
}
```

This becomes the source for downstream processing.

---

# 13. Phase 2 — Document Normalization

Normalize extracted information.

Examples:

```text
64GB
64 GB
64 G.B.
64 gigabytes
```

should be understood as the same capacity.

Similarly:

```text
NVIDIA A100
NVIDIA A100 GPU
A100
NVIDIA-A100
```

should be normalized carefully while preserving the original value.

Do NOT destroy the original text.

Store:

```text
original_value
normalized_value
```

---

# 14. Phase 3 — Canonical Knowledge Schema

Create a canonical representation independent of the PDF and Excel layouts.

Support entities such as:

```text
Server
GPU
CPU
Memory
Storage
Disk
Network Adapter
NIC
HBA
Switch
SAN
Cloud
Virtualization
Controller
License
Warranty
Software
Other Equipment
```

Example:

```json
{
  "entity_type": "server",
  "vendor": "...",
  "model": "...",
  "quantity": 3,
  "specifications": {
    "cpu": "...",
    "memory": "...",
    "storage": "...",
    "network": "...",
    "gpu": "..."
  },
  "source_evidence": []
}
```

The schema must be extensible.

Do not hardcode only GPUs and servers.

---

# 15. Provenance

Every extracted fact must be traceable to its source.

For example:

```json
{
  "field": "gpu_model",
  "value": "NVIDIA A100",
  "source": {
    "document_id": "DOC-001",
    "page": 15,
    "table_id": "T15-02",
    "image_id": null
  },
  "confidence": 0.98
}
```

For image-derived information:

```json
{
  "source": {
    "document_id": "DOC-001",
    "page": 18,
    "image_id": "IMG18-03"
  }
}
```

This is mandatory.

---

# 16. Phase 4 — Excel Analyzer

Analyze the uploaded Excel workbook dynamically.

Do NOT hardcode:

```text
B2 = NVMe
B5 = something
```

Instead detect:

* workbook name
* sheet names
* sheet order
* dimensions
* merged cells
* hidden rows
* hidden columns
* formulas
* tables
* headers
* sections
* subsections
* requirement rows
* vendor columns
* compliance columns
* remarks columns
* existing values
* formatting

---

# 17. Excel Structure Representation

Create an internal representation such as:

```json
{
  "sheet_name": "B2-NVMe Storage",
  "sections": [
    {
      "name": "Architecture",
      "requirements": [
        {
          "row": 5,
          "text": "Proposed Modular All Flash storage system..."
        }
      ]
    }
  ]
}
```

The actual schema must be flexible enough to handle different future workbook structures.

---

# 18. Detect Excel Requirements

Identify rows that represent requirements/specifications.

Examples:

```text
Minimum 32 cores per controller
Should have at least 350 TB RAW capacity
Per Disk capacity = 15TB
Should support NVMe-TLC
```

Store:

```text
requirement_id
sheet
row
section
requirement_text
source_cell/range
```

Do not assume every populated row is a requirement.

---

# 19. Detect Vendor/Provider Columns

The workbook may have:

```text
DWP
Premier
Vendor A
Vendor B
```

The system must dynamically detect which columns correspond to vendors/products.

Do not hardcode vendor names.

---

# 20. Phase 5 — Local AI Requirement Understanding

Use the local LLM to understand each requirement.

For example:

```text
"Minimum 32 cores per controller and 64 cores overall"
```

Convert internally to:

```json
{
  "category": "controller",
  "constraints": [
    {
      "field": "cores_per_controller",
      "operator": ">=",
      "value": 32
    },
    {
      "field": "total_cores",
      "operator": ">=",
      "value": 64
    }
  ]
}
```

Where possible, convert requirements into structured constraints.

This allows deterministic validation.

---

# 21. Phase 6 — Matching Engine

Match Excel requirements against canonical reference information.

Use a hybrid approach:

```text
Exact matching
+
Rule-based matching
+
Structured comparison
+
Semantic similarity
+
Local LLM reasoning
```

Do not rely exclusively on an LLM.

For example:

```text
Requirement:
Minimum storage = 350 TB

Reference:
300 TB

```

The deterministic engine should conclude:

```text
NON_COMPLIANT
```

without asking the LLM to perform simple arithmetic.

---

# 22. Compliance States

Use:

```text
COMPLIANT
PARTIALLY_COMPLIANT
NON_COMPLIANT
NOT_FOUND
AMBIGUOUS
```

Never force a yes/no answer when evidence is insufficient.

---

# 23. Evidence Generation

For every decision generate evidence.

Example:

```json
{
  "requirement_id": "REQ-006",
  "status": "COMPLIANT",
  "evidence": [
    {
      "value": "15TB NVMe-TLC",
      "page": 24,
      "source_type": "table"
    }
  ],
  "confidence": 0.96
}
```

The system must be able to explain:

```text
Why did you mark this compliant?
```

with:

```text
Reference.pdf
Page 24
Table T24-02
```

or:

```text
Reference.pdf
Page 31
Image IMG31-02
```

---

# 24. Hallucination Prevention

The AI MUST NOT invent:

* Server models
* GPU models
* Quantities
* Storage capacities
* Vendor names
* Compliance evidence
* Specifications
* Page numbers
* Product features

If evidence cannot be found:

```text
NOT_FOUND
```

If evidence conflicts:

```text
AMBIGUOUS
```

If two sources disagree, preserve both sources and flag the conflict.

---

# 25. Phase 7 — Excel Mapping

Map AI results to Excel dynamically.

The AI determines semantic mapping.

Python performs the actual write.

For example:

```text
Excel:
"GPU Type"

Canonical field:
gpu.model
```

Then Python writes the value.

Do not allow the LLM to directly generate arbitrary cell-writing code.

---

# 26. Excel Population

Use openpyxl.

Preserve the original workbook wherever possible:

* Sheet names
* Sheet order
* Formatting
* Borders
* Fonts
* Cell widths
* Merged cells
* Existing formulas
* Existing values
* Hidden rows/columns
* Page setup

Only modify cells that are intended to be populated.

Do not destroy unrelated workbook content.

---

# 27. Formatting

If the template has specific formatting for:

```text
Compliant
Non-Compliant
Remarks
```

preserve and/or reproduce it consistently.

Do not redesign the workbook unless explicitly requested.

The output should look like the original workbook, only correctly populated.

---

# 28. Phase 8 — Validation

After generating the workbook:

Run automated validation.

Check:

```text
Workbook opens successfully
Expected sheets still exist
No accidental sheets removed
No unexpected rows removed
No unexpected columns removed
Required cells populated
No invalid data types
Formulas preserved
Merged cells preserved where possible
Formatting preserved
Every AI conclusion has evidence
Low-confidence results are flagged
No unsupported claims inserted
```

If validation fails, do not silently return the file.

Show an error report.

---

# 29. Confidence Thresholds

Define configurable thresholds.

Example:

```text
>= 0.90
High confidence

0.70 - 0.89
Needs review

< 0.70
Do not automatically populate
```

Make these configurable.

Do not hardcode them throughout the application.

---

# 30. Human Review

Provide a review screen.

Show:

```text
Requirement
AI Result
Confidence
Evidence
PDF Page
Proposed Excel Cell
```

Example:

```text
Requirement:
Minimum 350 TB RAW capacity

Result:
COMPLIANT

Confidence:
94%

Evidence:
350 TB RAW capacity

Source:
Reference.pdf — Page 23

[Accept]
[Reject]
[Edit]
```

Low-confidence results should require review before final generation.

---

# 31. Versioning

Both PDF and Excel may change.

Store:

```text
document hash
document version
Excel hash
Excel version
processing timestamp
model used
prompt version
processing result
```

Example:

```text
Run #001
Reference_v1.pdf
Template_v1.xlsx

Run #002
Reference_v2.pdf
Template_v1.xlsx

Run #003
Reference_v2.pdf
Template_v2.xlsx
```

Do not overwrite historical runs.

---

# 32. Database

Use PostgreSQL to store:

```text
documents
document_pages
document_tables
document_images
extracted_facts
equipment
requirements
workbooks
workbook_sheets
mappings
compliance_results
evidence
processing_runs
validation_results
```

Use foreign keys and proper relationships.

---

# 33. RAG / Vector Search

Do NOT introduce RAG everywhere.

Use PostgreSQL/structured data for structured information.

Use ChromaDB/local embeddings when:

* PDFs are very large
* requirements need semantic retrieval
* relevant evidence may occur far apart
* exact keyword matching is insufficient

The RAG pipeline must remain local:

```text
PDF
 ↓
Chunks
 ↓
Local embedding model
 ↓
ChromaDB
 ↓
Relevant chunks
 ↓
Local LLM
```

Never send documents to external embedding APIs.

---

# 34. Local Model Abstraction

Do not hardcode the application around one model.

Create:

```text
LocalLLMProvider
```

with configurable:

```text
model_name
base_url
temperature
context_length
timeout
```

Support:

```text
Text model
Vision model
Embedding model
```

The application should be able to change models through configuration.

---

# 35. Structured LLM Output

Whenever possible require JSON output.

Do not rely on:

```text
"Yes, this seems compliant..."
```

Prefer:

```json
{
  "status": "COMPLIANT",
  "confidence": 0.94,
  "evidence": [
    {
      "text": "...",
      "page": 24
    }
  ]
}
```

Validate all LLM output with Pydantic before using it.

If JSON is invalid:

1. Attempt structured retry.
2. If still invalid, mark the operation as failed.
3. Do not silently parse unreliable output.

---

# 36. Security

Implement:

* Local-only file storage
* File type validation
* File size limits
* Safe filenames
* Temporary file cleanup
* No arbitrary code execution from uploaded files
* No macros execution
* No external network calls during processing
* Configuration through environment variables
* Logging without exposing sensitive document contents unnecessarily

Never execute VBA/macros contained in uploaded Excel files.

---

# 37. Logging

Create structured logs for:

```text
PDF uploaded
Excel uploaded
Extraction started
Extraction completed
OCR performed
Vision analysis performed
AI extraction performed
Requirement matching started
Requirement matching completed
Excel generation started
Validation started
Validation completed
```

Do not log entire sensitive documents by default.

---

# 38. API

Create endpoints approximately like:

```text
POST /upload/pdf
POST /upload/excel

POST /analyze/document
POST /analyze/workbook

POST /process

GET /runs/{run_id}

GET /runs/{run_id}/results

GET /runs/{run_id}/review

POST /runs/{run_id}/approve

POST /runs/{run_id}/generate

GET /runs/{run_id}/download
```

Keep API logic separate from business logic.

---

# 39. Frontend

Next.js web interface:

```text
AI RFP Excel Generator

1. Upload Reference PDF
2. Upload Excel Template

[ Analyze Files ]

Document:
Pages: 87
Tables: 42
Images: 31
OCR Pages: 12

Workbook:
Sheets: 6
Requirements: 247

[ Start AI Analysis ]
```

Then show:

```text
Processing...

PDF extraction       ✓
Table extraction     ✓
Image extraction     ✓
OCR                  ✓
Vision analysis      ✓
Excel analysis       ✓
Requirement mapping  ✓
Compliance analysis  ✓
Validation            ✓
```

Then show:

```text
Results

Compliant             183
Partially Compliant    21
Non-Compliant          17
Not Found              26
Ambiguous               4

High Confidence       91.4%
Needs Review           8.6%
```

Then:

```text
[ Review ]
[ Generate Excel ]
```

---

# 40. Testing Strategy

Do not test only with one PDF.

Create test categories:

### PDF tests

* Text-only PDF
* Table-heavy PDF
* Image-heavy PDF
* Scanned PDF
* Mixed PDF
* Poor-quality scan
* Multi-column PDF
* PDF with diagrams

### Excel tests

* Original workbook
* Renamed columns
* Added sheet
* Removed sheet
* Changed sheet order
* Added requirement
* Removed requirement
* Merged cells
* Hidden rows
* Formulas
* Different formatting

### AI tests

* Exact match
* Semantic match
* Partial match
* Contradictory evidence
* Missing information
* Ambiguous information
* Hallucination attempts

---

# 41. Evaluation Dataset

Create a small manually verified dataset.

For each requirement record the expected:

```text
requirement
expected status
expected evidence
expected source page
expected Excel location
```

Use this to evaluate the system.

Do not claim the AI is reliable merely because it generated an Excel file.

Measure:

```text
Extraction accuracy
Requirement matching accuracy
Compliance accuracy
Evidence accuracy
Excel population accuracy
False positive rate
False negative rate
```

---

# 42. MVP Strategy

Do NOT implement the entire system simultaneously.

Build in this exact order:

## MVP-1

PDF:

```text
PDF
→ text
→ tables
→ images
→ OCR
→ structured JSON
```

## MVP-2

Excel:

```text
Excel
→ workbook structure
→ sheets
→ requirements
→ vendor columns
→ structured JSON
```

## MVP-3

Local AI:

```text
Structured PDF
→ Ollama
→ canonical equipment/specification data
```

## MVP-4

Matching:

```text
Excel requirements
+
Canonical data
→ compliance results
+
evidence
```

## MVP-5

Excel:

```text
Compliance results
→ original Excel
→ populated Excel
```

## MVP-6

Validation:

```text
Generated Excel
→ automated validation
→ errors/review
```

## MVP-7

UI:

```text
Upload
→ Analyze
→ Review
→ Generate
→ Download
```

## MVP-8

Production:

```text
Docker
PostgreSQL
Versioning
Audit logs
Authentication if required
Performance optimization
```

---

# 43. Critical Design Rule

Separate responsibilities.

### AI is responsible for:

```text
Understanding
Classification
Semantic mapping
Complex reasoning
Image interpretation
Requirement interpretation
Evidence selection
```

### Deterministic Python is responsible for:

```text
File handling
PDF extraction
OCR orchestration
Database operations
Arithmetic
Unit conversion
Rule validation
Excel cell operations
Excel formatting
Workbook preservation
Final validation
```

Never let the LLM control everything.

---

# 44. Final End-to-End Workflow

The finished system must work like this:

```text
USER
 |
 | Upload PDF
 | Upload Excel
 v
INGESTION
 |
 +--> Native Text
 +--> Tables
 +--> Images
 +--> OCR
 +--> Vision
 |
 v
DOCUMENT REPRESENTATION
 |
 v
CANONICAL KNOWLEDGE
 |
 v
EXCEL ANALYSIS
 |
 +--> Sheets
 +--> Sections
 +--> Requirements
 +--> Vendors
 +--> Target fields
 |
 v
REQUIREMENT INTERPRETATION
 |
 v
EVIDENCE RETRIEVAL
 |
 v
COMPLIANCE ENGINE
 |
 +--> COMPLIANT
 +--> PARTIALLY_COMPLIANT
 +--> NON_COMPLIANT
 +--> NOT_FOUND
 +--> AMBIGUOUS
 |
 v
EVIDENCE + CONFIDENCE
 |
 v
HUMAN REVIEW
 |
 v
EXCEL GENERATION
 |
 v
VALIDATION
 |
 v
FINAL EXCEL
```

---

# 45. Definition of Done

The project is considered complete only when:

1. The system runs locally.
2. No document information leaves the local environment.
3. Copyable PDF text is extracted.
4. PDF tables are extracted.
5. Embedded PDF images are extracted.
6. Scanned pages are detected.
7. OCR is performed locally where required.
8. Images can be analyzed using a local vision model.
9. Page-level source references are preserved.
10. Extracted information is normalized.
11. A canonical knowledge representation exists.
12. Excel structure is detected dynamically.
13. Excel requirements are detected dynamically.
14. Vendor/product columns are detected dynamically.
15. Requirements can be semantically matched to reference information.
16. Compliance can be determined using both AI and deterministic rules.
17. Every important AI decision has evidence.
18. AI cannot invent unsupported specifications.
19. Unknown information is marked as `NOT_FOUND`.
20. Conflicting information is marked as `AMBIGUOUS`.
21. Low-confidence results can be manually reviewed.
22. The original Excel template is preserved.
23. Formatting and merged cells are preserved where possible.
24. Generated workbooks are validated before delivery.
25. PDF and Excel versions are tracked.
26. Processing history is stored.
27. The system can handle future PDF layout changes.
28. The system can handle future Excel layout changes.
29. Models can be changed through configuration.
30. The complete system can be deployed locally with Docker.

---

# 46. Development Instruction

Implement this project incrementally.

After completing each phase:

1. Explain what was implemented.
2. Show the relevant files.
3. Run tests.
4. Show test results.
5. Fix errors before moving forward.
6. Do not skip phases.
7. Do not create fake/mock functionality and claim it is complete.
8. Do not hardcode the current PDF structure.
9. Do not hardcode the current Excel cell positions.
10. Do not use external AI APIs.
11. Do not implement unnecessary RAG before structured extraction works.
12. Do not allow the LLM to directly manipulate Excel cells.
13. Preserve source provenance throughout the entire pipeline.
14. Prefer deterministic logic whenever a task does not require AI.
15. Ask for confirmation only when an architectural decision genuinely cannot be determined from the requirements.

Start with **Phase 0 — Project Setup**, then proceed one phase at a time.
