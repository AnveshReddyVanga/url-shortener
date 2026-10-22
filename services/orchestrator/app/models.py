from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class WorkflowRequest(BaseModel):
    scenario: Literal["greenfield", "brownfield", "ambiguous"]
    requirement: str = Field(min_length=8, max_length=8000)


class ApprovalRequest(BaseModel):
    approved_by: str = Field(min_length=3, max_length=200)
    comment: str = Field(min_length=3, max_length=2000)


class Task(BaseModel):
    id: str
    name: str
    dependencies: list[str] = Field(default_factory=list)
    status: str = "pending"
    attempts: int = 0
    max_attempts: int = 2
    artifact: Any = None
    error: str | None = None


class AuditEvent(BaseModel):
    at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event: str
    task_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class Workflow(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    scenario: str
    requirement: str
    status: str = "running"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    tasks: dict[str, Task]
    artifacts: dict[str, Any] = Field(default_factory=dict)
    audit: list[AuditEvent] = Field(default_factory=list)
    release_approved: bool = False
    approved_by: str | None = None
    approval_comment: str | None = None
    clarification_questions: list[str] = Field(default_factory=list)
    code_change_proposal: dict[str, Any] | None = None
    implementation_execution: dict[str, Any] | None = None


class CodeChangeProposalRequest(BaseModel):
    instructions: str | None = Field(default=None, max_length=8000)


class ApplyCodeChangesRequest(BaseModel):
    approved_by: str = Field(min_length=3, max_length=200)
    comment: str = Field(min_length=3, max_length=2000)