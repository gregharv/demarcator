from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demarcator.api import build_api


class DemarcatorAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "demarcator-api.db")
        self.api = build_api(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_health_endpoint(self) -> None:
        status, payload = self.api.handle("GET", "/health")
        self.assertEqual(status.value, 200)
        self.assertEqual(payload["status"], "ok")

    def test_unknown_route_returns_404(self) -> None:
        status, payload = self.api.handle("GET", "/missing")
        self.assertEqual(status.value, 404)
        self.assertIn("not found", payload["error"].lower())

    def test_invalid_json_returns_400(self) -> None:
        status, payload = self.api.handle("POST", "/runs", b"{bad json")
        self.assertEqual(status.value, 400)
        self.assertIn("valid json", payload["error"].lower())

    def test_missing_required_field_returns_400(self) -> None:
        body = json.dumps({"workflow_id": "daily-activity-digest", "requested_sources": []}).encode()
        status, payload = self.api.handle("POST", "/runs", body)
        self.assertEqual(status.value, 400)
        self.assertIn("actor_id", payload["error"])

    def test_non_reviewer_cannot_decide_approval(self) -> None:
        run_payload = json.dumps(
            {
                "actor_id": "olivia-operator",
                "workflow_id": "ops-exception-review",
                "requested_sources": [{"connector_id": "email", "scope": "mailbox/operations"}],
                "requested_action": {"type": "send_email", "summary": "Notify customer"},
            }
        ).encode()
        run_status, run_body = self.api.handle("POST", "/runs", run_payload)
        self.assertEqual(run_status.value, 201)

        decision_payload = json.dumps(
            {
                "reviewer_id": "olivia-operator",
                "decision": "approve",
                "note": "Should not work",
            }
        ).encode()
        status, payload = self.api.handle(
            "POST",
            f"/approvals/{run_body['approval_id']}/decision",
            decision_payload,
        )
        self.assertEqual(status.value, 403)
        self.assertIn("not allowed", payload["error"])

    def test_unknown_approval_returns_404(self) -> None:
        payload = json.dumps(
            {"reviewer_id": "riley-reviewer", "decision": "approve", "note": "Missing"}
        ).encode()
        status, body = self.api.handle("POST", "/approvals/approval_missing/decision", payload)
        self.assertEqual(status.value, 404)
        self.assertIn("not found", body["error"].lower())

    def test_run_and_approval_survive_rebuild(self) -> None:
        run_payload = json.dumps(
            {
                "actor_id": "olivia-operator",
                "workflow_id": "ops-exception-review",
                "requested_sources": [{"connector_id": "email", "scope": "mailbox/operations"}],
                "requested_action": {"type": "send_email", "summary": "Notify customer"},
            }
        ).encode()
        run_status, run_body = self.api.handle("POST", "/runs", run_payload)
        self.assertEqual(run_status.value, 201)

        rebuilt = build_api(self.db_path)
        approvals_status, approvals_payload = rebuilt.handle("GET", "/approvals")
        activity_status, activity_payload = rebuilt.handle("GET", "/activity")
        self.assertEqual(approvals_status.value, 200)
        self.assertEqual(activity_status.value, 200)
        self.assertEqual(approvals_payload["items"][0]["approval_id"], run_body["approval_id"])
        self.assertEqual(activity_payload["items"][0]["run_id"], run_body["run_id"])


if __name__ == "__main__":
    unittest.main()
