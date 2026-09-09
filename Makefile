.PHONY: setup start stop status logs verify tools

setup:
	docker compose build

start:
	docker compose up -d

stop:
	docker compose down

status:
	docker compose ps

logs:
	docker compose logs -f

verify:
	./scripts/verify-setup.sh

tools:
	docker compose --profile tools up -d

