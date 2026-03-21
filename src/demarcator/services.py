from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from demarcator.models import (
    ActionMode,
    Alert,
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStatus,
    AuditEvent,
    ConnectorHealth,
    ProposedAction,
    RequestedSource,
    Role,
    RunRequest,
    RunStatus,
    User,
    Workflow,
    WorkflowRun,
    new_id,
    utc_now,
)
from demarcator.store import InMemoryStore


class DemarcatorError(Exception):
    """Base exception for API-facing errors."""


class NotFoundError(DemarcatorError):
    """Requested object does not exist."""


class PermissionDeniedError(DemarcatorError):
    """User is not allowed to perform the requested action."""


@dataclass(slots=True)
class ApprovalDecisionResult:
    approval: ApprovalRequest
    run: WorkflowRun

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval": self.approval.to_dict(),
            "run": self.run.to_dict(),
        }


class DemarcatorService:
    def __init__(self, store: InMemoryStore):
        self.store = store

    def list_connectors(self) -> list[dict[str, Any]]:
        return [connector.to_dict() for connector in self.store.connectors.values()]

    def list_workflows(self) -> list[dict[str, Any]]:
        return [workflow.to_dict() for workflow in self.store.workflows.values()]

    def list_rules(self) -> list[dict[str, Any]]:
        return [rule.to_dict() for rule in self.store.rules]

    def list_people(self) -> list[dict[str, Any]]:
        return [
            {
                **user.to_dict(),
                "workflow_ids": sorted(grant.workflow_id for grant in self.store.grants if grant.user_id == user.user_id),
            }
            for user in self.store.users.values()
        ]

    def list_activity(self) -> list[dict[str, Any]]:
        runs = sorted(self.store.runs.values(), key=lambda item: item.created_at, reverse=True)
        return [run.to_dict() for run in runs]

    def list_approvals(self) -> list[dict[str, Any]]:
        approvals = sorted(self.store.approvals.values(), key=lambda item: item.created_at, reverse=True)
        return [approval.to_dict() for approval in approvals]

    def list_audit_events(self) -> list[dict[str, Any]]:
        events = sorted(self.store.audit_events, key=lambda item: item.timestamp, reverse=True)
        return [event.to_dict() for event in events]

    def list_alerts(self) -> list[dict[str, Any]]:
        alerts = sorted(self.store.alerts, key=lambda item: item.created_at, reverse=True)
        return [alert.to_dict() for alert in alerts]

    def summary(self) -> dict[str, Any]:
        pending_approvals = sum(1 for approval in self.store.approvals.values() if approval.status == ApprovalStatus.PENDING)
        failed_connectors = sum(1 for connector in self.store.connectors.values() if connector.health == ConnectorHealth.FAILED)
        recent_runs = list(self.store.runs.values())
        failures = sum(1 for run in recent_runs if run.status == RunStatus.FAILED)
        blocked = sum(1 for run in recent_runs if run.blocked_sources or run.action_outcome == "blocked")
        approvals_waiting_too_long = self._count_stale_approvals()

        return {
            "connected_sources": len(self.store.connectors),
            "active_workflows": sum(1 for workflow in self.store.workflows.values() if workflow.active),
            "runs_total": len(self.store.runs),
            "failures": failures,
            "blocked_attempts": blocked,
            "pending_approvals": pending_approvals,
            "failed_connectors": failed_connectors,
            "stale_approvals": approvals_waiting_too_long,
            "alerts_open": len(self.store.alerts),
        }

    def run_workflow(self, request: RunRequest) -> WorkflowRun:
        actor = self._require_user(request.actor_id)
        workflow = self._require_workflow(request.workflow_id)
        self._ensure_actor_can_run(actor, workflow)

        allowed_sources, blocked_sources = self._evaluate_sources(workflow.workflow_id, request.requested_sources)
        status = RunStatus.SUCCESS
        output_summary = f"Workflow {workflow.name} processed {len(allowed_sources)} approved source(s)."
        approval_id = None
        action_outcome = "none"

        if not allowed_sources:
            status = RunStatus.BLOCKED
            output_summary = "Workflow run blocked because no requested sources were allowed."
            self._record_alert(
                alert_type="blocked_access_attempt",
                severity="medium",
                summary=f"{actor.name} attempted {workflow.name} without any allowed sources.",
                workflow_id=workflow.workflow_id,
            )

        if request.requested_action:
            action_outcome, status, approval_id, output_summary = self._handle_action_request(
                actor=actor,
                workflow=workflow,
                request=request,
                current_status=status,
                current_output=output_summary,
                allowed_sources=allowed_sources,
            )

        run = WorkflowRun(
            run_id=new_id("run"),
            actor_id=actor.user_id,
            workflow_id=workflow.workflow_id,
            correlation_id=request.correlation_id,
            requested_sources=request.requested_sources,
            allowed_sources=allowed_sources,
            blocked_sources=blocked_sources,
            action_mode=workflow.action_mode,
            status=status,
            output_summary=output_summary,
            requested_action=request.requested_action,
            approval_id=approval_id,
            action_outcome=action_outcome,
        )
        self.store.runs[run.run_id] = run
        if approval_id:
            self.store.approvals[approval_id].run_id = run.run_id

        if blocked_sources:
            self._record_alert(
                alert_type="blocked_access_attempt",
                severity="medium",
                summary=f"{actor.name} requested blocked data scope(s) for {workflow.name}.",
                run_id=run.run_id,
                workflow_id=workflow.workflow_id,
            )

        self._record_audit_event(
            event_type="workflow_run",
            actor_id=actor.user_id,
            run_id=run.run_id,
            workflow_id=workflow.workflow_id,
            details={
                "status": run.status,
                "allowed_sources": [item.to_dict() for item in allowed_sources],
                "blocked_sources": [item.to_dict() for item in blocked_sources],
                "action_outcome": run.action_outcome,
                "approval_id": approval_id,
                "correlation_id": request.correlation_id,
            },
        )
        return run

    def decide_approval(
        self,
        approval_id: str,
        reviewer_id: str,
        decision: ApprovalDecision,
        note: str | None = None,
    ) -> ApprovalDecisionResult:
        reviewer = self._require_user(reviewer_id)
        if reviewer.role not in {Role.ADMIN, Role.REVIEWER}:
            raise PermissionDeniedError(f"User {reviewer.user_id} is not allowed to review approvals.")

        approval = self.store.approvals.get(approval_id)
        if not approval:
            raise NotFoundError(f"Approval {approval_id} was not found.")
        if approval.status != ApprovalStatus.PENDING:
            raise DemarcatorError(f"Approval {approval_id} has already been decided.")

        run = self.store.runs.get(approval.run_id)
        if not run:
            raise NotFoundError(f"Run {approval.run_id} was not found.")

        approval.reviewer_id = reviewer.user_id
        approval.note = note
        approval.decided_at = utc_now().isoformat()

        if decision == ApprovalDecision.APPROVE:
            approval.status = ApprovalStatus.APPROVED
            run.status = RunStatus.SUCCESS
            run.action_outcome = "approved"
            run.output_summary = "Approved action released for execution."
        else:
            approval.status = ApprovalStatus.REJECTED
            run.status = RunStatus.BLOCKED
            run.action_outcome = "rejected"
            run.output_summary = "Requested action rejected during review."
            self._record_alert(
                alert_type="approval_rejected",
                severity="low",
                summary=f"{reviewer.name} rejected an action for workflow {run.workflow_id}.",
                run_id=run.run_id,
                workflow_id=run.workflow_id,
            )

        self._record_audit_event(
            event_type="approval_decision",
            actor_id=reviewer.user_id,
            run_id=run.run_id,
            workflow_id=run.workflow_id,
            details={
                "approval_id": approval.approval_id,
                "decision": decision,
                "note": note,
            },
        )
        return ApprovalDecisionResult(approval=approval, run=run)

    def _count_stale_approvals(self) -> int:
        threshold = utc_now() - timedelta(hours=4)
        return sum(
            1
            for approval in self.store.approvals.values()
            if approval.status == ApprovalStatus.PENDING and datetime.fromisoformat(approval.created_at) < threshold
        )

    def _record_alert(
        self,
        alert_type: str,
        severity: str,
        summary: str,
        run_id: str | None = None,
        workflow_id: str | None = None,
    ) -> None:
        self.store.alerts.append(
            Alert(
                alert_id=new_id("alert"),
                alert_type=alert_type,
                severity=severity,
                summary=summary,
                created_at=utc_now().isoformat(),
                run_id=run_id,
                workflow_id=workflow_id,
            )
        )

    def _record_audit_event(
        self,
        event_type: str,
        actor_id: str | None,
        run_id: str | None,
        workflow_id: str | None,
        details: dict[str, Any],
    ) -> None:
        self.store.audit_events.append(
            AuditEvent(
                event_id=new_id("evt"),
                event_type=event_type,
                timestamp=utc_now().isoformat(),
                actor_id=actor_id,
                run_id=run_id,
                workflow_id=workflow_id,
                details=details,
            )
        )

    def _evaluate_sources(
        self,
        workflow_id: str,
        requested_sources: list[RequestedSource],
    ) -> tuple[list[RequestedSource], list[RequestedSource]]:
        allowed_sources: list[RequestedSource] = []
        blocked_sources: list[RequestedSource] = []
        for source in requested_sources:
            matching_rules = [
                rule
                for rule in self.store.rules
                if rule.workflow_id == workflow_id and rule.connector_id == source.connector_id
            ]
            allowed = any(rule.allows(source.scope) for rule in matching_rules)
            if allowed:
                allowed_sources.append(source)
            else:
                blocked_sources.append(source)
        return allowed_sources, blocked_sources

    def _handle_action_request(
        self,
        actor: User,
        workflow: Workflow,
        request: RunRequest,
        current_status: RunStatus,
        current_output: str,
        allowed_sources: list[RequestedSource],
    ) -> tuple[str, RunStatus, str | None, str]:
        if workflow.action_mode == ActionMode.READ_ONLY:
            self._record_alert(
                alert_type="action_blocked",
                severity="medium",
                summary=f"{actor.name} requested a write action on read-only workflow {workflow.name}.",
                workflow_id=workflow.workflow_id,
            )
            return "blocked", RunStatus.BLOCKED, None, "Requested action blocked because the workflow is read-only."

        if workflow.action_mode == ActionMode.DRAFT_ONLY:
            return "drafted", current_status, None, "Draft action prepared and stored for operator review."

        approval = ApprovalRequest(
            approval_id=new_id("approval"),
            run_id="pending-run-reference",
            workflow_id=workflow.workflow_id,
            requested_by=actor.user_id,
            action=request.requested_action or ProposedAction(action_type="unknown", summary="No action summary provided."),
            source_data=allowed_sources,
            summary=f"{workflow.name} requested action approval: {request.requested_action.summary if request.requested_action else ''}".strip(),
        )
        self.store.approvals[approval.approval_id] = approval
        return "pending_approval", RunStatus.PENDING_APPROVAL, approval.approval_id, "Action queued for reviewer approval."

    def _require_user(self, user_id: str) -> User:
        user = self.store.users.get(user_id)
        if not user:
            raise NotFoundError(f"User {user_id} was not found.")
        return user

    def _require_workflow(self, workflow_id: str) -> Workflow:
        workflow = self.store.workflows.get(workflow_id)
        if not workflow:
            raise NotFoundError(f"Workflow {workflow_id} was not found.")
        return workflow

    def _ensure_actor_can_run(self, actor: User, workflow: Workflow) -> None:
        if actor.role == Role.ADMIN:
            return
        allowed = any(grant.user_id == actor.user_id and grant.workflow_id == workflow.workflow_id for grant in self.store.grants)
        if not allowed:
            raise PermissionDeniedError(f"User {actor.user_id} cannot run workflow {workflow.workflow_id}.")
