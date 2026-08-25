.PHONY: help install dev test lint typecheck run-api run-streamlit docker-up docker-down migrate clean

help:
	@echo.
	@echo Available commands:
	@echo   make install        - Install dependencies
	@echo   make dev            - Install dev dependencies
	@echo   make test           - Run all tests
	@echo   make test-cov       - Run tests with coverage
	@echo   make lint           - Run ruff linter
	@echo   make lint-fix       - Run ruff with auto-fix
	@echo   make typecheck      - Run mypy type checker
	@echo   make check          - Run lint + typecheck
	@echo   make run-api        - Start FastAPI server
	@echo   make run-streamlit  - Start Streamlit UI
	@echo   make docker-up      - Start all services with Docker
	@echo   make docker-down    - Stop all Docker services
	@echo   make docker-logs    - View Docker logs
	@echo   make migrate        - Run database migrations
	@echo   make migrate-new    - Create new migration (msg="description")
	@echo   make clean          - Remove Python cache files
	@echo.

install:
	pip install -r ai_rfp_excel/requirements.txt

dev:
	pip install -r ai_rfp_excel/requirements.txt
	pip install ruff mypy pytest pytest-asyncio pytest-cov httpx

test:
	python -m pytest ai_rfp_excel/tests/ -v

test-cov:
	python -m pytest ai_rfp_excel/tests/ -v --cov=ai_rfp_excel/app --cov-report=term-missing

lint:
	python -m ruff check ai_rfp_excel/app --ignore E501

lint-fix:
	python -m ruff check ai_rfp_excel/app --ignore E501 --fix

typecheck:
	python -m mypy ai_rfp_excel/app --ignore-missing-imports --explicit-package-bases

check: lint typecheck
	@echo All checks passed!

run-api:
	uvicorn ai_rfp_excel.app.main:app --reload --port 8000

run-streamlit:
	streamlit run ai_rfp_excel/frontend/streamlit_app.py --server.port 8501

docker-up:
	docker-compose -f ai_rfp_excel/docker-compose.yml up -d

docker-down:
	docker-compose -f ai_rfp_excel/docker-compose.yml down

docker-logs:
	docker-compose -f ai_rfp_excel/docker-compose.yml logs -f

migrate:
	python -m alembic -c ai_rfp_excel/alembic.ini upgrade head

migrate-new:
	python -m alembic -c ai_rfp_excel/alembic.ini revision --autogenerate -m "$(msg)"

clean:
	for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
	for /r . %%f in (*.pyc) do @if exist "%%f" del /q "%%f"
