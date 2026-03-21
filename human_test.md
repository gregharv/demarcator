# Human Test Plan

This file is the manual test checklist for the current Demarcator slice.

## 1. Start the API

From the repo root:

```bash
python -m demarcator.api --host 127.0.0.1 --port 8080
```

Expected result:

- the process starts without crashing
- terminal prints `Demarcator API listening on http://127.0.0.1:8080`

## 2. Confirm health and seeded summary

In a second terminal:

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/summary
```

Check:

- `/health` returns `{"status": "ok"}`
- `/summary` returns counts for connected sources, workflows, runs, approvals, and alerts

## 3. Inspect seeded admin data

Run:

```bash
curl http://127.0.0.1:8080/connectors
curl http://127.0.0.1:8080/workflows
curl http://127.0.0.1:8080/rules
curl http://127.0.0.1:8080/people
```

Check:

- connectors include `email`, `spreadsheets`, `quickbooks`, `hubspot`
- workflows include `ops-exception-review`, `daily-activity-digest`, `customer-followup-draft`
- rules show limited allowed scopes rather than broad access
- people show simple role assignments and workflow grants

## 4. Run an allowed read-only workflow

Run:

```bash
curl -X POST http://127.0.0.1:8080/runs \
  -H 'content-type: application/json' \
  -d '{
    "actor_id": "olivia-operator",
    "workflow_id": "daily-activity-digest",
    "requested_sources": [
      {"connector_id": "spreadsheets", "scope": "dashboards/daily"}
    ]
  }'
```

Check:

- response status is `201`
- run status is `success`
- blocked sources is empty
- action mode is `read_only`

## 5. Confirm blocked source behavior

Run:

```bash
curl -X POST http://127.0.0.1:8080/runs \
  -H 'content-type: application/json' \
  -d '{
    "actor_id": "olivia-operator",
    "workflow_id": "ops-exception-review",
    "requested_sources": [
      {"connector_id": "email", "scope": "mailbox/operations"},
      {"connector_id": "quickbooks", "scope": "payroll"}
    ]
  }'
```

Check:

- run still succeeds because one source is allowed
- `quickbooks/payroll` appears under `blocked_sources`
- `/alerts` contains a blocked-access alert
- `/audit` contains a workflow run event with allowed and blocked sources

## 6. Confirm approval-required action flow

Run:

```bash
curl -X POST http://127.0.0.1:8080/runs \
  -H 'content-type: application/json' \
  -d '{
    "actor_id": "olivia-operator",
    "workflow_id": "ops-exception-review",
    "requested_sources": [
      {"connector_id": "email", "scope": "mailbox/operations"},
      {"connector_id": "quickbooks", "scope": "reports/ar-aging"}
    ],
    "requested_action": {
      "type": "send_email",
      "summary": "Email the customer with the exception summary."
    }
  }'
```

Check:

- run status is `pending_approval`
- response contains `approval_id`
- `/approvals` shows a pending item with source data and action summary

## 7. Approve a pending action

Replace `<approval-id>` with the actual value from the previous step:

```bash
curl -X POST http://127.0.0.1:8080/approvals/<approval-id>/decision \
  -H 'content-type: application/json' \
  -d '{
    "reviewer_id": "riley-reviewer",
    "decision": "approve",
    "note": "Safe to send."
  }'
```

Check:

- approval status changes to `approved`
- linked run status changes to `success`
- `/audit` records an `approval_decision` event

## 8. Reject a pending action

Create another approval-required run, then reject it:

```bash
curl -X POST http://127.0.0.1:8080/approvals/<approval-id>/decision \
  -H 'content-type: application/json' \
  -d '{
    "reviewer_id": "riley-reviewer",
    "decision": "reject",
    "note": "Too risky."
  }'
```

Check:

- approval status changes to `rejected`
- run status changes to `blocked`
- `/alerts` contains an `approval_rejected` alert

## 9. Confirm permission enforcement

Run:

```bash
curl -X POST http://127.0.0.1:8080/runs \
  -H 'content-type: application/json' \
  -d '{
    "actor_id": "victor-viewer",
    "workflow_id": "daily-activity-digest",
    "requested_sources": [
      {"connector_id": "spreadsheets", "scope": "dashboards/daily"}
    ]
  }'
```

Check:

- response status is `403`
- error says the user cannot run the workflow

## 10. Confirm read-only workflows block side effects

Run:

```bash
curl -X POST http://127.0.0.1:8080/runs \
  -H 'content-type: application/json' \
  -d '{
    "actor_id": "olivia-operator",
    "workflow_id": "daily-activity-digest",
    "requested_sources": [
      {"connector_id": "spreadsheets", "scope": "dashboards/daily"}
    ],
    "requested_action": {
      "type": "send_email",
      "summary": "This should be blocked."
    }
  }'
```

Check:

- run status is `blocked`
- action outcome is `blocked`
- `/alerts` records an `action_blocked` event

## 11. Test the `pi` bridge CLI

With the API still running:

```bash
python -m demarcator.pi_bridge \
  --server http://127.0.0.1:8080 \
  --actor olivia-operator \
  --workflow ops-exception-review \
  --source email:mailbox/operations \
  --source quickbooks:reports/ar-aging \
  --action-type send_email \
  --action-summary "Email the customer with the exception summary."
```

Check:

- CLI prints JSON for a created run
- payload shape matches the direct API call
- resulting approval appears in `/approvals`

## 12. Run automated tests

Run:

```bash
python -m unittest discover -s tests -v
```

Check:

- all tests pass

## Notes to capture while testing

Write down:

- any confusing API field names
- any missing admin views you needed during manual testing
- any cases where the status model felt ambiguous
- any API responses that should become frontend-friendly view models later
