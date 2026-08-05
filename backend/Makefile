.PHONY: dev api worker test lint demo

dev:
	docker compose up --build

api:
	uvicorn relayflow.main:app --reload

worker:
	python -m relayflow.worker

test:
	pytest -q

lint:
	ruff check .

demo:
	curl -sS -X POST http://localhost:8000/api/v1/workflows \
	  -H 'Content-Type: application/json' --data @examples/order_fulfillment.json

