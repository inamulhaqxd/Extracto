# Agent Guidance

## Project

AI-based RFP PDF-to-Excel automation system. Local, private, modular.

## Architecture

Pipeline pattern. Each phase is an independent module with defined inputs/outputs.

## Conventions

- Python 3.11+
- FastAPI for backend
- Streamlit for frontend
- SQLAlchemy 2.0 + Alembic for database
- pytest for testing
- Pydantic for validation
- Type hints required on all functions and methods

## Verification Rules

After completing any task or work item, ALWAYS run:

```bash
python -m ruff check ai_rfp_excel/app --ignore E501
python -m mypy ai_rfp_excel/app --ignore-missing-imports --explicit-package-bases
```

Fix all errors before committing. No exceptions.

## Skills Reference

Use the `skill` tool to load the relevant skill before working on matching tasks.

### Python & Backend

| Skill | When to Use |
|-------|-------------|
| `python-pro` | Writing modern Python 3.12+ code, async patterns, type hints, performance optimization |
| `python-fastapi-development` | Building FastAPI routes, middleware, dependency injection, error handlers |
| `fastapi-pro` | Advanced FastAPI: SQLAlchemy 2.0 integration, background tasks, WebSocket, microservices |
| `async-python-patterns` | Implementing async/await in pipeline steps, concurrent PDF processing, background jobs |
| `pydantic-models-py` | Creating Pydantic models for API contracts, validation, settings, and pipeline context |
| `architecture-patterns` | Designing Clean Architecture layers, pipeline module boundaries, dependency inversion |

### Database & Migrations

| Skill | When to Use |
|-------|-------------|
| `postgresql` | Writing Postgres-specific queries, JSONB for config storage, full-text search, indexing |
| `postgresql-table-design` | Designing new tables, columns, constraints, indexes for processing runs and results |
| `database-migrations-sql-migrations` | Creating Alembic migrations, zero-downtime schema changes, rollback strategies |

### AI & LLM

| Skill | When to Use |
|-------|-------------|
| `local-llm-expert` | Ollama setup, model selection, VRAM optimization, quantization (GGUF), local inference |
| `prompt-engineering-patterns` | Designing structured JSON prompts for spec extraction, compliance matching, evidence generation |
| `llm-evaluation` | Measuring LLM accuracy on extraction/matching tasks, building evaluation benchmarks |

### PDF & Document Processing

| Skill | When to Use |
|-------|-------------|
| `pdf-official` | PDF text/table extraction, PyMuPDF rendering, Tesseract/PaddleOCR integration, form filling |

### Testing

| Skill | When to Use |
|-------|-------------|
| `pytest-skill` | Writing pytest fixtures, parametrize, mocking LLM providers, integration tests per pipeline phase |
| `act-flutter-robot-testing` | Not applicable — Flutter only. Skip for this project. |

### DevOps & Infrastructure

| Skill | When to Use |
|-------|-------------|
| `docker-expert` | Docker Compose setup (FastAPI + Streamlit + PostgreSQL + Ollama), multi-stage builds, volume config |
| `ci-security-scanning` | GitHub Actions setup: secrets scanning, dependency audit, SAST for the pipeline codebase |

### ACT Workflow Skills

| Skill | When to Use |
|-------|-------------|
| `act-interview` | Resolving intent, constraints, and decision dependencies before writing a Spec |
| `act-create-spec` | Saving conversation context as a Spec file |
| `act-refine-spec` | Reviewing a Spec for contradictions, gaps, and codebase misalignment |
| `act-create-issues` | Turning a Spec into independently executable Work Items |
| `act-implement` | Implementing a Work Item or Spec end-to-end |
| `act-git-commit` | Creating conventional commits for staged changes |
| `act-workflow-compound` | Capturing session insights into reusable documentation |

### Skills NOT Applicable to This Project

These are global skills but do not apply to this Python/FastAPI/Streamlit project:
- `act-flutter-*`, `act-dart-*`, `act-figma-to-flutter` — Flutter/Dart only
- `act-web-*`, `next-*`, `typescript-*`, `tailwind-*`, `react-*`, `vercel-*`, `motion-*`, `nextjs_*` — Next.js/React only
- `supabase*` — We use PostgreSQL directly, not Supabase
- `design-system`, `web-design-guidelines` — UI design review, not relevant for pipeline logic

## ACT Workflow

ACT workflow storage for new Specs is configured in `.act/config.yaml`.

ACT workflow semantics, Workflow Storage selection, artifact vocabulary, and domain-doc guidance are defined in `.act/workflow.md`.
