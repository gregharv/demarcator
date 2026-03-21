from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demarcator.bootstrap import create_seeded_service
from demarcator.models import ApprovalDecision, ApprovalStatus, ProposedAction, RequestedSource, RunRequest, RunStatus
from demarcator.pi_bridge import build_payload
from demarcator.services import PermissionDeniedError


class DemarcatorServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = create_seeded_service()

    def test_run_requires_workflow_grant(self) -> None:
        request = RunRequest(
            actor_id="victor-viewer",
            workflow_id="daily-activity-digest",
            requested_sources=[RequestedSource(connector_id="spreadsheets", scope="dashboards/daily")],
        )
        with self.assertRaises(PermissionDeniedError):
            self.service.run_workflow(request)

    def test_blocked_sources_are_recorded_but_allowed_sources_continue(self) -> None:
        request = RunRequest(
            actor_id="olivia-operator",
            workflow_id="ops-exception-review",
            requested_sources=[
                RequestedSource(connector_id="email", scope="mailbox/operations"),
                RequestedSource(connector_id="quickbooks", scope="payroll"),
            ],
        )
        run = self.service.run_workflow(request)
        self.assertEqual(run.status, RunStatus.SUCCESS)
        self.assertEqual(len(run.allowed_sources), 1)
        self.assertEqual(len(run.blocked_sources), 1)
        self.assertEqual(run.blocked_sources[0].scope, "payroll")

    def test_approval_required_action_creates_pending_approval(self) -> None:
        request = RunRequest(
            actor_id="olivia-operator",
            workflow_id="ops-exception-review",
            requested_sources=[RequestedSource(connector_id="email", scope="mailbox/operations")],
            requested_action=ProposedAction(action_type="send_email", summary="Notify customer"),
        )
        run = self.service.run_workflow(request)
        self.assertEqual(run.status, RunStatus.PENDING_APPROVAL)
        self.assertIsNotNone(run.approval_id)

        approval = self.service.store.approvals[run.approval_id]
        self.assertEqual(approval.status, ApprovalStatus.PENDING)
        self.assertEqual(approval.run_id, run.run_id)

    def test_approval_decision_updates_run(self) -> None:
        request = RunRequest(
            actor_id="olivia-operator",
            workflow_id="ops-exception-review",
            requested_sources=[RequestedSource(connector_id="email", scope="mailbox/operations")],
            requested_action=ProposedAction(action_type="send_email", summary="Notify customer"),
        )
        run = self.service.run_workflow(request)

        result = self.service.decide_approval(
            approval_id=run.approval_id or "",
            reviewer_id="riley-reviewer",
            decision=ApprovalDecision.APPROVE,
            note="Safe to send.",
        )

        self.assertEqual(result.approval.status, ApprovalStatus.APPROVED)
        self.assertEqual(result.run.status, RunStatus.SUCCESS)
        self.assertEqual(result.run.action_outcome, "approved")

    def test_read_only_workflow_blocks_requested_action(self) -> None:
        request = RunRequest(
            actor_id="olivia-operator",
            workflow_id="daily-activity-digest",
            requested_sources=[RequestedSource(connector_id="spreadsheets", scope="dashboards/daily")],
            requested_action=ProposedAction(action_type="send_email", summary="This should not send"),
        )

        run = self.service.run_workflow(request)
        self.assertEqual(run.status, RunStatus.BLOCKED)
        self.assertEqual(run.action_outcome, "blocked")

    def test_pi_bridge_payload_shape(self) -> None:
        class Args:
            actor = "olivia-operator"
            workflow = "ops-exception-review"
            source = [{"connector_id": "email", "scope": "mailbox/operations"}]
            correlation_id = "corr_demo"
            action_type = "send_email"
            action_summary = "Notify customer"

        payload = build_payload(Args())
        self.assertEqual(payload["actor_id"], "olivia-operator")
        self.assertEqual(payload["workflow_id"], "ops-exception-review")
        self.assertEqual(payload["requested_sources"][0]["connector_id"], "email")
        self.assertEqual(payload["requested_action"]["type"], "send_email")


if __name__ == "__main__":
    unittest.main()
