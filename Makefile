.PHONY: help install dev test test-cov lint lint-fix typecheck check run run-all run-api run-frontend run-ui stop seed docker-up docker-down docker-logs migrate migrate-new clean

help:
	@echo Available commands:
	@echo   make run            - Start both Backend (8000) and Frontend (3000) in separate windows
	@echo   make run-api        - Start FastAPI backend server (port 8000)
	@echo   make run-frontend   - Start Next.js UI frontend (port 3000)
	@echo   make stop           - Stop all running backend and frontend processes
	@echo   make seed           - Seed initial admin user in database
	@echo   make install        - Install requirements
	@echo   make dev            - Install requirements and development tooling
	@echo   make test           - Run all test suites
	@echo   make test-cov       - Run tests with coverage report
	@echo   make lint           - Run ruff linter
	@echo   make lint-fix       - Run ruff with auto-fix
	@echo   make typecheck      - Run mypy type checker
	@echo   make check          - Run full lint and typecheck
	@echo   make docker-up      - Start all services with Docker Compose
	@echo   make docker-down    - Stop all Docker services
	@echo   make docker-logs    - View Docker logs
	@echo   make migrate        - Run database migrations (Alembic)
	@echo   make migrate-new    - Create new migration (msg="description")
	@echo   make clean          - Remove Python cache files

# Start Docker Backend (Postgres + FastAPI + Backup) and Native Frontend (Next.js)
run:
	@powershell -Command "docker compose -f ai_rfp_excel/docker-compose.yml up -d; Start-Process powershell -ArgumentList '-NoExit', '-Command', 'cd frontend; pnpm dev'; Write-Host 'TenderFlow Docker backend (http://localhost:8000) and Native frontend (http://localhost:3000) launched!'"

run-all: run

# Individual Server Targets
run-api:
	docker compose -f ai_rfp_excel/docker-compose.yml up -d postgres api

run-frontend:
	cd frontend && pnpm dev

run-ui: run-frontend

# Stop All Running Project Processes (Docker backend & Port 3000 frontend)
stop:
	@powershell -Command "docker compose -f ai_rfp_excel/docker-compose.yml down; $$conns = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue; if ($$conns) { $$conns | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $$_ -Force -ErrorAction SilentlyContinue }; Write-Host 'Native frontend stopped.' }; Write-Host 'TenderFlow services stopped.'"

# Seed Admin User
seed:
	docker compose -f ai_rfp_excel/docker-compose.yml exec api python -m ai_rfp_excel.scripts.seed_admin

# Environment & Dependencies
install:
	pip install -r ai_rfp_excel/requirements.txt

dev:
	pip install -r ai_rfp_excel/requirements.txt
	pip install ruff mypy pytest pytest-asyncio pytest-cov httpx

# Testing & Quality
test:
	python -m pytest ai_rfp_excel/tests/ -v

test-cov:
	python -m pytest ai_rfp_excel/tests/ -v --cov=ai_rfp_excel/app --cov-report=term-missing

lint:
	python -m ruff check ai_rfp_excel --ignore E501

lint-fix:
	python -m ruff check ai_rfp_excel --ignore E501 --fix

typecheck:
	python -m mypy ai_rfp_excel --ignore-missing-imports --explicit-package-bases

check: lint typecheck
	@echo All checks passed!

# Docker Services
docker-up:
	docker-compose -f ai_rfp_excel/docker-compose.yml up -d

docker-down:
	docker-compose -f ai_rfp_excel/docker-compose.yml down

docker-logs:
	docker-compose -f ai_rfp_excel/docker-compose.yml logs -f

# Database Migrations
migrate:
	python -m alembic -c ai_rfp_excel/alembic.ini upgrade head

migrate-new:
	python -m alembic -c ai_rfp_excel/alembic.ini revision --autogenerate -m "$(msg)"

clean:
	for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
	for /r . %%f in (*.pyc) do @if exist "%%f" del /q "%%f"
