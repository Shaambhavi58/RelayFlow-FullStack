import asyncio
import re
from typing import Any

import httpx

TOKEN = re.compile(r"\{\{\s*([^}]+)\s*\}\}")


def resolve(value: Any, context: dict):
    if isinstance(value, dict):
        return {key: resolve(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve(item, context) for item in value]
    if not isinstance(value, str):
        return value

    def replace(match):
        current: Any = context
        for part in match.group(1).strip().split("."):
            current = current[part]
        return str(current)

    return TOKEN.sub(replace, value)


async def execute(task_type: str, config: dict, context: dict) -> dict:
    config = resolve(config, context)
    if task_type == "delay":
        seconds = min(float(config.get("seconds", 1)), 3600)
        await asyncio.sleep(seconds)
        return {"waited_seconds": seconds}
    if task_type == "transform":
        return {"value": config.get("value")}
    if task_type == "http":
        headers = {"Idempotency-Key": context["task"]["id"], **(config.get("headers") or {})}
        async with httpx.AsyncClient(timeout=float(config.get("timeout", 30))) as client:
            response = await client.request(
                config.get("method", "GET"),
                config["url"],
                headers=headers,
                json=config.get("body"),
            )
            response.raise_for_status()
            try:
                body = response.json()
            except ValueError:
                body = response.text
            return {"status_code": response.status_code, "body": body}
    raise ValueError(f"Unsupported task type: {task_type}")
