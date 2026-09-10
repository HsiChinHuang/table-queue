.PHONY: setup dev backend frontend seed test test-backend test-frontend lint format

setup:
	python3 -m venv backend/.venv
	backend/.venv/bin/python -m pip install -e backend
	cd frontend && npm install

dev:
	@echo "Running development servers..."
	cd backend && ../.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 &
	cd frontend && npm run dev

backend:
	cd backend && ../.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0

frontend:
	cd frontend && npm run dev

seed:
	cd backend && ../.venv/bin/python -m app.seed --reset

test: test-backend test-frontend

test-backend:
	cd backend && ../.venv/bin/python -m pytest

test-frontend:
	cd frontend && npm run test

lint:
	cd frontend && npm run lint

format:
	cd frontend && npm run format
