from enum import StrEnum
from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict


class State(StrEnum):
    CREATED = "CREATED"
    ANALYZING = "ANALYZING"
    PLANNING = "PLANNING"
    IMPLEMENTING = "IMPLEMENTING"
    SECURITY_REVIEW = "SECURITY_REVIEW"
    TESTING = "TESTING"
    REPAIRING = "REPAIRING"
    FINAL_VERIFICATION = "FINAL_VERIFICATION"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RunCreate(BaseModel):
    repository: str = Field(min_length=1, max_length=1024)
    task: str = Field(min_length=10, max_length=16000)
    policy: Literal["adaptive", "small_only", "large_only"] = "adaptive"
    mode: Literal["scripted", "live"] = "scripted"
    fixture: Literal["demo", "function", "validation", "authorization", "edge", "feature"] = "demo"
    max_budget: float = Field(default=1.0, gt=0, le=100)
    max_repairs: int = Field(default=2, ge=0, le=5)
    max_tool_calls: int = Field(default=80, ge=1, le=500)
    max_seconds: int = Field(default=300, ge=1, le=1800)


class ImplementationPlan(BaseModel):
    summary: str
    affected_files: list[str] = Field(min_length=1)
    steps: list[str] = Field(min_length=1)
    acceptance_criteria: list[str] = Field(min_length=1)
    risks: list[str]
    testing_strategy: str


class Finding(BaseModel):
    severity: Literal["low", "medium", "high", "critical"]
    source: str
    verified: bool
    message: str
    evidence: str
    remediation: str


class AgentOutput(BaseModel):
    summary: str
    findings: list[Finding] = []
    criteria: dict[str, bool] = {}
    recommendation: Literal["review", "reject"] = "review"
    residual_risks: list[str] = []


class RunView(RunCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: State
    created_at: str
    started_at: str | None
    ended_at: str | None
    base_commit: str | None
    patch_hash: str | None
    security_hash: str | None
    test_hash: str | None
    retries: int
    tool_calls: int
    cost: float
    input_tokens: int
    output_tokens: int
    outcome: str | None
    cancel_requested: bool
    organization_id: str | None


class EventView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    run_id: str
    state: str
    timestamp: str
    detail: dict[str, Any]


class InvocationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: str
    model: str
    tier: str
    routing_reason: str
    context_tokens: int
    input_tokens: int | None
    output_tokens: int | None
    cost: float | None
    usage_source: str
    latency_ms: float
    attempt: int
    success: bool
    failure_class: str | None


class ArtifactView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    patch_hash: str | None
    created_at: str
    content: Any
