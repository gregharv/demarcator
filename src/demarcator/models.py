from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class Role(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class ActionMode(StrEnum):
    READ_ONLY = "read_only"
    DRAFT_ONLY = "draft_only"
    APPROVAL_REQUIRED = "approval_required"


class RunStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING_APPROVAL = "pending_approval"
    BLOCKED = "blocked"


class ConnectorHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(slots=True)
class User:
    user_id: str
    name: str
    role: Role

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Connector:
    connector_id: str
    name: str
    health: ConnectorHealth
    last_successful_sync: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Workflow:
    workflow_id: str
    name: str
    description: str
    action_mode: ActionMode
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RequestedSource:
    connector_id: str
    scope: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProposedAction:
    action_type: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.action_type, "summary": self.summary}


@dataclass(slots=True)
class DataScopeRule:
    workflow_id: str
    connector_id: str
    allowed_scopes: list[str] = field(default_factory=list)

    def allows(self, scope: str) -> bool:
        if not self.allowed_scopes:
            return False
        return any(scope == candidate or scope.startswith(f"{candidate}/") for candidate in self.allowed_scopes)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WorkflowGrant:
    user_id: str
    workflow_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ApprovalRequest:
    approval_id: str
    run_id: str
    workflow_id: str
    requested_by: str
    action: ProposedAction
    source_data: list[RequestedSource]
    summary: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    reviewer_id: str | None = None
    note: str | None = None
    created_at: str = field(default_factory=lambda: utc_now().isoformat())
    decided_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "requested_by": self.requested_by,
            "action": self.action.to_dict(),
            "source_data": [item.to_dict() for item in self.source_data],
            "summary": self.summary,
            "status": self.status,
            "reviewer_id": self.reviewer_id,
            "note": self.note,
            "created_at": self.created_at,
            "decided_at": self.decided_at,
        }


@dataclass(slots=True)
class AuditEvent:
    event_id: str
    event_type: str
    timestamp: str
    actor_id: str | None
    run_id: str | None
    workflow_id: str | None
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WorkflowRun:
    run_id: str
    actor_id: str
    workflow_id: str
    correlation_id: str
    requested_sources: list[RequestedSource]
    allowed_sources: list[RequestedSource]
    blocked_sources: list[RequestedSource]
    action_mode: ActionMode
    status: RunStatus
    output_summary: str
    requested_action: ProposedAction | None
    approval_id: str | None
    action_outcome: str
    created_at: str = field(default_factory=lambda: utc_now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "actor_id": self.actor_id,
            "workflow_id": self.workflow_id,
            "correlation_id": self.correlation_id,
            "requested_sources": [item.to_dict() for item in self.requested_sources],
            "allowed_sources": [item.to_dict() for item in self.allowed_sources],
            "blocked_sources": [item.to_dict() for item in self.blocked_sources],
            "action_mode": self.action_mode,
            "status": self.status,
            "output_summary": self.output_summary,
            "requested_action": self.requested_action.to_dict() if self.requested_action else None,
            "approval_id": self.approval_id,
            "action_outcome": self.action_outcome,
            "created_at": self.created_at,
        }


@dataclass(slots=True)
class Alert:
    alert_id: str
    alert_type: str
    severity: str
    summary: str
    created_at: str
    run_id: str | None = None
    workflow_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RunRequest:
    actor_id: str
    workflow_id: str
    requested_sources: list[RequestedSource]
    requested_action: ProposedAction | None = None
    correlation_id: str = field(default_factory=lambda: new_id("corr"))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RunRequest":
        requested_sources = [
            RequestedSource(
                connector_id=item["connector_id"],
                scope=item["scope"],
            )
            for item in payload.get("requested_sources", [])
        ]
        requested_action = payload.get("requested_action")
        action = None
        if requested_action:
            action = ProposedAction(
                action_type=requested_action["type"],
                summary=requested_action["summary"],
            )
        return cls(
            actor_id=payload["actor_id"],
            workflow_id=payload["workflow_id"],
            requested_sources=requested_sources,
            requested_action=action,
            correlation_id=payload.get("correlation_id", new_id("corr")),
        )
