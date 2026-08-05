import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import settings
from .coordination import live_workers
from .database import Base, SessionLocal, engine, get_db
from .models import (
    DeadLetterTask,
    RunEvent,
    RunStatus,
    TaskAttempt,
    TaskRun,
    TaskStatus,
    User,
    UserRole,
    Workflow,
    WorkflowRun,
    utcnow,
)
from .observability import QUEUE_DEPTH, WORKERS_ONLINE
from .orchestrator import create_workflow, emit, start_run
from .schemas import LoginRequest, RefreshRequest, RunCreate, UserCreate, WorkflowCreate
from .security import (
    bootstrap_admin,
    create_token,
    hash_password,
    require_roles,
    user_from_refresh_token,
    verify_password,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        bootstrap_admin(db)
    yield


app = FastAPI(
    title="RelayFlow API",
    version="1.0.0",
    description="Production-style durable DAG orchestration with RabbitMQ, Redis and RBAC",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[item.strip() for item in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


def task_json(task: TaskRun):
    return {
        "id": task.id,
        "key": task.task_key,
        "type": task.task_type,
        "status": task.status,
        "attempt": task.attempt,
        "max_attempts": task.max_attempts,
        "dependencies": task.dependencies,
        "output": task.output,
        "error": task.error,
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "relayflow-api"}


@app.post("/api/v1/auth/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return {
        "access_token": create_token(user),
        "refresh_token": create_token(user, "refresh"),
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "role": user.role.value},
    }


@app.post("/api/v1/auth/refresh")
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    user = user_from_refresh_token(body.refresh_token, db)
    return {"access_token": create_token(user), "token_type": "bearer"}


@app.post("/api/v1/users", status_code=201)
def add_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN)),
):
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(409, "User already exists")
    user = User(email=body.email, password_hash=hash_password(body.password), role=UserRole(body.role))
    db.add(user)
    db.commit()
    return {"id": user.id, "email": user.email, "role": user.role.value}


@app.post("/api/v1/workflows", status_code=201)
def add_workflow(
    body: WorkflowCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    try:
        workflow = create_workflow(db, body)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A workflow with this name already exists")
    return {"id": workflow.id, "name": workflow.name, "version": workflow.version}


@app.get("/api/v1/workflows")
def list_workflows(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    rows = db.scalars(select(Workflow).order_by(Workflow.created_at.desc())).all()
    return [
        {"id": row.id, "name": row.name, "description": row.description, "version": row.version}
        for row in rows
    ]


@app.get("/api/v1/workflows/{workflow_id}")
def get_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    workflow = db.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    return {
        "id": workflow.id,
        "name": workflow.name,
        "description": workflow.description,
        **workflow.definition,
    }


@app.post("/api/v1/workflows/{workflow_id}/runs", status_code=202)
def trigger_run(
    workflow_id: str,
    body: RunCreate,
    response: Response,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    workflow = db.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    key = idempotency_key or body.idempotency_key
    run, created = start_run(db, workflow, body.input, key)
    if not created:
        response.status_code = status.HTTP_200_OK
    return {"id": run.id, "status": run.status, "created": created}


@app.get("/api/v1/runs")
def list_runs(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    runs = db.scalars(
        select(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(limit)
    ).all()
    return [
        {"id": r.id, "workflow_id": r.workflow_id, "status": r.status, "created_at": r.created_at}
        for r in runs
    ]


@app.get("/api/v1/runs/{run_id}")
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    run = db.get(WorkflowRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    tasks = db.scalars(
        select(TaskRun).where(TaskRun.run_id == run_id).order_by(TaskRun.task_key)
    ).all()
    return {
        "id": run.id,
        "workflow_id": run.workflow_id,
        "status": run.status,
        "input": run.input,
        "output": run.output,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "tasks": [task_json(task) for task in tasks],
    }


@app.post("/api/v1/runs/{run_id}/cancel")
def cancel_run(
    run_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    run = db.get(WorkflowRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run.status not in {RunStatus.PENDING, RunStatus.RUNNING}:
        raise HTTPException(409, f"Run is already {run.status.value}")
    run.status = RunStatus.CANCELLED
    run.completed_at = utcnow()
    tasks = db.scalars(select(TaskRun).where(TaskRun.run_id == run_id)).all()
    for task in tasks:
        if task.status not in {TaskStatus.SUCCEEDED, TaskStatus.FAILED}:
            task.status = TaskStatus.CANCELLED
            task.completed_at = utcnow()
    emit(db, run_id, "run.cancelled", {})
    db.commit()
    return {"id": run.id, "status": run.status}


@app.get("/api/v1/runs/{run_id}/events")
async def stream_events(
    run_id: str,
    after: int = 0,
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    async def event_source():
        cursor = after
        while True:
            with SessionLocal() as db:
                events = db.scalars(
                    select(RunEvent)
                    .where(RunEvent.run_id == run_id, RunEvent.id > cursor)
                    .order_by(RunEvent.id)
                ).all()
                for event in events:
                    cursor = event.id
                    data = {"id": event.id, "type": event.event_type, "payload": event.payload}
                    yield f"id: {event.id}\nevent: {event.event_type}\ndata: {json.dumps(data)}\n\n"
            yield ": heartbeat\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(event_source(), media_type="text/event-stream")


@app.get("/api/v1/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    status_counts = dict(db.execute(select(WorkflowRun.status, func.count()).group_by(WorkflowRun.status)).all())
    task_counts = dict(db.execute(select(TaskRun.status, func.count()).group_by(TaskRun.status)).all())
    total = sum(status_counts.values())
    succeeded = status_counts.get(RunStatus.SUCCEEDED, 0)
    avg_duration = db.scalar(
        select(func.avg(func.extract("epoch", WorkflowRun.completed_at - WorkflowRun.started_at))).where(
            WorkflowRun.completed_at.is_not(None)
        )
    ) if not settings.database_url.startswith("sqlite") else 0
    worker_rows = live_workers()
    queue = {
        "pending": task_counts.get(TaskStatus.READY, 0) + task_counts.get(TaskStatus.BLOCKED, 0),
        "running": task_counts.get(TaskStatus.RUNNING, 0),
        "retrying": task_counts.get(TaskStatus.RETRYING, 0),
        "dead_letter": db.scalar(select(func.count()).select_from(DeadLetterTask)) or 0,
    }
    for state, value in queue.items():
        QUEUE_DEPTH.labels(state=state).set(value)
    WORKERS_ONLINE.set(len(worker_rows))
    return {
        "runs": {status.value: count for status, count in status_counts.items()},
        "running_workflows": status_counts.get(RunStatus.RUNNING, 0),
        "success_rate": round((succeeded / total * 100) if total else 100, 2),
        "average_execution_seconds": round(float(avg_duration or 0), 2),
        "queue": queue,
        "workers": worker_rows,
    }


@app.get("/api/v1/runs/{run_id}/attempts")
def attempts(
    run_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    rows = db.scalars(
        select(TaskAttempt).join(TaskRun).where(TaskRun.run_id == run_id).order_by(TaskAttempt.id)
    ).all()
    return [
        {"task_run_id": row.task_run_id, "attempt": row.attempt, "worker": row.worker_id, "status": row.status, "error": row.error}
        for row in rows
    ]


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def run():
    import uvicorn

    uvicorn.run("relayflow.main:app", host="0.0.0.0", port=8000)
