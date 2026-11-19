# Docker Compose workflow for the LiveKit session archive.
# Needs Docker, and a repo-root env file with B2 and LiveKit values
# (copy .env.example). The web UI runs on the host: `make web`.

COMPOSE ?= docker compose
RUN_ID ?= $(shell date -u +%Y%m%d%H%M%S)

.PHONY: up down logs demo test retention retention-apply web

up: ## Build and start redis, livekit, egress, agent and api; wait until healthy
	$(COMPOSE) up -d --build --wait

down: ## Stop the stack
	$(COMPOSE) down

logs: ## Follow every service's logs
	$(COMPOSE) logs -f --tail=100

demo: ## Record one scripted session to B2 and print its manifest
	$(COMPOSE) exec api python -m live_tests.demo

test: ## Live end-to-end suite against B2, isolated under e2e/<run-id>/
	ARCHIVE_PREFIX=e2e/$(RUN_ID)/ $(COMPOSE) up -d --build --wait
	$(COMPOSE) exec -e RUN_LIVE_SESSION_TESTS=1 api \
		python -m pytest live_tests/test_session_archive_e2e.py -m live -v -p no:cacheprovider; \
	status=$$?; \
	$(COMPOSE) up -d --wait api; \
	exit $$status

retention: ## Dry-run retention as of today (AS_OF=YYYY-MM-DD to pick a date)
	$(COMPOSE) exec api python -m app.jobs.retention $(if $(AS_OF),--as-of $(AS_OF),)

retention-apply: ## Apply retention: delete expired media, write reports/<date>.json
	$(COMPOSE) exec api python -m app.jobs.retention --apply $(if $(AS_OF),--as-of $(AS_OF),)

web: ## Run the Next.js UI on the host against the api container
	NEXT_PUBLIC_API_URL=http://localhost:8000 pnpm dev:web
