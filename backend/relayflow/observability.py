from prometheus_client import Counter, Gauge, Histogram

TASKS_STARTED = Counter("relayflow_tasks_started_total", "Task attempts started")
TASKS_COMPLETED = Counter("relayflow_tasks_completed_total", "Tasks completed", ["status"])
TASK_DURATION = Histogram("relayflow_task_duration_seconds", "Task attempt duration")
QUEUE_DEPTH = Gauge("relayflow_queue_depth", "Tasks waiting by state", ["state"])
WORKERS_ONLINE = Gauge("relayflow_workers_online", "Workers with a live Redis heartbeat")
