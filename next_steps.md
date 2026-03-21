# Next Steps

This is the recommended implementation order after the current in-memory prototype.

## 1. Persist the control-plane state

Replace the in-memory store with a real database-backed repository layer.

Implement:

- durable storage for users, workflows, grants, data-scope rules, runs, approvals, audit events, and alerts
- migration setup for schema changes
- stable IDs and timestamps generated at the persistence boundary

Why next:

- the current API loses all state on restart
- approvals and audit logs are only useful if they persist

## 2. Separate policy evaluation from workflow execution

Move from one service class into explicit application boundaries.

Implement:

- a policy engine module for scope checks and action-mode decisions
- an execution service that accepts a validated run request and emits domain events
- a clearer event model for blocked access, pending approval, approval decision, and action release

Why next:

- this will make the runtime replaceable
- it reduces the chance of mixing business policy with connector logic

## 3. Add real connector abstractions

Right now connectors are metadata only. They need execution-facing interfaces.

Implement:

- a connector adapter interface with read operations first
- connector-specific scope validation helpers
- connector health checks and sync status updates
- read-only defaults at the adapter level

Start with:

- email
- spreadsheets
- one line-of-business system such as QuickBooks or HubSpot

## 4. Build the first real admin UI

Add the SMB-facing surface that matches the product summary.

Implement:

- Connected Apps screen
- Data Access Rules screen
- People & Permissions screen
- Activity Feed screen
- Approvals screen

Important constraint:

- keep the language business-facing
- do not expose `pi`, prompt, model, or agent-framework concepts in the UI

## 5. Add authentication and actor identity

The prototype trusts raw actor IDs from the request. That is not acceptable beyond local development.

Implement:

- login/authentication for admins, operators, reviewers, and viewers
- server-side identity resolution
- authorization middleware for API routes
- audit actor attribution from authenticated sessions rather than request payloads

## 6. Add approval release mechanics

Approvals currently change run status, but they do not release work into an execution queue.

Implement:

- a queue or job table for approved actions
- idempotent execution of approved actions
- execution result updates back into the run record and audit log
- retry and failure handling for released actions

## 7. Add alerting and operator workflows

Alerts exist only as stored records.

Implement:

- email notifications for connector failures and stale approvals
- filtering by alert type and severity
- acknowledgement or resolution state for alerts
- summary digests for operators and reviewers

## 8. Define the real `pi` package boundary

The current bridge CLI is enough for local integration, but the next step is a real package structure for `pi`.

Implement:

- a local `pi` package or extension that wraps the bridge calls
- commands or tools for starting approved workflows from `pi`
- a small operator-focused workflow catalog inside `pi`
- correlation IDs propagated from `pi` into Demarcator events

Rule to keep:

- Demarcator owns policy, approvals, and audit
- `pi` only initiates execution and receives results

## 9. Add API-level integration tests

The current tests cover service logic only.

Implement:

- end-to-end tests against the HTTP handlers
- approval flow tests through real JSON requests
- failure-path tests for bad payloads and permission errors

## 10. Decide the first vertical wedge

Before broadening the platform, choose one narrow customer shape and implement toward that workflow.

Best current candidates from the summary:

- logistics / distribution
- finance / insurance operations
- healthcare-adjacent admin

Recommendation:

- choose one workflow-heavy Jacksonville SMB profile
- implement only the connectors and approval flow that make that workflow succeed end to end
