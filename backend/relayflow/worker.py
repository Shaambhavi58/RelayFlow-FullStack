import asyncio
import json
from datetime import timedelta

import aio_pika
from sqlalchemy import or_, select

from .config import settings
from .coordination import heartbeat
from .database import Base, SessionLocal, engine
from .executors import execute
from .models import RunStatus, TaskAttempt, TaskRun, TaskStatus, WorkflowRun, utcnow
from .observability import TASK_DURATION, TASKS_COMPLETED, TASKS_STARTED
from .orchestrator import advance_run, emit, retry_task


def claim_task(requested_task_id: str | None = None):
    with SessionLocal() as db:
        now = utcnow()
        stmt = (
            select(TaskRun)
            .join(WorkflowRun)
            .where(
                WorkflowRun.status == RunStatus.RUNNING,
                TaskRun.available_at <= now,
                or_(
                    TaskRun.status.in_([TaskStatus.READY, TaskStatus.RETRYING]),
                    (TaskRun.status == TaskStatus.RUNNING) & (TaskRun.lease_expires_at < now),
                ),
            )
            .order_by(TaskRun.available_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if requested_task_id:
            stmt = stmt.where(TaskRun.id == requested_task_id)
        task = db.scalar(stmt)
        if not task:
            return None
        task.status = TaskStatus.RUNNING
        task.attempt += 1
        task.started_at = task.started_at or now
        task.lease_owner = settings.worker_id
        task.lease_expires_at = now + timedelta(seconds=settings.lease_seconds)
        db.add(
            TaskAttempt(
                task_run_id=task.id,
                attempt=task.attempt,
                worker_id=settings.worker_id,
                status="running",
                started_at=now,
            )
        )
        emit(db, task.run_id, "task.started", {"task": task.task_key, "attempt": task.attempt})
        db.commit()
        db.refresh(task)
        return task.id


async def process(task_id: str):
    with SessionLocal() as db:
        task = db.get(TaskRun, task_id)
        run = db.get(WorkflowRun, task.run_id)
        siblings = list(db.scalars(select(TaskRun).where(TaskRun.run_id == task.run_id)))
        context = {
            "input": run.input,
            "tasks": {item.task_key: item.output for item in siblings},
            "task": {"id": task.id, "run_id": task.run_id, "key": task.task_key},
        }
        backoff = int(task.config.get("_backoff_seconds", 2))
        attempt = db.scalar(
            select(TaskAttempt).where(
                TaskAttempt.task_run_id == task.id, TaskAttempt.attempt == task.attempt
            )
        )
        TASKS_STARTED.inc()
        started = asyncio.get_running_loop().time()
        try:
            result = await execute(task.task_type, task.config, context)
            task.output = result
            task.status = TaskStatus.SUCCEEDED
            task.completed_at = utcnow()
            task.lease_owner = None
            task.lease_expires_at = None
            if attempt:
                attempt.status = "succeeded"
                attempt.completed_at = utcnow()
            emit(db, task.run_id, "task.succeeded", {"task": task.task_key, "output": result})
            db.commit()
            TASKS_COMPLETED.labels(status="succeeded").inc()
            advance_run(db, task.run_id)
        except Exception as exc:
            if attempt:
                attempt.status = "failed"
                attempt.error = str(exc)[:4000]
                attempt.completed_at = utcnow()
                db.commit()
            TASKS_COMPLETED.labels(status="failed").inc()
            retry_task(db, task, str(exc), backoff)
        finally:
            TASK_DURATION.observe(asyncio.get_running_loop().time() - started)


async def heartbeat_loop():
    while True:
        heartbeat(
            settings.worker_id,
            {"id": settings.worker_id, "status": "healthy", "runtime": "python-3.12", "seen_at": utcnow().isoformat()},
        )
        await asyncio.sleep(max(2, settings.heartbeat_ttl_seconds // 3))


async def consume_broker():
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    exchange = await channel.declare_exchange("relayflow.dlx", aio_pika.ExchangeType.DIRECT, durable=True)
    dead = await channel.declare_queue(settings.dead_letter_queue, durable=True)
    await dead.bind(exchange, routing_key=settings.dead_letter_queue)
    queue = await channel.declare_queue(
        settings.queue_name,
        durable=True,
        arguments={
            "x-dead-letter-exchange": "relayflow.dlx",
            "x-dead-letter-routing-key": settings.dead_letter_queue,
        },
    )
    async with queue.iterator() as messages:
        async for message in messages:
            async with message.process(requeue=False):
                body = json.loads(message.body)
                task_id = await asyncio.to_thread(claim_task, body["task_id"])
                if task_id:
                    await process(task_id)


async def worker_loop():
    Base.metadata.create_all(engine)
    asyncio.create_task(heartbeat_loop())
    if settings.broker_enabled:
        asyncio.create_task(consume_broker())
    while True:
        task_id = await asyncio.to_thread(claim_task)
        if task_id:
            await process(task_id)
        else:
            await asyncio.sleep(settings.poll_interval_seconds)


def run():
    asyncio.run(worker_loop())


if __name__ == "__main__":
    run()
