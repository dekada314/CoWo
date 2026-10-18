ifneq ($(wildcard .env),)
    include .env
    export
endif
up:
	docker compose up

db:
	docker exec -it db psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)