Project summary

We started from the question: how can one person monetize data science talent in the age of agents, ideally in a way that works for SMBs and can be sold locally in Jacksonville, Florida.

We narrowed in on a product direction:
Build an SMB-facing AI control plane on top of pi.dev.

Core idea

Use pi.dev as the agent/runtime layer, but build the missing trust/control product around it for SMBs.

The value is not “yet another AI chatbot.”
The value is:
- connect tools the SMB already pays for
- control what data AI can and cannot use
- control which users can run which workflows
- require approvals before risky actions
- show a clean log of what happened
- provide light monitoring/alerts

Important framing

pi.dev seems suitable as the underlying runtime/agent layer, but not as the whole SMB product.
The major missing layer is the customer-facing control plane:
- permissions/policies
- approvals
- audit trail
- monitoring
- simple admin UI

The product should feel like:
“we connect the tools you already use, put approvals around AI, and give you one place to see what ran, what touched data, what failed, and what needs review.”

Not like:
- “agent framework”
- “AI orchestration”
- “prompt engineering product”

Key product thesis

The thing to build first is not a giant analytics dashboard.
The first build should be an admin/control plane for AI workflows.

Think:
policy system first, UI second

The question the product should answer for a nontechnical office manager:
- what systems are connected?
- what data can this workflow use?
- who is allowed to run it?
- what did it do yesterday/this week?

Target users / likely buyer

SMB owners, operators, office managers, or department leads who are not deeply technical but want:
- guardrails
- visibility
- approvals
- confidence

Potential local angle

Jacksonville was mentioned as an advantage. The earlier idea was to use local industry concentration as a wedge instead of going horizontal immediately.
Good wedge candidates discussed:
- logistics / distribution
- finance / insurance operations
- healthcare-adjacent admin
- advanced manufacturing

A good initial offer would be workflow-specific rather than platform-generic.

Example wedge:
Connect email + spreadsheets + line-of-business exports for a logistics or operations-heavy SMB, detect issues/exceptions, summarize activity, and optionally draft actions subject to approval.

Product principles

1. Enforcement first, presentation second.
2. Read-only by default.
3. Keep AI actions behind approval until trust is earned.
4. Use simple business language, not technical AI language.
5. Sell “peace of mind” and control, not “AI magic.”
6. Start narrow: a few workflows, a few connectors, one buyer persona.

Absolutely necessary features for v1

1. Connected Apps
- show which systems are connected
- connection health
- last successful sync
- reconnect/disconnect

2. Data Scope Controls
Admins can define what each workflow is allowed to use.
Examples:
- workflow can use QuickBooks but not payroll
- workflow can read HubSpot contacts but not notes
- workflow can read service tickets but not financial reports

Need:
- source-level allow/deny
- optional sub-scope selection where easy (folder/report/table/category)
- default deny unless allowed

3. User Access Controls
Need a simple mapping of:
- who
- can run which workflow
- against which data

Do not overbuild permissions initially.
Use simple roles:
- admin
- operator
- reviewer
- viewer

4. Action Mode / Safety Mode
Each workflow should have a mode:
- read only
- draft only
- approval required for actions

Examples:
- summarize data = read only
- draft an email = draft only
- send email / update CRM / create invoice = approval required

5. Approval Queue
A place to review proposed AI actions.
Each item should show:
- proposed action
- short reason/summary
- source data used
- approve / reject
- timestamp and user

6. Activity Log
Mandatory.
For each run, show:
- who triggered it
- which workflow ran
- which data sources it touched
- what output it produced
- what was blocked
- whether an action was proposed or taken
- timestamp
- status: success / failed / pending approval

7. Basic Alerts
Need a few obvious alerts:
- connector failed
- repeated workflow failures
- blocked access attempt
- unusually high volume
- approvals pending too long

Email is enough at first.

8. One Summary Screen
Not many dashboards.
One page that shows:
- what ran this week
- what failed
- what is waiting for approval
- which sources are connected
- which workflows are active

Nice to have

- sensitive data masking / redaction
- policy templates
- scheduled summaries (weekly email)
- search/filtering in activity log
- simple output feedback (thumbs up/down, wrong source, too risky, not useful)
- usage/cost visibility
- Slack/Teams notifications
- source-specific controls with more granularity

Ignore in first 60 days

- no-code workflow builder
- fancy BI dashboards
- full field-level lineage everywhere
- dozens of connectors
- customer-selectable model switching
- fine-tuning
- autonomous write-back without review
- complex role hierarchies
- white-labeling
- mobile app
- advanced multi-tenant reporting
- chat-first UX as the main product interface

Best v1 screens

Keep v1 to 5 screens:

1. Connected Apps
- what is connected
- health
- sync status

2. Data Access Rules
- what each workflow is allowed to read/use

3. People & Permissions
- which users can run which workflows

4. Activity Feed
- what happened
- what data was touched
- what failed
- what was blocked

5. Approvals
- proposed actions waiting for review

Recommended UX language

Do not expose internal AI/runtime concepts to SMB users.
Translate the system into plain language like:
- “This assistant can read invoices but not payroll.”
- “Only Sarah and Mike can run this.”
- “Nothing sends emails unless approved.”
- “Show me everything it touched this week.”

60-day build order

Days 1–15
- define the core policy model
- connectors
- source allow/deny rules
- user/workflow mapping
- read-only default
- basic run logging

Days 16–30
- add action modes
- add approval queue
- blocked-action handling
- run detail view

Days 31–45
- build admin UI
- Connected Apps page
- Data Access page
- People/Roles page
- Activity Feed page

Days 46–60
- add monitoring basics
- basic alerts
- one summary dashboard
- weekly email summary
- harden based on pilot usage

Suggested product framing

This is not just a dashboard.
This is an admin control plane for AI workflows.

The product should help SMBs answer:
- what data is connected
- what the AI can use
- who can run it
- what happened recently
- what needs human review

Suggested implementation direction

Use pi.dev as the runtime/orchestration layer.
Build the missing control plane around it:
- connectors
- policy engine
- permission checks
- approval flow
- event log / audit log
- monitoring / alerts
- simple admin UI

Likely data model / objects to define

Need objects/tables roughly like:
- users
- roles
- workflows
- connected_sources
- source_scopes
- workflow_source_permissions
- user_workflow_permissions
- runs
- run_events
- approvals
- alerts

High-level technical requirements

- every run should be logged
- every access to a source should be logged
- every blocked action should be logged
- every write/action should be either disabled or approval-gated
- system defaults should be conservative (read-only, deny by default)

Non-goals for v1

- generic platform for every industry
- huge connector marketplace
- autonomous AI employees
- polished analytics suite
- fully customizable workflow builder

Definition of ready for initial revenue

A nontechnical office manager should be able to answer, without help:
- what systems are connected?
- what data is this workflow allowed to use?
- who is allowed to run it?
- what did it do this week?

Requested next step for Codex

Please turn this into:
1. a lean technical architecture
2. a proposed data model/schema
3. v1 API surface
4. v1 UI route/component map
5. implementation plan for the first 60 days
6. clear separation between must-build-now vs later
