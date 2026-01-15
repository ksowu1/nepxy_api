.PHONY: up down logs fmt lint test migrate migrate-check smoke release-check

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

fmt:
	@echo "fmt: no-op (no formatter configured)"

lint:
	@echo "lint: no-op (no linter configured)"

test:
	python -m pytest -q

migrate:
	alembic upgrade head

migrate-check:
	python -c "import subprocess, sys; out = subprocess.check_output(['alembic','heads','--verbose']).decode('utf-8','ignore'); sys.exit(1) if out.count('Rev:') > 1 else 0"

smoke:
	python scripts/smoke_dev.py

release-check: test migrate-check smoke
