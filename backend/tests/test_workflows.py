import asyncio
import os

os.environ["RELAYFLOW_DATABASE_URL"] = "sqlite:///./test_relayflow.db"

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from relayflow.database import Base, SessionLocal, engine
from relayflow.main import app
from relayflow.models import DeadLetterTask, TaskRun, TaskStatus
from relayflow.security import bootstrap_admin
from relayflow.worker import claim_task, process

client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        bootstrap_admin(db)


def auth_headers(email="admin@relayflow.local", password="relayflow-admin"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def workflow_body():
    return {
        "name": "order-pipeline",
        "description": "Validates and notifies",
        "tasks": [
            {"key": "validate", "type": "transform", "config": {"value": "ok"}},
            {
                "key": "notify",
                "type": "delay",
                "depends_on": ["validate"],
                "config": {"seconds": 0},
            },
        ],
    }


def test_create_and_trigger_dag():
    headers = auth_headers()
    created = client.post("/api/v1/workflows", json=workflow_body(), headers=headers)
    assert created.status_code == 201
    workflow_id = created.json()["id"]
    run = client.post(
        f"/api/v1/workflows/{workflow_id}/runs",
        json={"input": {"order_id": 42}},
        headers={**headers, "Idempotency-Key": "order-42"},
    )
    assert run.status_code == 202
    details = client.get(f"/api/v1/runs/{run.json()['id']}", headers=headers).json()
    assert [task["status"] for task in details["tasks"]] == ["blocked", "ready"]


def test_rejects_cycle():
    body = workflow_body()
    body["name"] = "cyclic"
    body["tasks"][0]["depends_on"] = ["notify"]
    response = client.post("/api/v1/workflows", json=body, headers=auth_headers())
    assert response.status_code == 422


def test_idempotent_trigger_returns_same_run():
    headers = auth_headers()
    workflow_id = client.post("/api/v1/workflows", json=workflow_body(), headers=headers).json()["id"]
    url = f"/api/v1/workflows/{workflow_id}/runs"
    first = client.post(url, json={"input": {}}, headers={**headers, "Idempotency-Key": "same"})
    second = client.post(url, json={"input": {}}, headers={**headers, "Idempotency-Key": "same"})
    assert first.json()["id"] == second.json()["id"]
    assert second.status_code == 200


def test_viewer_cannot_create_workflow():
    admin = auth_headers()
    created = client.post(
        "/api/v1/users",
        json={"email": "viewer@relayflow.local", "password": "viewer-password", "role": "viewer"},
        headers=admin,
    )
    assert created.status_code == 201
    viewer = auth_headers("viewer@relayflow.local", "viewer-password")
    assert client.get("/api/v1/workflows", headers=viewer).status_code == 200
    assert client.post("/api/v1/workflows", json=workflow_body(), headers=viewer).status_code == 403


def test_dashboard_reports_real_queue_depth():
    headers = auth_headers()
    workflow_id = client.post("/api/v1/workflows", json=workflow_body(), headers=headers).json()["id"]
    client.post(f"/api/v1/workflows/{workflow_id}/runs", json={"input": {}}, headers=headers)
    dashboard = client.get("/api/v1/dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["queue"]["pending"] == 2


def test_worker_advances_dag_after_success():
    headers = auth_headers()
    workflow_id = client.post("/api/v1/workflows", json=workflow_body(), headers=headers).json()["id"]
    run_id = client.post(f"/api/v1/workflows/{workflow_id}/runs", json={"input": {}}, headers=headers).json()["id"]
    task_id = claim_task()
    asyncio.run(process(task_id))
    with SessionLocal() as db:
        tasks = db.scalars(select(TaskRun).where(TaskRun.run_id == run_id).order_by(TaskRun.task_key)).all()
        assert [task.status for task in tasks] == [TaskStatus.READY, TaskStatus.SUCCEEDED]


def test_permanent_failure_is_written_to_dead_letter_table():
    headers = auth_headers()
    workflow_id = client.post("/api/v1/workflows", json=workflow_body(), headers=headers).json()["id"]
    client.post(f"/api/v1/workflows/{workflow_id}/runs", json={"input": {}}, headers=headers)
    with SessionLocal() as db:
        task = db.scalar(select(TaskRun).where(TaskRun.status == TaskStatus.READY))
        task.task_type = "unsupported"
        task.max_attempts = 1
        db.commit()
    asyncio.run(process(claim_task()))
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(DeadLetterTask)) == 1
