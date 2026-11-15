# ECOSHIELD — Product Direction and MVP Blueprint

## Product direction

ECOSHIELD is a lightweight security-readiness and human-risk platform for small teams that do not have a dedicated security operations centre. It helps a team run repeatable security assessments, understand risky behaviours, deliver relevant micro-learning, and measure whether security habits improve.

The Render-hosted demonstration is inspiration and evidence of the original direction, not a specification to copy. The GitHub implementation is the product source of truth. We should preserve useful working concepts while improving the workflow, security model, usability, and measurement.

### Initial customer

Small organisations and teams that need practical security awareness and basic human-risk visibility but cannot justify a full SOC stack or a dedicated analyst.

The initial product should be fast to configure, inexpensive to operate, understandable to a non-specialist administrator, and useful without SIEM, EDR, or identity-provider integrations.

## Expanded product architecture: organisation-configured human risk

ECOSHIELD is intended to grow beyond a campaign-and-awareness prototype into an organisation-configured Human Risk Management and Security Response platform. The campaign workflow remains the first usable entry point, but it must operate on shared organisation configuration and shared risk, learning, policy, and response services.

### Organisation setup and security profile

During onboarding, an authorised administrator should be able to configure:

- Organisation identity, timezone, departments, teams, and employee directory source.
- Authorised data connections and their scope (initially import/read-only wherever possible).
- Risk indicators, weights, evidence windows, decay/expiry rules, and review thresholds.
- Campaign defaults, eligible audiences, scenario categories, and assessment frequency.
- Awareness content, language/readability level, and escalation contacts.
- Response policies, approval requirements, permitted actions, and restrictions.

Configuration must be versioned and auditable. Every assessment should retain the configuration version and policy version used, so an administrator can understand why a score or recommendation was produced. Do not allow an integration to grant broader access than the administrator explicitly authorised.

### Three connected but separate engines

1. **Risk assessment engine:** combines permitted evidence such as assessment outcomes, reporting behaviour, repeated patterns, learning completion, role context, and approved security signals. It produces explainable indicators with evidence, confidence/limitations, time window, and freshness. A simulation result alone is never proof of compromise.
2. **Awareness and learning engine:** maps a verified learning need to a short, plain-language teaching note, examples, practical next steps, and an optional retest. It must avoid jargon, explain why the behaviour matters, and never shame employees.
3. **Response and policy engine:** evaluates the organisation's configured policy against the risk assessment and proposes an action. Actions can include no action, targeted learning, administrator review, or an approved temporary restriction. Every decision records the rule, evidence, approver (if required), execution result, and verification state.

These engines share event and identity contracts but keep their responsibilities distinct. A risk score is not itself an instruction to block a user.

### Response safety and control levels

- **Simulation:** demonstrate the proposed action and label it clearly as simulated.
- **Recommendation:** create a review item for an authorised administrator.
- **Controlled execution:** only through an explicitly authorised integration, least-privilege credentials, scoped policy, approval where appropriate, time limits, rollback/recovery path, and post-action verification.

A failed awareness test must never automatically lock an account, isolate a device, revoke access, or label an employee compromised. High-impact actions require independent evidence and explicit policy authorisation. If execution cannot be verified, report the action as unverified or failed—not successful.

### Risk score semantics

Risk indicators are configurable decision-support signals, not employee grades or predictions of individual character. Show contributing factors and their weights, evidence timestamps, confidence/coverage limitations, and expiry/decay. Include positive protective behaviour such as reporting suspicious activity and improvement after learning. Restrict individual-level visibility to authorised roles; prefer aggregate team trends for routine reporting. Do not expose punitive public leaderboards.

### Shared-core implementation sequence

Build this incrementally on the existing campaign workflow:

1. Stable employee identity and authenticated subject ownership (IDs, not display names).
2. Canonical event records with source, timestamp, event type, tenant/organisation context, and idempotency key.
3. Versioned organisation configuration and risk indicator definitions.
4. Explainable risk assessment service, with score breakdown and time windows.
5. Plain-language awareness content mapped to assessment evidence.
6. Policy evaluation and response recommendation records.
7. Approval-gated, verified integrations only after the above contracts are tested.

The current prototype remains single-organisation and demo-authenticated. Do not claim multi-tenancy, production integrations, AI-driven scoring, or real containment until those capabilities are implemented and independently tested.

## Product loop

1. **Assess** — An administrator creates a campaign, chooses a scenario and audience, and schedules a controlled assessment.
2. **Observe** — ECOSHIELD records safe behavioural signals such as opened, clicked, reported, ignored, or completed. It must never collect real passwords or other secrets.
3. **Explain** — The system explains what the behaviour indicates, what it does not prove, and why the signal matters.
4. **Educate** — The employee receives a short lesson and a practical action matched to the observed gap.
5. **Retest** — A later assessment checks whether behaviour improved.
6. **Report** — The administrator sees team-level patterns, participation, reporting behaviour, learning completion, and changes over time.

## MVP capabilities

### 1. Team and campaign management
- Manage a small employee directory and departments.
- Create one-time or recurring assessment campaigns.
- Select an audience by employee or department.
- Set a start time, end time, and campaign status.
- Show the campaign schedule and its delivery/participation state.
- Make timezone handling explicit; default display timezone is Africa/Kampala unless configured otherwise.

### 2. Safe simulation library
Start with a small, reusable library of controlled scenarios:
- Suspicious link / phishing message.
- Unexpected attachment.
- Impersonation or urgent payment request.
- MFA fatigue / unexpected approval request.
- QR-code or shortened-link awareness.

Scenarios must be clearly controlled training exercises. They must not harvest credentials, execute attachments, deliver malware, or impersonate a real third party without authorisation. For the first MVP, in-app or manually shared test links are preferable to sending external email automatically.

### 3. Behaviour and risk indicators
Use explainable signals rather than an opaque employee score. Track, where available:
- Interaction outcome (clicked, ignored, reported, completed).
- Reporting rate and time-to-report.
- Repeat behaviour across campaigns.
- Learning completion and retest outcome.
- Participation and campaign coverage.

Show the evidence behind every indicator. Avoid treating one click as proof that an employee is compromised or unsafe. Do not use public employee leaderboards or punitive rankings.

### 4. Targeted micro-learning
- Recommend a short lesson based on the observed behaviour.
- Keep lessons practical and concise.
- Record completion.
- Offer a follow-up assessment.
- Show the employee what they can do differently next time.

### 5. Small-team dashboard
The administrator should quickly understand:
- Which campaigns are scheduled, active, or complete.
- Which departments have participated.
- The most common behaviour gaps.
- Reporting and learning-completion rates.
- Whether the team is improving across repeated assessments.

### 6. Safe response guidance
Provide suggested next steps and a record of what the administrator did. The MVP may simulate response actions, but must label them as simulated. It must not claim to isolate a device, revoke access, lock a real account, or contact an incident team unless an actual integration performed that action and the result was verified.

## Design principles

- **Lightweight first:** Flask and SQLite are suitable for a controlled single-instance MVP; avoid adding infrastructure without a demonstrated need.
- **Privacy by design:** collect the minimum behavioural data required; no real credentials; restrict employee-level detail to authorised roles.
- **Explainable:** show the event, rule, reason, and recommended action behind every risk indicator.
- **Non-punitive:** use assessments to improve team readiness, not shame or rank employees.
- **Reliable scheduling:** scheduled work must have an explicit execution mechanism, timezone, retry policy, and visible status. A campaign must not be shown as sent or completed merely because it was created.
- **Honest product claims:** distinguish simulated behaviour from real security controls and rule-based analysis from AI.

## MVP acceptance criteria for the founder meetings

A credible first demonstration should allow us to:
1. Sign in as an administrator.
2. Create a campaign for a selected employee or department.
3. Set a future schedule and see its status.
4. Run a controlled simulation using a safe test interaction.
5. Record the outcome against the correct campaign and employee.
6. Recommend and display a relevant learning item.
7. Record learning completion and a follow-up assessment.
8. Show an aggregate campaign report comparing the initial assessment with a linked retest, including click rate, reporting rate, and learning completion changes.
9. Demonstrate role restrictions and explain which actions are simulated.

If a feature is not implemented end-to-end, the interface and pitch must label it as planned or simulated.

## Delivery sequence

### Current MVP stabilisation
- Keep the login, role checks, simulation and event records isolated from production employee data.
- Use rule-based language consistently; do not present the watcher as AI.
- Keep training indicators separate from compromise status, account lockout, or containment actions.
- Validate the campaign-to-assignment-to-learning path with a small synthetic team.
- Prepare a repeatable demo dataset and reset procedure.

### After the first meeting
- Prioritise feedback from founders.
- Improve campaign scheduling and audience management.
- Complete targeted learning and retest reporting.
- Validate the need with potential small-business users before adding integrations.

### Later roadmap
- Optional email/calendar integrations.
- Multi-tenant organisation support.
- External identity, endpoint, and SIEM integrations.
- Stronger analytics after collecting sufficient, consented data.
- More advanced automation only where an integration can safely verify the action.

## Current implementation caveats

The current branch contains a Flask dashboard, department-level simulation controls, SQLite employee/event records, scheduled campaigns, per-employee assignments, response recording, targeted lesson assignment, learning completion, and a separate polling scheduler worker. These features are implemented in the prototype but must still be validated end-to-end.

The employee login is still configured for one demo employee rather than supporting multiple independently authenticated employees. The prototype does not send real campaign emails or support multiple independently authenticated employee accounts. It now supports aggregate reports and baseline-linked retest comparisons for matching audience/scenario campaigns, but it is not yet a complete multi-tenant team-readiness reporting platform. The simulation library and seeded employee records are synthetic.

The event watcher and analysis endpoint are rule-based. Training indicators are not evidence of compromise. No real account lockout, device isolation, access revocation, or external incident escalation is performed. The Render-hosted demo is not automatically updated by changes on this development branch.
