from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from fastlite import Database

from demarcator.models import (
    ActionMode,
    Alert,
    ApprovalRequest,
    ApprovalStatus,
    AuditEvent,
    Connector,
    ConnectorHealth,
    DataScopeRule,
    ProposedAction,
    RequestedSource,
    Role,
    RunStatus,
    User,
    Workflow,
    WorkflowGrant,
    WorkflowRun,
    new_id,
    utc_now,
)


class SQLiteRepository:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db = Database(self.db_path)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self.db.begin()
        try:
            yield
        except Exception:
            self.db.rollback()
            raise
        else:
            self.db.commit()

    def initialize_schema(self) -> None:
        statements = [
            """
            create table if not exists schema_migrations (
                version text primary key,
                applied_at text not null
            )
            """,
            """
            create table if not exists users (
                user_id text primary key,
                name text not null,
                role text not null
            )
            """,
            """
            create table if not exists connectors (
                connector_id text primary key,
                name text not null,
                health text not null,
                last_successful_sync text not null
            )
            """,
            """
            create table if not exists workflows (
                workflow_id text primary key,
                name text not null,
                description text not null,
                action_mode text not null,
                active integer not null
            )
            """,
            """
            create table if not exists data_scope_rules (
                workflow_id text not null,
                connector_id text not null,
                seq integer not null,
                scope text not null,
                primary key (workflow_id, connector_id, seq)
            )
            """,
            """
            create table if not exists workflow_grants (
                user_id text not null,
                workflow_id text not null,
                primary key (user_id, workflow_id)
            )
            """,
            """
            create table if not exists workflow_runs (
                run_id text primary key,
                actor_id text not null,
                workflow_id text not null,
                correlation_id text not null,
                action_mode text not null,
                status text not null,
                output_summary text not null,
                action_type text,
                action_summary text,
                approval_id text,
                action_outcome text not null,
                created_at text not null
            )
            """,
            """
            create table if not exists requested_sources (
                run_id text not null,
                seq integer not null,
                connector_id text not null,
                scope text not null,
                primary key (run_id, seq)
            )
            """,
            """
            create table if not exists allowed_sources (
                run_id text not null,
                seq integer not null,
                connector_id text not null,
                scope text not null,
                primary key (run_id, seq)
            )
            """,
            """
            create table if not exists blocked_sources (
                run_id text not null,
                seq integer not null,
                connector_id text not null,
                scope text not null,
                primary key (run_id, seq)
            )
            """,
            """
            create table if not exists approval_requests (
                approval_id text primary key,
                run_id text not null,
                workflow_id text not null,
                requested_by text not null,
                action_type text not null,
                action_summary text not null,
                summary text not null,
                status text not null,
                reviewer_id text,
                note text,
                created_at text not null,
                decided_at text
            )
            """,
            """
            create table if not exists approval_sources (
                approval_id text not null,
                seq integer not null,
                connector_id text not null,
                scope text not null,
                primary key (approval_id, seq)
            )
            """,
            """
            create table if not exists audit_events (
                event_id text primary key,
                event_type text not null,
                timestamp text not null,
                actor_id text,
                run_id text,
                workflow_id text,
                details_json text not null
            )
            """,
            """
            create table if not exists alerts (
                alert_id text primary key,
                alert_type text not null,
                severity text not null,
                summary text not null,
                created_at text not null,
                run_id text,
                workflow_id text
            )
            """,
            "create index if not exists idx_runs_created_at on workflow_runs (created_at desc)",
            "create index if not exists idx_approvals_created_at on approval_requests (created_at desc)",
            "create index if not exists idx_audit_timestamp on audit_events (timestamp desc)",
            "create index if not exists idx_alerts_created_at on alerts (created_at desc)",
        ]
        for statement in statements:
            self.db.execute(statement)
        self.db.execute(
            "insert or ignore into schema_migrations (version, applied_at) values (?, ?)",
            ("2026-03-21-initial", utc_now().isoformat()),
        )

    def is_empty(self) -> bool:
        row = self.db.q("select count(*) as count from users")[0]
        return int(row["count"]) == 0

    def seed_demo_data(self) -> None:
        users = [
            User(user_id="alice-admin", name="Alice Admin", role=Role.ADMIN),
            User(user_id="olivia-operator", name="Olivia Operator", role=Role.OPERATOR),
            User(user_id="riley-reviewer", name="Riley Reviewer", role=Role.REVIEWER),
            User(user_id="victor-viewer", name="Victor Viewer", role=Role.VIEWER),
        ]
        connectors = [
            Connector(
                connector_id="email",
                name="Shared Email",
                health=ConnectorHealth.HEALTHY,
                last_successful_sync="2026-03-21T09:00:00+00:00",
            ),
            Connector(
                connector_id="spreadsheets",
                name="Shared Spreadsheets",
                health=ConnectorHealth.HEALTHY,
                last_successful_sync="2026-03-21T08:50:00+00:00",
            ),
            Connector(
                connector_id="quickbooks",
                name="QuickBooks",
                health=ConnectorHealth.HEALTHY,
                last_successful_sync="2026-03-21T08:45:00+00:00",
            ),
            Connector(
                connector_id="hubspot",
                name="HubSpot",
                health=ConnectorHealth.DEGRADED,
                last_successful_sync="2026-03-21T06:15:00+00:00",
            ),
        ]
        workflows = [
            Workflow(
                workflow_id="ops-exception-review",
                name="Ops Exception Review",
                description="Summarize operational exceptions and draft outbound handling.",
                action_mode=ActionMode.APPROVAL_REQUIRED,
            ),
            Workflow(
                workflow_id="daily-activity-digest",
                name="Daily Activity Digest",
                description="Prepare a read-only summary of yesterday's activity.",
                action_mode=ActionMode.READ_ONLY,
            ),
            Workflow(
                workflow_id="customer-followup-draft",
                name="Customer Follow-up Draft",
                description="Draft customer follow-up communication for operator review.",
                action_mode=ActionMode.DRAFT_ONLY,
            ),
        ]
        rules = [
            DataScopeRule(
                workflow_id="ops-exception-review",
                connector_id="email",
                allowed_scopes=["mailbox/operations"],
            ),
            DataScopeRule(
                workflow_id="ops-exception-review",
                connector_id="quickbooks",
                allowed_scopes=["reports/ar-aging", "reports/open-invoices"],
            ),
            DataScopeRule(
                workflow_id="daily-activity-digest",
                connector_id="spreadsheets",
                allowed_scopes=["dashboards/daily", "exports/activity-log"],
            ),
            DataScopeRule(
                workflow_id="customer-followup-draft",
                connector_id="hubspot",
                allowed_scopes=["contacts", "tickets/open"],
            ),
            DataScopeRule(
                workflow_id="customer-followup-draft",
                connector_id="email",
                allowed_scopes=["mailbox/customer-success"],
            ),
        ]
        grants = [
            WorkflowGrant(user_id="olivia-operator", workflow_id="ops-exception-review"),
            WorkflowGrant(user_id="olivia-operator", workflow_id="daily-activity-digest"),
            WorkflowGrant(user_id="olivia-operator", workflow_id="customer-followup-draft"),
            WorkflowGrant(user_id="riley-reviewer", workflow_id="daily-activity-digest"),
        ]

        with self.transaction():
            for user in users:
                self.db.execute(
                    "insert into users (user_id, name, role) values (?, ?, ?)",
                    (user.user_id, user.name, user.role),
                )
            for connector in connectors:
                self.db.execute(
                    """
                    insert into connectors (connector_id, name, health, last_successful_sync)
                    values (?, ?, ?, ?)
                    """,
                    (
                        connector.connector_id,
                        connector.name,
                        connector.health,
                        connector.last_successful_sync,
                    ),
                )
            for workflow in workflows:
                self.db.execute(
                    """
                    insert into workflows (workflow_id, name, description, action_mode, active)
                    values (?, ?, ?, ?, ?)
                    """,
                    (
                        workflow.workflow_id,
                        workflow.name,
                        workflow.description,
                        workflow.action_mode,
                        int(workflow.active),
                    ),
                )
            for rule in rules:
                for seq, scope in enumerate(rule.allowed_scopes):
                    self.db.execute(
                        """
                        insert into data_scope_rules (workflow_id, connector_id, seq, scope)
                        values (?, ?, ?, ?)
                        """,
                        (rule.workflow_id, rule.connector_id, seq, scope),
                    )
            for grant in grants:
                self.db.execute(
                    "insert into workflow_grants (user_id, workflow_id) values (?, ?)",
                    (grant.user_id, grant.workflow_id),
                )

    def list_connectors(self) -> list[Connector]:
        rows = self.db.q("select * from connectors order by connector_id")
        return [
            Connector(
                connector_id=row["connector_id"],
                name=row["name"],
                health=ConnectorHealth(row["health"]),
                last_successful_sync=row["last_successful_sync"],
            )
            for row in rows
        ]

    def list_workflows(self) -> list[Workflow]:
        rows = self.db.q("select * from workflows order by workflow_id")
        return [
            Workflow(
                workflow_id=row["workflow_id"],
                name=row["name"],
                description=row["description"],
                action_mode=ActionMode(row["action_mode"]),
                active=bool(row["active"]),
            )
            for row in rows
        ]

    def get_workflow(self, workflow_id: str) -> Workflow | None:
        rows = self.db.q("select * from workflows where workflow_id = ?", (workflow_id,))
        if not rows:
            return None
        row = rows[0]
        return Workflow(
            workflow_id=row["workflow_id"],
            name=row["name"],
            description=row["description"],
            action_mode=ActionMode(row["action_mode"]),
            active=bool(row["active"]),
        )

    def list_rules(self) -> list[DataScopeRule]:
        rows = self.db.q(
            """
            select workflow_id, connector_id, seq, scope
            from data_scope_rules
            order by workflow_id, connector_id, seq
            """
        )
        grouped: dict[tuple[str, str], list[str]] = {}
        for row in rows:
            key = (row["workflow_id"], row["connector_id"])
            grouped.setdefault(key, []).append(row["scope"])
        return [
            DataScopeRule(
                workflow_id=workflow_id,
                connector_id=connector_id,
                allowed_scopes=scopes,
            )
            for (workflow_id, connector_id), scopes in grouped.items()
        ]

    def list_rules_for_workflow(self, workflow_id: str) -> list[DataScopeRule]:
        return [rule for rule in self.list_rules() if rule.workflow_id == workflow_id]

    def list_users(self) -> list[User]:
        rows = self.db.q("select * from users order by user_id")
        return [User(user_id=row["user_id"], name=row["name"], role=Role(row["role"])) for row in rows]

    def get_user(self, user_id: str) -> User | None:
        rows = self.db.q("select * from users where user_id = ?", (user_id,))
        if not rows:
            return None
        row = rows[0]
        return User(user_id=row["user_id"], name=row["name"], role=Role(row["role"]))

    def list_workflow_grants(self) -> list[WorkflowGrant]:
        rows = self.db.q("select * from workflow_grants order by user_id, workflow_id")
        return [WorkflowGrant(user_id=row["user_id"], workflow_id=row["workflow_id"]) for row in rows]

    def has_workflow_grant(self, user_id: str, workflow_id: str) -> bool:
        rows = self.db.q(
            "select 1 as present from workflow_grants where user_id = ? and workflow_id = ? limit 1",
            (user_id, workflow_id),
        )
        return bool(rows)

    def save_run(self, run: WorkflowRun) -> None:
        self.db.execute(
            """
            insert into workflow_runs (
                run_id, actor_id, workflow_id, correlation_id, action_mode, status,
                output_summary, action_type, action_summary, approval_id, action_outcome, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.run_id,
                run.actor_id,
                run.workflow_id,
                run.correlation_id,
                run.action_mode,
                run.status,
                run.output_summary,
                run.requested_action.action_type if run.requested_action else None,
                run.requested_action.summary if run.requested_action else None,
                run.approval_id,
                run.action_outcome,
                run.created_at,
            ),
        )
        self._replace_sources("requested_sources", run.run_id, run.requested_sources)
        self._replace_sources("allowed_sources", run.run_id, run.allowed_sources)
        self._replace_sources("blocked_sources", run.run_id, run.blocked_sources)

    def update_run(self, run: WorkflowRun) -> None:
        self.db.execute(
            """
            update workflow_runs
            set actor_id = ?, workflow_id = ?, correlation_id = ?, action_mode = ?, status = ?,
                output_summary = ?, action_type = ?, action_summary = ?, approval_id = ?,
                action_outcome = ?, created_at = ?
            where run_id = ?
            """,
            (
                run.actor_id,
                run.workflow_id,
                run.correlation_id,
                run.action_mode,
                run.status,
                run.output_summary,
                run.requested_action.action_type if run.requested_action else None,
                run.requested_action.summary if run.requested_action else None,
                run.approval_id,
                run.action_outcome,
                run.created_at,
                run.run_id,
            ),
        )
        self._replace_sources("requested_sources", run.run_id, run.requested_sources)
        self._replace_sources("allowed_sources", run.run_id, run.allowed_sources)
        self._replace_sources("blocked_sources", run.run_id, run.blocked_sources)

    def get_run(self, run_id: str) -> WorkflowRun | None:
        rows = self.db.q("select * from workflow_runs where run_id = ?", (run_id,))
        if not rows:
            return None
        return self._hydrate_run(rows[0])

    def list_runs(self) -> list[WorkflowRun]:
        rows = self.db.q("select * from workflow_runs order by created_at desc")
        return [self._hydrate_run(row) for row in rows]

    def save_approval(self, approval: ApprovalRequest) -> None:
        self.db.execute(
            """
            insert into approval_requests (
                approval_id, run_id, workflow_id, requested_by, action_type, action_summary,
                summary, status, reviewer_id, note, created_at, decided_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                approval.approval_id,
                approval.run_id,
                approval.workflow_id,
                approval.requested_by,
                approval.action.action_type,
                approval.action.summary,
                approval.summary,
                approval.status,
                approval.reviewer_id,
                approval.note,
                approval.created_at,
                approval.decided_at,
            ),
        )
        self._replace_approval_sources(approval.approval_id, approval.source_data)

    def update_approval(self, approval: ApprovalRequest) -> None:
        self.db.execute(
            """
            update approval_requests
            set run_id = ?, workflow_id = ?, requested_by = ?, action_type = ?, action_summary = ?,
                summary = ?, status = ?, reviewer_id = ?, note = ?, created_at = ?, decided_at = ?
            where approval_id = ?
            """,
            (
                approval.run_id,
                approval.workflow_id,
                approval.requested_by,
                approval.action.action_type,
                approval.action.summary,
                approval.summary,
                approval.status,
                approval.reviewer_id,
                approval.note,
                approval.created_at,
                approval.decided_at,
                approval.approval_id,
            ),
        )
        self._replace_approval_sources(approval.approval_id, approval.source_data)

    def get_approval(self, approval_id: str) -> ApprovalRequest | None:
        rows = self.db.q("select * from approval_requests where approval_id = ?", (approval_id,))
        if not rows:
            return None
        return self._hydrate_approval(rows[0])

    def list_approvals(self) -> list[ApprovalRequest]:
        rows = self.db.q("select * from approval_requests order by created_at desc")
        return [self._hydrate_approval(row) for row in rows]

    def append_audit_event(
        self,
        event_type: str,
        actor_id: str | None,
        run_id: str | None,
        workflow_id: str | None,
        details: dict,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=new_id("evt"),
            event_type=event_type,
            timestamp=utc_now().isoformat(),
            actor_id=actor_id,
            run_id=run_id,
            workflow_id=workflow_id,
            details=details,
        )
        self.db.execute(
            """
            insert into audit_events (event_id, event_type, timestamp, actor_id, run_id, workflow_id, details_json)
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.event_type,
                event.timestamp,
                event.actor_id,
                event.run_id,
                event.workflow_id,
                json.dumps(event.details, sort_keys=True),
            ),
        )
        return event

    def list_audit_events(self) -> list[AuditEvent]:
        rows = self.db.q("select * from audit_events order by timestamp desc")
        return [
            AuditEvent(
                event_id=row["event_id"],
                event_type=row["event_type"],
                timestamp=row["timestamp"],
                actor_id=row["actor_id"],
                run_id=row["run_id"],
                workflow_id=row["workflow_id"],
                details=json.loads(row["details_json"]),
            )
            for row in rows
        ]

    def append_alert(
        self,
        alert_type: str,
        severity: str,
        summary: str,
        run_id: str | None = None,
        workflow_id: str | None = None,
    ) -> Alert:
        alert = Alert(
            alert_id=new_id("alert"),
            alert_type=alert_type,
            severity=severity,
            summary=summary,
            created_at=utc_now().isoformat(),
            run_id=run_id,
            workflow_id=workflow_id,
        )
        self.db.execute(
            """
            insert into alerts (alert_id, alert_type, severity, summary, created_at, run_id, workflow_id)
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert.alert_id,
                alert.alert_type,
                alert.severity,
                alert.summary,
                alert.created_at,
                alert.run_id,
                alert.workflow_id,
            ),
        )
        return alert

    def list_alerts(self) -> list[Alert]:
        rows = self.db.q("select * from alerts order by created_at desc")
        return [
            Alert(
                alert_id=row["alert_id"],
                alert_type=row["alert_type"],
                severity=row["severity"],
                summary=row["summary"],
                created_at=row["created_at"],
                run_id=row["run_id"],
                workflow_id=row["workflow_id"],
            )
            for row in rows
        ]

    def _replace_sources(self, table: str, run_id: str, sources: list[RequestedSource]) -> None:
        self.db.execute(f"delete from {table} where run_id = ?", (run_id,))
        for seq, source in enumerate(sources):
            self.db.execute(
                f"insert into {table} (run_id, seq, connector_id, scope) values (?, ?, ?, ?)",
                (run_id, seq, source.connector_id, source.scope),
            )

    def _replace_approval_sources(self, approval_id: str, sources: list[RequestedSource]) -> None:
        self.db.execute("delete from approval_sources where approval_id = ?", (approval_id,))
        for seq, source in enumerate(sources):
            self.db.execute(
                """
                insert into approval_sources (approval_id, seq, connector_id, scope)
                values (?, ?, ?, ?)
                """,
                (approval_id, seq, source.connector_id, source.scope),
            )

    def _load_sources(self, table: str, run_id: str) -> list[RequestedSource]:
        rows = self.db.q(
            f"select connector_id, scope from {table} where run_id = ? order by seq",
            (run_id,),
        )
        return [RequestedSource(connector_id=row["connector_id"], scope=row["scope"]) for row in rows]

    def _load_approval_sources(self, approval_id: str) -> list[RequestedSource]:
        rows = self.db.q(
            """
            select connector_id, scope
            from approval_sources
            where approval_id = ?
            order by seq
            """,
            (approval_id,),
        )
        return [RequestedSource(connector_id=row["connector_id"], scope=row["scope"]) for row in rows]

    def _hydrate_run(self, row: dict) -> WorkflowRun:
        requested_action = None
        if row["action_type"] and row["action_summary"]:
            requested_action = ProposedAction(
                action_type=row["action_type"],
                summary=row["action_summary"],
            )
        return WorkflowRun(
            run_id=row["run_id"],
            actor_id=row["actor_id"],
            workflow_id=row["workflow_id"],
            correlation_id=row["correlation_id"],
            requested_sources=self._load_sources("requested_sources", row["run_id"]),
            allowed_sources=self._load_sources("allowed_sources", row["run_id"]),
            blocked_sources=self._load_sources("blocked_sources", row["run_id"]),
            action_mode=ActionMode(row["action_mode"]),
            status=RunStatus(row["status"]),
            output_summary=row["output_summary"],
            requested_action=requested_action,
            approval_id=row["approval_id"],
            action_outcome=row["action_outcome"],
            created_at=row["created_at"],
        )

    def _hydrate_approval(self, row: dict) -> ApprovalRequest:
        return ApprovalRequest(
            approval_id=row["approval_id"],
            run_id=row["run_id"],
            workflow_id=row["workflow_id"],
            requested_by=row["requested_by"],
            action=ProposedAction(
                action_type=row["action_type"],
                summary=row["action_summary"],
            ),
            source_data=self._load_approval_sources(row["approval_id"]),
            summary=row["summary"],
            status=ApprovalStatus(row["status"]),
            reviewer_id=row["reviewer_id"],
            note=row["note"],
            created_at=row["created_at"],
            decided_at=row["decided_at"],
        )
