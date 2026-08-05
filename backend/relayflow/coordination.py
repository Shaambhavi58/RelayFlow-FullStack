import json
from contextlib import contextmanager

from redis import Redis
from redis.exceptions import RedisError

from .config import settings


def client() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=2)


@contextmanager
def distributed_lock(name: str, timeout: int = 10):
    lock = None
    acquired = True
    try:
        lock = client().lock(f"relayflow:lock:{name}", timeout=timeout, blocking_timeout=2)
        acquired = lock.acquire(blocking=True)
    except RedisError:
        # PostgreSQL constraints and row locks remain the correctness fallback.
        acquired = True
    try:
        yield acquired
    finally:
        if lock and acquired:
            try:
                lock.release()
            except RedisError:
                pass


def heartbeat(worker_id: str, payload: dict) -> None:
    try:
        client().setex(
            f"relayflow:worker:{worker_id}",
            settings.heartbeat_ttl_seconds,
            json.dumps(payload),
        )
    except RedisError:
        pass


def live_workers() -> list[dict]:
    try:
        redis = client()
        result = []
        for key in redis.scan_iter("relayflow:worker:*"):
            value = redis.get(key)
            if value:
                result.append(json.loads(value))
        return result
    except (RedisError, json.JSONDecodeError):
        return []
