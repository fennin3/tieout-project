MANAGE = docker compose run --rm app python manage.py
ACCOUNT = NGB-USD-01
AS_OF = 2026-11-02

.PHONY: up migrate test load recon report reset

up:
	docker compose up -d db

migrate:
	$(MANAGE) migrate

test:
	docker compose run --rm app pytest

load:
	$(MANAGE) create_account --code $(ACCOUNT) --name "Northgate Bank USD nostro" --currency USD
	$(MANAGE) load_statement data/statement_$(AS_OF).mt940 --account $(ACCOUNT)
	$(MANAGE) load_ledger data/ledger_$(AS_OF).csv --account $(ACCOUNT)

recon:
	$(MANAGE) run_recon --account $(ACCOUNT) --as-of $(AS_OF)

report:
	$(MANAGE) recon_report --account $(ACCOUNT) --as-of $(AS_OF)

reset:
	docker compose down -v
