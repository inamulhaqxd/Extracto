# Extracto AI

> **100% Local, Hallucination-Free RFP PDF-to-Excel Automation**  
> Automatically reads technical specification PDFs and accurately populates customer RFP Excel questionnaires with compliance answers and evidence citations.

---

## 📌 Overview

| Input | Output | Execution |
| :--- | :--- | :--- |
| **Technical PDF** (datasheet / BOM) + **Excel Template** (RFP questionnaire) | **Populated Excel** with answers, compliance status & citations | **100% Local** (Ollama, zero cloud APIs) |

---

## 🔄 How It Works

```
[ Technical PDF ] + [ Excel Questionnaire ]
                     │
                     ▼
  1. Extract Text & Tables (PyMuPDF + Local OCR)
  2. Parse Excel Questions (Dynamic Slot Detection)
  3. Retrieve Grounded Evidence (Hybrid Search)
  4. Verify Compliance (Local LLM Reasoning)
  5. Populate Excel In-Place (Formula & Style Safe)
                     │
                     ▼
       [ Completed Excel Workbook ]
```

---

## ⚡ Core Rules

- **Zero Hallucination**: If a spec is not in the document, it outputs `NOT_SPECIFIED`. It never guesses.
- **Yellow Audit Trail**: Cells with missing or low-confidence data are highlighted yellow (`#FFFF00`) for quick human review.
- **Formula & Style Safe**: Original Excel formulas, merged cells, fonts, and borders remain 100% intact.
- **Strictly Offline**: Operates completely on local infrastructure — zero external data leakage.

---

## 🚀 How to Run

### 1. Terminal / CLI (Quickest)

```bash
# Run with sample files
python run_pipeline.py

# Run with your own files
python run_pipeline.py path/to/spec.pdf path/to/questions.xlsx -o output_dir
```

### 2. Full Stack (Web UI + API)

```bash
# Start backend (Port 8000) & frontend (Port 3000)
make run

# Seed admin user (first time only)
make seed
```

- **Web Dashboard**: [http://localhost:3000](http://localhost:3000)
- **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Default Credentials**: `admin@extracto.local` / `AdminPassword123!`

---

## 📁 Repository Structure

```
Extracto/
├── ai_rfp_excel/         # FastAPI backend & 5-phase pipeline engine
│   ├── app/pipeline/     # Core processing steps (Extract -> Search -> Populate)
│   └── tests/            # Automated unit & integration tests
├── frontend/             # Next.js 15 web interface & live run monitor
├── testworkflowfile/     # Sample benchmark PDFs and Excel questionnaires
├── run_pipeline.py       # Standalone CLI runner
└── Makefile              # Task runner (run, stop, test, check)
```

---

## 🛠️ Quick Commands

```bash
make run      # Launch all services
make stop     # Stop all running processes
make test     # Run pipeline test suite
make check    # Run linter (ruff) and typecheck (mypy)
```
