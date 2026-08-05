from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .broker import publish_dead_letter, publish_task
from .coordination import distributed_lock
from .models import (
    DeadLetterTask,
    RunEvent,
    RunStatus,
    TaskRun,
    TaskStatus,
    Workflow,
    WorkflowRun,
    utcnow,
)
from .schemas import WorkflowCreate


def emit(db: Session, run_id: str, event_type: str, payload: dict):
    db.add(RunEvent(run_id=run_id, event_type=event_type, payload=payload))


def create_workflow(db: Session, data: WorkflowCreate) -> Workflow:
    workflow = Workflow(
        name=data.name,
        description=data.description,
        definition=data.model_dump(mode="json"),
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return workflow


def start_run(db: Session, workflow: Workflow, payload: dict, idempotency_key: str | None):
    with distributed_lock(f"trigger:{workflow.id}:{idempotency_key or 'none'}") as acquired:
        if not acquired:
            raise RuntimeError("Could not acquire workflow trigger lock")
        if idempotency_key:
            existing = db.scalar(
                select(WorkflowRun).where(
                    WorkflowRun.workflow_id == workflow.id,
                    WorkflowRun.idempotency_key == idempotency_key,
                )
            )
            if existing:
                return existing, False

    run = WorkflowRun(
        workflow_id=workflow.id,
        status=RunStatus.RUNNING,
        input=payload,
        idempotency_key=idempotency_key,
        started_at=utcnow(),
    )
    db.add(run)
    db.flush()
    for task in workflow.definition["tasks"]:
        db.add(
            TaskRun(
                run_id=run.id,
                task_key=task["key"],
                task_type=task["type"],
                config={**task["config"], "_backoff_seconds": task["retry"]["backoff_seconds"]},
                dependencies=task["depends_on"],
                max_attempts=task["retry"]["max_attempts"],
                status=TaskStatus.READY if not task["depends_on"] else TaskStatus.BLOCKED,
            )
        )
    emit(db, run.id, "run.started", {"workflow_id": workflow.id})
    db.commit()
    db.refresh(run)
    ready_ids = db.scalars(
        select(TaskRun.id).where(TaskRun.run_id == run.id, TaskRun.status == TaskStatus.READY)
    ).all()
    for task_id in ready_ids:
        publish_task(task_id)
    return run, True


def advance_run(db: Session, run_id: str):
    run = db.get(WorkflowRun, run_id)
    tasks = list(db.scalars(select(TaskRun).where(TaskRun.run_id == run_id)))
    states = {task.task_key: task.status for task in tasks}

    became_ready = []
    for task in tasks:
        if task.status == TaskStatus.BLOCKED:
            dependency_states = [states[key] for key in task.dependencies]
            if any(s in {TaskStatus.FAILED, TaskStatus.CANCELLED} for s in dependency_states):
                task.status = TaskStatus.CANCELLED
                task.completed_at = utcnow()
                emit(db, run_id, "task.cancelled", {"task": task.task_key, "reason": "dependency"})
            elif all(s == TaskStatus.SUCCEEDED for s in dependency_states):
                task.status = TaskStatus.READY
                became_ready.append(task.id)
                emit(db, run_id, "task.ready", {"task": task.task_key})

    terminal = {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}
    if tasks and all(task.status in terminal for task in tasks):
        if any(task.status == TaskStatus.FAILED for task in tasks):
            run.status = RunStatus.FAILED
        elif run.status == RunStatus.CANCELLED:
            pass
        else:
            run.status = RunStatus.SUCCEEDED
            run.output = {task.task_key: task.output for task in tasks}
        run.completed_at = utcnow()
        emit(db, run_id, f"run.{run.status.value}", {})
    db.commit()
    for task_id in became_ready:
        publish_task(task_id)


def retry_task(db: Session, task: TaskRun, error: str, backoff_seconds: int):
    task.error = error[:4000]
    task.lease_owner = None
    task.lease_expires_at = None
    if task.attempt < task.max_attempts:
        task.status = TaskStatus.RETRYING
        task.available_at = utcnow() + timedelta(
            seconds=backoff_seconds * (2 ** (task.attempt - 1))
        )
        emit(db, task.run_id, "task.retrying", {"task": task.task_key, "attempt": task.attempt})
    else:
        task.status = TaskStatus.FAILED
        task.completed_at = utcnow()
        db.add(
            DeadLetterTask(
                task_run_id=task.id,
                run_id=task.run_id,
                task_key=task.task_key,
                reason=task.error,
                payload={"attempt": task.attempt, "max_attempts": task.max_attempts},
            )
        )
        emit(db, task.run_id, "task.failed", {"task": task.task_key, "error": task.error})
        publish_dead_letter(task.id, task.run_id, task.error)
    db.commit()
    if task.status == TaskStatus.RETRYING:
        publish_task(task.id, max(0, int((task.available_at - utcnow()).total_seconds())))
    advance_run(db, task.run_id)
