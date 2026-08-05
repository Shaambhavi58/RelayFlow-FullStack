import json

import pika
from pika.exceptions import AMQPError

from .config import settings


def _channel():
    connection = pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
    channel = connection.channel()
    channel.exchange_declare(exchange="relayflow.dlx", exchange_type="direct", durable=True)
    channel.queue_declare(queue=settings.dead_letter_queue, durable=True)
    channel.queue_bind(
        queue=settings.dead_letter_queue,
        exchange="relayflow.dlx",
        routing_key=settings.dead_letter_queue,
    )
    channel.queue_declare(
        queue=settings.queue_name,
        durable=True,
        arguments={
            "x-dead-letter-exchange": "relayflow.dlx",
            "x-dead-letter-routing-key": settings.dead_letter_queue,
        },
    )
    return connection, channel


def publish_task(task_id: str, delay_seconds: int = 0) -> bool:
    if not settings.broker_enabled:
        return False
    try:
        connection, channel = _channel()
        channel.basic_publish(
            exchange="",
            routing_key=settings.queue_name,
            body=json.dumps({"task_id": task_id}),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
                headers={"retry_after_seconds": delay_seconds},
            ),
        )
        connection.close()
        return True
    except AMQPError:
        return False


def publish_dead_letter(task_id: str, run_id: str, reason: str) -> bool:
    if not settings.broker_enabled:
        return False
    try:
        connection, channel = _channel()
        channel.basic_publish(
            exchange="relayflow.dlx",
            routing_key=settings.dead_letter_queue,
            body=json.dumps({"task_id": task_id, "run_id": run_id, "reason": reason}),
            properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
        )
        connection.close()
        return True
    except AMQPError:
        return False
