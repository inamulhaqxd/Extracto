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

## ACT Workflow

ACT workflow storage for new Specs is configured in `.act/config.yaml`.

ACT workflow semantics, Workflow Storage selection, artifact vocabulary, and domain-doc guidance are defined in `.act/workflow.md`.
