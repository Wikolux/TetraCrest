PIP ?= pip
PYTHON ?= python3

setup:
	$(PYTHON) -m venv .venv
	. .venv/bin/activate && $(PIP) install -r backend/requirements.txt

run:
	cd backend && . ../.venv/bin/activate && uvicorn main:app --reload --host 0.0.0.0 --port 8000

test:
	cd backend && . ../.venv/bin/activate && pytest -q

lint:
	cd backend && . ../.venv/bin/activate && ruff check .

format:
	cd backend && . ../.venv/bin/activate && black .
