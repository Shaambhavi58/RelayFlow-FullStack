from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class RetryPolicy(BaseModel):
    max_attempts: int = Field(3, ge=1, le=20)
    backoff_seconds: int = Field(2, ge=0, le=3600)


class TaskDefinition(BaseModel):
    key: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,119}$")
    type: Literal["http", "delay", "transform"]
    depends_on: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    retry: RetryPolicy = Field(default_factory=RetryPolicy)


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = ""
    tasks: list[TaskDefinition] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_dag(self):
        keys = [task.key for task in self.tasks]
        if len(keys) != len(set(keys)):
            raise ValueError("Task keys must be unique")
        key_set = set(keys)
        for task in self.tasks:
            missing = set(task.depends_on) - key_set
            if missing:
                raise ValueError(f"Task {task.key} has unknown dependencies: {sorted(missing)}")
        visiting, visited = set(), set()
        graph = {task.key: task.depends_on for task in self.tasks}

        def visit(node):
            if node in visiting:
                raise ValueError("Workflow contains a dependency cycle")
            if node in visited:
                return
            visiting.add(node)
            for dependency in graph[node]:
                visit(dependency)
            visiting.remove(node)
            visited.add(node)

        for key in keys:
            visit(key)
        return self


class RunCreate(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=160)


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    role: Literal["admin", "developer", "viewer"] = "viewer"


class RefreshRequest(BaseModel):
    refresh_token: str
