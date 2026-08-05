# RelayFlow — Distributed Workflow Orchestration Platform

RelayFlow is a production-style workflow engine and operations dashboard inspired by Temporal, Airflow and GitHub Actions. It executes dependency graphs across multiple workers while preserving durable state, retry history and live operational visibility.

## What is real

- RabbitMQ durable task delivery and dead-letter queue
- PostgreSQL workflow, run, task, attempt, event and DLQ persistence
- Redis distributed trigger locks and expiring worker heartbeats
- DAG validation, dependency scheduling and failure propagation
- Atomic worker claims using `FOR UPDATE SKIP LOCKED`
- Worker crash recovery through expiring PostgreSQL leases
- Idempotent workflow triggers and task uniqueness constraints
- Exponential retry backoff and permanent-failure records
- JWT access/refresh tokens with Admin, Developer and Viewer RBAC
- REST APIs, SSE execution events and Prometheus metrics
- Next.js dashboard using real backend metrics/runs with an offline demo fallback
- Automated tests and GitHub Actions for backend, frontend and Docker

## Run locally

### 1. Start the orchestration stack

```powershell
cd backend
docker compose up --build
```

Services:

- API and Swagger: http://localhost:8000/docs
- Prometheus metrics: http://localhost:8000/metrics
- RabbitMQ management: http://localhost:15672 (`guest` / `guest`)
- PostgreSQL, Redis and two worker replicas run inside Docker.

Default development login:

```text
admin@relayflow.local
relayflow-admin
```

Set `RELAYFLOW_JWT_SECRET`, `RELAYFLOW_ADMIN_EMAIL` and `RELAYFLOW_ADMIN_PASSWORD` before any public deployment.

### 2. Start the dashboard in a second terminal

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. The “Backend connected” indicator confirms that dashboard KPIs, queue depth, runs and worker health are coming from RelayFlow APIs.

## Test

```powershell
cd backend
python -m pip install -e ".[dev]"
pytest -q
ruff check relayflow tests
```

```powershell
cd frontend
npm install
npm run build
```

## Interview discussion

The design intentionally uses at-least-once message delivery with PostgreSQL as the authority. RabbitMQ wakes workers, but a worker cannot execute unless it atomically owns the task row. If a worker dies, its lease expires and another worker safely reclaims the task. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for failure semantics, security and the million-job scaling plan.

## Repository structure

- `backend/relayflow` — API, scheduler, broker, coordination, workers and executors
- `backend/tests` — DAG, idempotency, RBAC, worker and DLQ tests
- `frontend/app` — Next.js operations dashboard and workflow builder
- `docs` — architecture and scaling rationale
- `.github/workflows` — CI pipeline
