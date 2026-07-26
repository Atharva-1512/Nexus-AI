# =============================================================
# NEXUS AI — Makefile
# Common development commands — run from the project root
# Usage: make <target>
# =============================================================

.PHONY: help install dev up down logs test lint format clean

# ─── Variables ────────────────────────────────────────────────
BACKEND_DIR  := ./backend
FRONTEND_DIR := ./frontend
PYTHON       := python
PYTEST       := pytest
RUFF         := ruff
NPM          := npm

# Default target
help: ## Show this help message
	@echo ""
	@echo "  ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗     █████╗ ██╗"
	@echo "  ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝    ██╔══██╗██║"
	@echo "  ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗    ███████║██║"
	@echo "  ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║    ██╔══██║██║"
	@echo "  ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║    ██║  ██║██║"
	@echo "  ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝    ╚═╝  ╚═╝╚═╝"
	@echo ""
	@echo "  NIFTY Expert eXecution & Understanding System"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ─── Setup ────────────────────────────────────────────────────
install: ## Install all dependencies (backend + frontend)
	@echo "📦 Installing backend dependencies..."
	cd $(BACKEND_DIR) && pip install -r requirements.txt
	@echo "📦 Installing frontend dependencies..."
	cd $(FRONTEND_DIR) && $(NPM) install
	@echo "✅ All dependencies installed."

install-backend: ## Install backend Python dependencies only
	cd $(BACKEND_DIR) && pip install -r requirements.txt

install-frontend: ## Install frontend Node.js dependencies only
	cd $(FRONTEND_DIR) && $(NPM) install

setup-env: ## Copy .env.example to .env (run once)
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✅ .env created from .env.example — fill in your values."; \
	else \
		echo "⚠️  .env already exists. Not overwriting."; \
	fi

# ─── Development ──────────────────────────────────────────────
dev-backend: ## Start FastAPI backend with hot reload
	cd $(BACKEND_DIR) && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

dev-frontend: ## Start Next.js frontend dev server
	cd $(FRONTEND_DIR) && $(NPM) run dev

dev: ## Start all services with Docker Compose (recommended)
	docker compose up -d postgres redis mongodb zookeeper kafka
	@echo "⏳ Waiting for services to be healthy..."
	@sleep 10
	@echo "🚀 Starting backend and frontend..."
	docker compose up -d backend frontend
	@echo "✅ NEXUS AI is running!"
	@echo "   Frontend  : http://localhost:3000"
	@echo "   Backend   : http://localhost:8000"
	@echo "   API Docs  : http://localhost:8000/api/docs"
	@echo "   Kafka UI  : (run: make kafka-ui)"

# ─── Docker ───────────────────────────────────────────────────
up: ## Start all Docker services
	docker compose up -d

up-infra: ## Start only infrastructure (DB, Redis, Kafka)
	docker compose up -d postgres redis mongodb zookeeper kafka

down: ## Stop all Docker services
	docker compose down

down-volumes: ## Stop all Docker services AND delete volumes (⚠️ DATA LOSS)
	docker compose down -v

logs: ## Tail logs for all services
	docker compose logs -f

logs-backend: ## Tail backend logs only
	docker compose logs -f backend

logs-frontend: ## Tail frontend logs only
	docker compose logs -f frontend

kafka-ui: ## Start Kafka UI (dev tool)
	docker compose --profile dev-tools up -d kafka-ui
	@echo "📊 Kafka UI: http://localhost:8080"

restart-backend: ## Restart backend container
	docker compose restart backend

build: ## Rebuild all Docker images
	docker compose build

# ─── Testing ──────────────────────────────────────────────────
test: ## Run all backend tests
	cd $(BACKEND_DIR) && $(PYTEST) tests/ -v --tb=short

test-cov: ## Run tests with coverage report
	cd $(BACKEND_DIR) && $(PYTEST) tests/ -v --cov=app --cov=modules --cov-report=term-missing --cov-report=html

test-bs: ## Run Black-Scholes pricer tests only
	cd $(BACKEND_DIR) && $(PYTEST) tests/test_phase1.py::TestBlackScholesPricer -v

test-api: ## Run API endpoint tests only
	cd $(BACKEND_DIR) && $(PYTEST) tests/test_phase1.py::TestHealthEndpoints tests/test_phase1.py::TestSignalEndpoints -v

test-frontend: ## Run frontend tests
	cd $(FRONTEND_DIR) && $(NPM) test

# ─── Code Quality ─────────────────────────────────────────────
lint: ## Lint backend Python code with Ruff
	cd $(BACKEND_DIR) && $(RUFF) check . --select=ALL --ignore=D,ANN
	cd $(BACKEND_DIR) && python -m mypy app/ --ignore-missing-imports

format: ## Auto-format backend Python code with Ruff
	cd $(BACKEND_DIR) && $(RUFF) format .
	cd $(BACKEND_DIR) && $(RUFF) check . --fix

lint-frontend: ## Lint frontend TypeScript code
	cd $(FRONTEND_DIR) && $(NPM) run lint

# ─── Database ─────────────────────────────────────────────────
db-migrate: ## Run Alembic database migrations
	cd $(BACKEND_DIR) && alembic upgrade head

db-migrate-new: ## Create a new migration (usage: make db-migrate-new MSG="add table")
	cd $(BACKEND_DIR) && alembic revision --autogenerate -m "$(MSG)"

db-rollback: ## Rollback last migration
	cd $(BACKEND_DIR) && alembic downgrade -1

db-shell: ## Open PostgreSQL shell
	docker compose exec postgres psql -U nexus -d nexus_ai

redis-cli: ## Open Redis CLI
	docker compose exec redis redis-cli

# ─── Utilities ────────────────────────────────────────────────
clean: ## Remove Python cache files and build artifacts
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -name ".coverage" -delete 2>/dev/null || true
	@echo "✅ Cleaned."

status: ## Show status of all Docker services
	docker compose ps

health: ## Check backend health endpoint
	@curl -s http://localhost:8000/api/v1/health/ | python -m json.tool
