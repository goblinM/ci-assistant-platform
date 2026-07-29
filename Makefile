.PHONY: setup test run dev migrate compose-up compose-down eval eval-rag eval-ranking docker-build docker-run

APP_PORT ?= 8080
IMAGE_NAME ?= ai-ci-assistant

setup:
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example"; fi
	pip install -e ".[dev]"

test:
	pytest

migrate:
	alembic upgrade head

compose-up:
	docker compose up --build

compose-down:
	docker compose down

run:
	uvicorn ci_assistant.main:app --host 0.0.0.0 --port $(APP_PORT)

dev:
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example, please fill LLM settings if needed."; fi
	uvicorn ci_assistant.main:app --reload --host 0.0.0.0 --port $(APP_PORT)

eval:
	python -m ci_analysis_demo.scripts.evaluate_ci_assistant

eval-rag:
	python -c "import asyncio; from ci_analysis_demo.scripts.evaluate_ci_assistant import main; asyncio.run(main(True))"

eval-ranking:
	python -m ci_assistant.scripts.evaluate_ranking

docker-build:
	docker build -t $(IMAGE_NAME) .

docker-run:
	docker run --env-file .env -p $(APP_PORT):8080 $(IMAGE_NAME)
