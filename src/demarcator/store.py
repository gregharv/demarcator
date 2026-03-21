from __future__ import annotations

from dataclasses import dataclass, field

from demarcator.models import Alert, ApprovalRequest, AuditEvent, Connector, DataScopeRule, User, Workflow, WorkflowGrant, WorkflowRun


@dataclass(slots=True)
class InMemoryStore:
    users: dict[str, User] = field(default_factory=dict)
    connectors: dict[str, Connector] = field(default_factory=dict)
    workflows: dict[str, Workflow] = field(default_factory=dict)
    rules: list[DataScopeRule] = field(default_factory=list)
    grants: list[WorkflowGrant] = field(default_factory=list)
    runs: dict[str, WorkflowRun] = field(default_factory=dict)
    approvals: dict[str, ApprovalRequest] = field(default_factory=dict)
    audit_events: list[AuditEvent] = field(default_factory=list)
    alerts: list[Alert] = field(default_factory=list)
