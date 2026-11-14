import uuid
from datetime import datetime, UTC
from typing import Any
from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(UTC).isoformat()


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str | None] = mapped_column(nullable=True, index=True)
    repository: Mapped[str]
    task: Mapped[str] = mapped_column(Text)
    policy: Mapped[str]
    mode: Mapped[str]
    fixture: Mapped[str]
    max_budget: Mapped[float]
    max_repairs: Mapped[int]
    max_tool_calls: Mapped[int]
    max_seconds: Mapped[int]
    status: Mapped[str] = mapped_column(default="CREATED", index=True)
    created_at: Mapped[str] = mapped_column(default=now)
    started_at: Mapped[str | None] = mapped_column(nullable=True)
    ended_at: Mapped[str | None] = mapped_column(nullable=True)
    base_commit: Mapped[str | None] = mapped_column(nullable=True)
    patch_hash: Mapped[str | None] = mapped_column(nullable=True)
    security_hash: Mapped[str | None] = mapped_column(nullable=True)
    test_hash: Mapped[str | None] = mapped_column(nullable=True)
    retries: Mapped[int] = mapped_column(default=0)
    tool_calls: Mapped[int] = mapped_column(default=0)
    cost: Mapped[float] = mapped_column(default=0)
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    cancel_requested: Mapped[bool] = mapped_column(default=False)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    state: Mapped[str]
    timestamp: Mapped[str] = mapped_column(default=now)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Invocation(Base):
    __tablename__ = "invocations"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    role: Mapped[str]
    model: Mapped[str]
    tier: Mapped[str]
    routing_reason: Mapped[str]
    context_tokens: Mapped[int]
    input_tokens: Mapped[int | None] = mapped_column(nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(nullable=True)
    cost: Mapped[float | None] = mapped_column(nullable=True)
    usage_source: Mapped[str]
    latency_ms: Mapped[float]
    attempt: Mapped[int]
    success: Mapped[bool]
    failure_class: Mapped[str | None] = mapped_column(nullable=True)


class Artifact(Base):
    __tablename__ = "artifacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    kind: Mapped[str]
    patch_hash: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[str] = mapped_column(default=now)
    content: Mapped[Any] = mapped_column(JSON)
