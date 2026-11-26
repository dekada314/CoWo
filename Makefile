ifneq ($(wildcard .env),)
    include .env
    export
endif
up:
	docker compose up --build

down:
	docker compose down

migrate:
	docker compose run --rm migrate

test:
	uv run pytest

lint:
	uv run ruff check .

db:
	docker compose exec postgres psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)
