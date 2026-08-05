from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./relayflow.db"
    worker_id: str = "worker-local"
    poll_interval_seconds: float = 1.0
    lease_seconds: int = 30
    cors_origins: str = "http://localhost:3000"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    redis_url: str = "redis://localhost:6379/0"
    broker_enabled: bool = False
    queue_name: str = "relayflow.tasks"
    dead_letter_queue: str = "relayflow.tasks.dlq"
    heartbeat_ttl_seconds: int = 20
    jwt_secret: str = "change-me-in-production-32-bytes-minimum"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    bootstrap_admin_email: str = "admin@relayflow.local"
    bootstrap_admin_password: str = "relayflow-admin"

    model_config = SettingsConfigDict(env_prefix="RELAYFLOW_", env_file=".env")


settings = Settings()
