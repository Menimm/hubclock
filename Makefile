.PHONY: backend-setup frontend-setup backend-run frontend-run db-init db-test clean

backend-setup:
	./scripts/setup_backend.sh

frontend-setup:
	./scripts/setup_frontend.sh

backend-run:
	./scripts/start_backend.sh

frontend-run:
	./scripts/start_frontend.sh

db-init:
	curl -sS -X POST http://127.0.0.1:8000/db/init | jq .

db-test:
	curl -sS http://127.0.0.1:8000/db/test | jq .

clean:
	rm -rf backend/.venv frontend/node_modules
