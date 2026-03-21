from __future__ import annotations

from demarcator.models import ActionMode, Connector, ConnectorHealth, DataScopeRule, Role, User, Workflow, WorkflowGrant
from demarcator.services import DemarcatorService
from demarcator.store import InMemoryStore


def create_seeded_service() -> DemarcatorService:
    store = InMemoryStore()

    store.users = {
        "alice-admin": User(user_id="alice-admin", name="Alice Admin", role=Role.ADMIN),
        "olivia-operator": User(user_id="olivia-operator", name="Olivia Operator", role=Role.OPERATOR),
        "riley-reviewer": User(user_id="riley-reviewer", name="Riley Reviewer", role=Role.REVIEWER),
        "victor-viewer": User(user_id="victor-viewer", name="Victor Viewer", role=Role.VIEWER),
    }

    store.connectors = {
        "email": Connector(
            connector_id="email",
            name="Shared Email",
            health=ConnectorHealth.HEALTHY,
            last_successful_sync="2026-03-21T09:00:00+00:00",
        ),
        "spreadsheets": Connector(
            connector_id="spreadsheets",
            name="Shared Spreadsheets",
            health=ConnectorHealth.HEALTHY,
            last_successful_sync="2026-03-21T08:50:00+00:00",
        ),
        "quickbooks": Connector(
            connector_id="quickbooks",
            name="QuickBooks",
            health=ConnectorHealth.HEALTHY,
            last_successful_sync="2026-03-21T08:45:00+00:00",
        ),
        "hubspot": Connector(
            connector_id="hubspot",
            name="HubSpot",
            health=ConnectorHealth.DEGRADED,
            last_successful_sync="2026-03-21T06:15:00+00:00",
        ),
    }

    store.workflows = {
        "ops-exception-review": Workflow(
            workflow_id="ops-exception-review",
            name="Ops Exception Review",
            description="Summarize operational exceptions and draft outbound handling.",
            action_mode=ActionMode.APPROVAL_REQUIRED,
        ),
        "daily-activity-digest": Workflow(
            workflow_id="daily-activity-digest",
            name="Daily Activity Digest",
            description="Prepare a read-only summary of yesterday's activity.",
            action_mode=ActionMode.READ_ONLY,
        ),
        "customer-followup-draft": Workflow(
            workflow_id="customer-followup-draft",
            name="Customer Follow-up Draft",
            description="Draft customer follow-up communication for operator review.",
            action_mode=ActionMode.DRAFT_ONLY,
        ),
    }

    store.rules = [
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

    store.grants = [
        WorkflowGrant(user_id="olivia-operator", workflow_id="ops-exception-review"),
        WorkflowGrant(user_id="olivia-operator", workflow_id="daily-activity-digest"),
        WorkflowGrant(user_id="olivia-operator", workflow_id="customer-followup-draft"),
        WorkflowGrant(user_id="riley-reviewer", workflow_id="daily-activity-digest"),
    ]

    return DemarcatorService(store)
