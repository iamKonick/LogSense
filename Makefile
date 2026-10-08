.PHONY: up down logs test test-live format
up:
	docker compose up -d --build
down:
	docker compose down
logs:
	docker compose logs -f --tail 50 api classifier knowledge-worker
test:
	python -m pytest -q
test-live:
	docker compose exec -T -e LOGSENSE_TEST_LIVE=1 api python -m pytest tests -q -p no:cacheprovider
format:
	ruff format backend experiments scripts
	cd frontend && npm run format
